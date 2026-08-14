from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetImportRequest(BaseModel):
    source: str
    origin: str = "sample"  # "sample" (built-in) or "huggingface"
    split: str = "test"
    subset: str | None = None
    max_items: int | None = None


class DatasetUploadItem(BaseModel):
    prompt: str
    reference_answer: str | None = None
    metadata: dict = {}


class DatasetUploadRequest(BaseModel):
    name: str
    dataset_type: str = "custom"
    description: str | None = None
    system_prompt: str | None = None
    items: list[DatasetUploadItem]


class DatasetResponse(BaseModel):
    id: int
    name: str
    dataset_type: str
    description: str | None
    total_items: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetItemResponse(BaseModel):
    id: int
    dataset_id: int
    item_index: int
    prompt: str
    reference_answer: str | None
    metadata: dict = {}

    model_config = ConfigDict(from_attributes=True)
