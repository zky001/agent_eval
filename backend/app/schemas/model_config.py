from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelConfigCreate(BaseModel):
    name: str
    provider: str
    api_base_url: str | None = None
    api_key: str | None = None
    model_id: str
    default_params: dict = {}


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    api_base_url: str | None = None
    api_key: str | None = None
    model_id: str | None = None
    default_params: dict | None = None


class ModelConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    api_base_url: str | None
    api_key: str | None
    model_id: str
    default_params: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelTestResponse(BaseModel):
    success: bool
    response: str | None = None
    error: str | None = None
    latency_ms: int | None = None
