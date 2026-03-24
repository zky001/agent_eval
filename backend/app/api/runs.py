import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.task import Task
from app.models.result import Result
from app.schemas.run import RunCreate, RunResponse
from app.services.dispatcher import RunExecutor

router = APIRouter(prefix="/runs", tags=["runs"])


def _parse_json_field(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return value


def _run_to_response(run: EvaluationRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        name=run.name,
        dataset_id=run.dataset_id,
        model_config_id=run.model_config_id,
        status=run.status,
        params_override=_parse_json_field(run.params_override),
        total_tasks=run.total_tasks or 0,
        completed_tasks=run.completed_tasks or 0,
        failed_tasks=run.failed_tasks or 0,
        aggregate_score=run.aggregate_score,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        error_message=run.error_message,
    )


@router.get("/", response_model=list[RunResponse])
async def list_runs(
    dataset_id: Optional[int] = None,
    model_config_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(EvaluationRun).order_by(EvaluationRun.created_at.desc())

    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)
    if model_config_id is not None:
        query = query.where(EvaluationRun.model_config_id == model_config_id)
    if status is not None:
        query = query.where(EvaluationRun.status == status)

    result = await db.execute(query)
    runs = result.scalars().all()
    return [_run_to_response(r) for r in runs]


@router.post("/", response_model=RunResponse)
async def create_run(run_create: RunCreate, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, run_create.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    model_config = await db.get(ModelConfig, run_create.model_config_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model config not found")

    run = EvaluationRun(
        name=run_create.name or f"{dataset.name} - {model_config.name}",
        dataset_id=run_create.dataset_id,
        model_config_id=run_create.model_config_id,
        status="pending",
        params_override=json.dumps(run_create.params_override),
        total_tasks=0,
        completed_tasks=0,
        failed_tasks=0,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    executor = RunExecutor(async_session, run.id)
    asyncio.create_task(executor.execute())

    return _run_to_response(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_response(run)


@router.get("/{run_id}/tasks")
async def get_run_tasks(
    run_id: int,
    status: Optional[str] = None,
    is_correct: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    query = select(Task).where(Task.run_id == run_id).order_by(Task.id)
    if status is not None:
        query = query.where(Task.status == status)

    result = await db.execute(query.offset(skip).limit(limit))
    tasks = result.scalars().all()

    task_responses = []
    for task in tasks:
        res_query = await db.execute(select(Result).where(Result.task_id == task.id))
        task_result = res_query.scalar_one_or_none()

        item = await db.get(DatasetItem, task.dataset_item_id)

        if is_correct is not None and task_result:
            if task_result.is_correct != is_correct:
                continue

        response = {
            "task_id": task.id,
            "item_index": item.item_index if item else 0,
            "prompt": item.prompt if item else "",
            "reference_answer": item.reference_answer if item else None,
            "status": task.status,
            "raw_response": task_result.raw_response if task_result else None,
            "parsed_answer": task_result.parsed_answer if task_result else None,
            "is_correct": task_result.is_correct if task_result else None,
            "score": task_result.score if task_result else None,
            "latency_ms": task_result.latency_ms if task_result else None,
        }
        task_responses.append(response)

    count_query = select(func.count(Task.id)).where(Task.run_id == run_id)
    if status is not None:
        count_query = count_query.where(Task.status == status)
    total = (await db.execute(count_query)).scalar() or 0

    return {"tasks": task_responses, "total": total}


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status '{run.status}'")
    run.status = "cancelled"
    run.completed_at = datetime.utcnow()
    return {"detail": "Run cancelled"}


@router.delete("/{run_id}")
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running evaluation")

    tasks_result = await db.execute(select(Task).where(Task.run_id == run_id))
    tasks = tasks_result.scalars().all()
    for task in tasks:
        res = await db.execute(select(Result).where(Result.task_id == task.id))
        result_obj = res.scalar_one_or_none()
        if result_obj:
            await db.delete(result_obj)
        await db.delete(task)
    await db.delete(run)
    return {"detail": "Run deleted"}
