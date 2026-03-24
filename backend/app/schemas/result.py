from pydantic import BaseModel, ConfigDict


class TaskResultResponse(BaseModel):
    task_id: int
    item_index: int
    prompt: str
    reference_answer: str | None
    raw_response: str | None
    parsed_answer: str | None
    is_correct: bool | None
    score: float | None
    latency_ms: int | None
    status: str

    model_config = ConfigDict(from_attributes=True)
