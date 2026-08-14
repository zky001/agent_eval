from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    model_name: str
    model_id: int
    dataset_name: str
    score: float
    completed_runs: int
    avg_latency: float
    avg_cost_usd: float | None = None


class ModelComparison(BaseModel):
    model_name: str
    model_id: int
    dataset_name: str
    score: float
    completed_runs: int
    avg_latency: float
    avg_cost_usd: float | None = None


class ScoreHistoryPoint(BaseModel):
    run_id: int
    model_id: int
    model_name: str
    score: float
    completed_at: str | None
