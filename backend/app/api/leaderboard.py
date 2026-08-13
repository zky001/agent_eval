from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dataset import Dataset
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.result import Result
from app.models.task import Task
from app.schemas.leaderboard import LeaderboardEntry, ModelComparison

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


async def _leaderboard_rows(
    db: AsyncSession,
    dataset_id: Optional[int] = None,
    model_ids: Optional[list[int]] = None,
):
    """Aggregate per (model, dataset), giving every run equal weight.

    Score and latency are aggregated in separate subqueries: a single flat
    JOIN through tasks/results repeats each run's aggregate_score once per
    task row, silently weighting runs by task count.
    """
    run_filter = [
        EvaluationRun.status == "completed",
        EvaluationRun.aggregate_score.isnot(None),
    ]
    if dataset_id is not None:
        run_filter.append(EvaluationRun.dataset_id == dataset_id)
    if model_ids:
        run_filter.append(EvaluationRun.model_config_id.in_(model_ids))

    score_sq = (
        select(
            EvaluationRun.model_config_id.label("model_config_id"),
            EvaluationRun.dataset_id.label("dataset_id"),
            func.avg(EvaluationRun.aggregate_score).label("score"),
            func.count(EvaluationRun.id).label("completed_runs"),
        )
        .where(*run_filter)
        .group_by(EvaluationRun.model_config_id, EvaluationRun.dataset_id)
        .subquery()
    )

    latency_sq = (
        select(
            EvaluationRun.model_config_id.label("model_config_id"),
            EvaluationRun.dataset_id.label("dataset_id"),
            func.avg(Result.latency_ms).label("avg_latency"),
        )
        .join(Task, Task.run_id == EvaluationRun.id)
        .join(Result, Result.task_id == Task.id)
        .where(*run_filter)
        .where(Result.latency_ms.isnot(None))
        .group_by(EvaluationRun.model_config_id, EvaluationRun.dataset_id)
        .subquery()
    )

    query = (
        select(
            ModelConfig.name.label("model_name"),
            ModelConfig.id.label("model_id"),
            Dataset.name.label("dataset_name"),
            score_sq.c.score,
            score_sq.c.completed_runs,
            latency_sq.c.avg_latency,
        )
        .join(ModelConfig, ModelConfig.id == score_sq.c.model_config_id)
        .join(Dataset, Dataset.id == score_sq.c.dataset_id)
        .outerjoin(
            latency_sq,
            (latency_sq.c.model_config_id == score_sq.c.model_config_id)
            & (latency_sq.c.dataset_id == score_sq.c.dataset_id),
        )
        .order_by(score_sq.c.score.desc())
    )

    return (await db.execute(query)).all()


def _row_to_entry(row) -> dict:
    return {
        "model_name": row.model_name,
        "model_id": row.model_id,
        "dataset_name": row.dataset_name,
        "score": round(row.score * 100, 2) if row.score is not None else 0,
        "completed_runs": row.completed_runs,
        "avg_latency": round(row.avg_latency, 0) if row.avg_latency is not None else 0,
    }


@router.get("/", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    rows = await _leaderboard_rows(db, dataset_id=dataset_id)
    return [LeaderboardEntry(**_row_to_entry(row)) for row in rows]


@router.get("/compare", response_model=list[ModelComparison])
async def compare_models(
    model_ids: str = Query(..., description="Comma-separated model IDs"),
    dataset_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        model_id_list = [int(x.strip()) for x in model_ids.split(",") if x.strip()]
    except ValueError:
        return []
    if not model_id_list:
        return []

    rows = await _leaderboard_rows(db, dataset_id=dataset_id, model_ids=model_id_list)
    return [ModelComparison(**_row_to_entry(row)) for row in rows]
