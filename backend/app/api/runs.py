import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.result import Result
from app.models.task import Task
from app.schemas.run import BatchRunCreate, RunCreate, RunResponse
from app.services.dispatcher import spawn_run
from app.utils import utcnow

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


def _run_to_response(
    run: EvaluationRun,
    dataset_name: str | None = None,
    model_name: str | None = None,
    **stats,
) -> RunResponse:
    return RunResponse(
        id=run.id,
        name=run.name,
        dataset_id=run.dataset_id,
        model_config_id=run.model_config_id,
        dataset_name=dataset_name,
        model_name=model_name,
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
        **stats,
    )


@router.get("/", response_model=list[RunResponse])
async def list_runs(
    dataset_id: Optional[int] = None,
    model_config_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(EvaluationRun, Dataset.name, ModelConfig.name)
        .outerjoin(Dataset, Dataset.id == EvaluationRun.dataset_id)
        .outerjoin(ModelConfig, ModelConfig.id == EvaluationRun.model_config_id)
        .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
    )

    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)
    if model_config_id is not None:
        query = query.where(EvaluationRun.model_config_id == model_config_id)
    if status is not None:
        query = query.where(EvaluationRun.status == status)

    rows = (await db.execute(query.offset(skip).limit(limit))).all()
    return [
        _run_to_response(run, dataset_name=ds_name, model_name=mc_name)
        for run, ds_name, mc_name in rows
    ]


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
        created_at=utcnow(),
    )
    db.add(run)
    # Commit BEFORE spawning: the executor reads from its own session and
    # would otherwise race the request transaction and miss the new run.
    await db.commit()

    spawn_run(async_session, run.id)

    return _run_to_response(run, dataset_name=dataset.name, model_name=model_config.name)


@router.post("/batch", response_model=list[RunResponse])
async def create_batch_runs(batch: BatchRunCreate, db: AsyncSession = Depends(get_db)):
    if not batch.dataset_ids:
        raise HTTPException(status_code=400, detail="At least one dataset_id is required")
    if not batch.model_config_ids:
        raise HTTPException(status_code=400, detail="At least one model_config_id is required")

    datasets: dict[int, Dataset] = {}
    for dataset_id in dict.fromkeys(batch.dataset_ids):
        dataset = await db.get(Dataset, dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
        datasets[dataset_id] = dataset

    model_configs: dict[int, ModelConfig] = {}
    for model_config_id in dict.fromkeys(batch.model_config_ids):
        model_config = await db.get(ModelConfig, model_config_id)
        if not model_config:
            raise HTTPException(
                status_code=404, detail=f"Model config {model_config_id} not found"
            )
        model_configs[model_config_id] = model_config

    params_json = json.dumps(batch.params_override)
    created: list[tuple[EvaluationRun, str, str]] = []
    for dataset_id, dataset in datasets.items():
        for model_config_id, model_config in model_configs.items():
            run = EvaluationRun(
                name=f"{dataset.name} - {model_config.name}",
                dataset_id=dataset_id,
                model_config_id=model_config_id,
                status="pending",
                params_override=params_json,
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                created_at=utcnow(),
            )
            db.add(run)
            created.append((run, dataset.name, model_config.name))

    # Single commit for the whole batch, then start the executors.
    await db.commit()
    for run, _, _ in created:
        spawn_run(async_session, run.id)

    return [
        _run_to_response(run, dataset_name=ds_name, model_name=mc_name)
        for run, ds_name, mc_name in created
    ]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(EvaluationRun, Dataset.name, ModelConfig.name)
            .outerjoin(Dataset, Dataset.id == EvaluationRun.dataset_id)
            .outerjoin(ModelConfig, ModelConfig.id == EvaluationRun.model_config_id)
            .where(EvaluationRun.id == run_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    run, dataset_name, model_name = row

    stats_row = (
        await db.execute(
            select(
                func.count(Result.id).filter(Result.is_correct.is_(True)),
                func.avg(Result.latency_ms),
                func.sum(Result.token_count),
            )
            .join(Task, Task.id == Result.task_id)
            .where(Task.run_id == run_id)
        )
    ).one()
    correct_tasks, avg_latency, total_tokens = stats_row

    return _run_to_response(
        run,
        dataset_name=dataset_name,
        model_name=model_name,
        correct_tasks=correct_tasks or 0,
        avg_latency_ms=round(avg_latency, 1) if avg_latency is not None else None,
        total_tokens=total_tokens,
    )


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

    # Single JOIN query to avoid N+1 queries
    query = (
        select(Task, Result, DatasetItem)
        .outerjoin(Result, Result.task_id == Task.id)
        .outerjoin(DatasetItem, DatasetItem.id == Task.dataset_item_id)
        .where(Task.run_id == run_id)
        .order_by(Task.id)
    )
    count_query = (
        select(func.count(Task.id))
        .outerjoin(Result, Result.task_id == Task.id)
        .where(Task.run_id == run_id)
    )
    if status is not None:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    if is_correct is not None:
        query = query.where(Result.is_correct == is_correct)
        count_query = count_query.where(Result.is_correct == is_correct)

    total = (await db.execute(count_query)).scalar() or 0
    rows = (await db.execute(query.offset(skip).limit(limit))).all()

    task_responses = [
        {
            "task_id": task.id,
            "item_index": item.item_index if item else 0,
            "prompt": item.prompt if item else "",
            "reference_answer": item.reference_answer if item else None,
            "status": task.status,
            "raw_response": result.raw_response if result else None,
            "parsed_answer": result.parsed_answer if result else None,
            "is_correct": result.is_correct if result else None,
            "score": result.score if result else None,
            "latency_ms": result.latency_ms if result else None,
            "token_count": result.token_count if result else None,
            "evaluation_details": _parse_json_field(result.evaluation_details)
            if result
            else {},
        }
        for task, result, item in rows
    ]

    return {"tasks": task_responses, "total": total}


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status '{run.status}'")
    run.status = "cancelled"
    run.completed_at = utcnow()
    return {"detail": "Run cancelled"}


@router.delete("/{run_id}")
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running evaluation")

    # Bulk deletes: the old per-row loop issued 2 queries per task.
    task_ids = select(Task.id).where(Task.run_id == run_id)
    await db.execute(delete(Result).where(Result.task_id.in_(task_ids)))
    await db.execute(delete(Task).where(Task.run_id == run_id))
    await db.execute(delete(EvaluationRun).where(EvaluationRun.id == run_id))
    return {"detail": "Run deleted"}
