from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.dataset import DatasetResponse
from app.schemas.model_config import ModelConfigResponse


class RunCreate(BaseModel):
    dataset_id: int
    model_config_id: int
    name: str | None = None
    params_override: dict = {}


class RunResponse(BaseModel):
    id: int
    name: str | None
    dataset_id: int
    model_config_id: int
    status: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    aggregate_score: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    error_message: str | None
    dataset: DatasetResponse | None = None
    model_config: ModelConfigResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class RunListResponse(BaseModel):
    id: int
    name: str | None
    dataset_id: int
    model_config_id: int
    status: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    aggregate_score: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)
