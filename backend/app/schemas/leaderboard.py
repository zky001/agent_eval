from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    model_name: str
    model_id: int
    dataset_name: str
    score: float
    completed_runs: int
    avg_latency: float


class ModelComparison(BaseModel):
    model_name: str
    model_id: int
    dataset_name: str
    score: float
    completed_runs: int
    avg_latency: float
