from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dataset import Dataset
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.result import Result
from app.models.task import Task
from app.schemas.leaderboard import LeaderboardEntry, ModelComparison

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            ModelConfig.name.label("model_name"),
            ModelConfig.id.label("model_id"),
            Dataset.name.label("dataset_name"),
            func.avg(EvaluationRun.aggregate_score).label("score"),
            func.count(EvaluationRun.id).label("completed_runs"),
        )
        .join(ModelConfig, EvaluationRun.model_config_id == ModelConfig.id)
        .join(Dataset, EvaluationRun.dataset_id == Dataset.id)
        .where(EvaluationRun.status == "completed")
        .where(EvaluationRun.aggregate_score.isnot(None))
        .group_by(ModelConfig.id, Dataset.id)
        .order_by(func.avg(EvaluationRun.aggregate_score).desc())
    )

    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)

    result = await db.execute(query)
    rows = result.all()

    entries = []
    for row in rows:
        latency_query = (
            select(func.avg(Result.latency_ms))
            .join(Task, Result.task_id == Task.id)
            .join(EvaluationRun, Task.run_id == EvaluationRun.id)
            .where(EvaluationRun.model_config_id == row.model_id)
            .where(EvaluationRun.status == "completed")
        )
        if dataset_id is not None:
            latency_query = latency_query.where(EvaluationRun.dataset_id == dataset_id)

        avg_latency = (await db.execute(latency_query)).scalar() or 0

        entries.append(
            LeaderboardEntry(
                model_name=row.model_name,
                model_id=row.model_id,
                dataset_name=row.dataset_name,
                score=round(row.score * 100, 2) if row.score else 0,
                completed_runs=row.completed_runs,
                avg_latency=round(avg_latency, 0) if avg_latency else 0,
            )
        )

    return entries


@router.get("/compare", response_model=list[ModelComparison])
async def compare_models(
    model_ids: str = Query(..., description="Comma-separated model IDs"),
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    model_id_list = [int(x.strip()) for x in model_ids.split(",") if x.strip()]

    results = []
    for mid in model_id_list:
        model = await db.get(ModelConfig, mid)
        if not model:
            continue

        query = (
            select(
                func.avg(EvaluationRun.aggregate_score).label("score"),
                func.count(EvaluationRun.id).label("completed_runs"),
                Dataset.name.label("dataset_name"),
            )
            .join(Dataset, EvaluationRun.dataset_id == Dataset.id)
            .where(EvaluationRun.model_config_id == mid)
            .where(EvaluationRun.status == "completed")
            .where(EvaluationRun.aggregate_score.isnot(None))
            .group_by(Dataset.id)
        )

        if dataset_id is not None:
            query = query.where(EvaluationRun.dataset_id == dataset_id)

        rows = await db.execute(query)
        for row in rows.all():
            latency_q = (
                select(func.avg(Result.latency_ms))
                .join(Task, Result.task_id == Task.id)
                .join(EvaluationRun, Task.run_id == EvaluationRun.id)
                .where(EvaluationRun.model_config_id == mid)
                .where(EvaluationRun.status == "completed")
            )
            if dataset_id is not None:
                latency_q = latency_q.where(EvaluationRun.dataset_id == dataset_id)
            avg_lat = (await db.execute(latency_q)).scalar() or 0

            results.append(
                ModelComparison(
                    model_name=model.name,
                    model_id=model.id,
                    dataset_name=row.dataset_name,
                    score=round(row.score * 100, 2) if row.score else 0,
                    completed_runs=row.completed_runs,
                    avg_latency=round(avg_lat, 0) if avg_lat else 0,
                )
            )

    return results
