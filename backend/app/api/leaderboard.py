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


def _build_leaderboard_query(dataset_id: Optional[int] = None):
    """Single query that fetches score, run count, and avg latency together."""
    query = (
        select(
            ModelConfig.name.label("model_name"),
            ModelConfig.id.label("model_id"),
            Dataset.name.label("dataset_name"),
            func.avg(EvaluationRun.aggregate_score).label("score"),
            func.count(EvaluationRun.id.distinct()).label("completed_runs"),
            func.avg(Result.latency_ms).label("avg_latency"),
        )
        .join(ModelConfig, EvaluationRun.model_config_id == ModelConfig.id)
        .join(Dataset, EvaluationRun.dataset_id == Dataset.id)
        .outerjoin(Task, Task.run_id == EvaluationRun.id)
        .outerjoin(Result, Result.task_id == Task.id)
        .where(EvaluationRun.status == "completed")
        .where(EvaluationRun.aggregate_score.isnot(None))
        .group_by(ModelConfig.id, Dataset.id)
        .order_by(func.avg(EvaluationRun.aggregate_score).desc())
    )
    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)
    return query


@router.get("/", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(_build_leaderboard_query(dataset_id))
    rows = result.all()

    return [
        LeaderboardEntry(
            model_name=row.model_name,
            model_id=row.model_id,
            dataset_name=row.dataset_name,
            score=round(row.score * 100, 2) if row.score else 0,
            completed_runs=row.completed_runs,
            avg_latency=round(row.avg_latency, 0) if row.avg_latency else 0,
        )
        for row in rows
    ]


@router.get("/compare", response_model=list[ModelComparison])
async def compare_models(
    model_ids: str = Query(..., description="Comma-separated model IDs"),
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    model_id_list = [int(x.strip()) for x in model_ids.split(",") if x.strip()]
    if not model_id_list:
        return []

    query = (
        select(
            ModelConfig.name.label("model_name"),
            ModelConfig.id.label("model_id"),
            Dataset.name.label("dataset_name"),
            func.avg(EvaluationRun.aggregate_score).label("score"),
            func.count(EvaluationRun.id.distinct()).label("completed_runs"),
            func.avg(Result.latency_ms).label("avg_latency"),
        )
        .join(ModelConfig, EvaluationRun.model_config_id == ModelConfig.id)
        .join(Dataset, EvaluationRun.dataset_id == Dataset.id)
        .outerjoin(Task, Task.run_id == EvaluationRun.id)
        .outerjoin(Result, Result.task_id == Task.id)
        .where(EvaluationRun.model_config_id.in_(model_id_list))
        .where(EvaluationRun.status == "completed")
        .where(EvaluationRun.aggregate_score.isnot(None))
        .group_by(ModelConfig.id, Dataset.id)
    )
    if dataset_id is not None:
        query = query.where(EvaluationRun.dataset_id == dataset_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        ModelComparison(
            model_name=row.model_name,
            model_id=row.model_id,
            dataset_name=row.dataset_name,
            score=round(row.score * 100, 2) if row.score else 0,
            completed_runs=row.completed_runs,
            avg_latency=round(row.avg_latency, 0) if row.avg_latency else 0,
        )
        for row in rows
    ]
