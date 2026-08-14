from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RunCreate(BaseModel):
    name: str | None = None
    dataset_id: int
    model_config_id: int
    judge_model_config_id: int | None = None
    params_override: dict = {}


class BatchRunCreate(BaseModel):
    dataset_ids: list[int]
    model_config_ids: list[int]
    judge_model_config_id: int | None = None
    params_override: dict = {}


class RunResponse(BaseModel):
    id: int
    name: str | None
    dataset_id: int
    model_config_id: int
    judge_model_config_id: int | None = None
    dataset_name: str | None = None
    model_name: str | None = None
    status: str
    params_override: dict = {}
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    aggregate_score: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    error_message: str | None
    # Detail-only aggregate stats (None in list responses)
    correct_tasks: int | None = None
    avg_latency_ms: float | None = None
    total_tokens: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    id: int
    run_id: int
    dataset_item_id: int
    status: str
    dispatched_at: datetime | None
    completed_at: datetime | None
    result: "ResultResponse | None" = None

    model_config = ConfigDict(from_attributes=True)


class ResultResponse(BaseModel):
    id: int
    task_id: int
    raw_response: str | None
    parsed_answer: str | None
    is_correct: bool | None
    score: float | None
    latency_ms: int | None
    token_count: int | None
    evaluation_details: dict = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
