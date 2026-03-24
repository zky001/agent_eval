import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.model_config import ModelConfig
from app.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    ModelTestResponse,
)
from app.services.llm_clients import create_llm_client

router = APIRouter(prefix="/models", tags=["models"])


def _model_to_response(model: ModelConfig) -> ModelConfigResponse:
    default_params = {}
    if model.default_params:
        if isinstance(model.default_params, str):
            try:
                default_params = json.loads(model.default_params)
            except (json.JSONDecodeError, TypeError):
                default_params = {}
        else:
            default_params = model.default_params
    # Mask API key — only expose last 4 chars to confirm one is set
    masked_key: str | None = None
    if model.api_key:
        masked_key = "sk-..." + model.api_key[-4:] if len(model.api_key) > 4 else "****"

    return ModelConfigResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        api_base_url=model.api_base_url,
        api_key=masked_key,
        model_id=model.model_id,
        default_params=default_params,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("/", response_model=list[ModelConfigResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.created_at.desc()))
    models = result.scalars().all()
    return [_model_to_response(m) for m in models]


@router.post("/", response_model=ModelConfigResponse)
async def create_model(config: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(ModelConfig).where(ModelConfig.name == config.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Model '{config.name}' already exists")

    model = ModelConfig(
        name=config.name,
        provider=config.provider,
        api_base_url=config.api_base_url,
        api_key=config.api_key,
        model_id=config.model_id,
        default_params=json.dumps(config.default_params),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return _model_to_response(model)


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")
    return _model_to_response(model)


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model(
    model_id: int,
    update: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")

    update_data = update.model_dump(exclude_unset=True)
    if "default_params" in update_data and update_data["default_params"] is not None:
        update_data["default_params"] = json.dumps(update_data["default_params"])

    for key, value in update_data.items():
        setattr(model, key, value)

    model.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(model)
    return _model_to_response(model)


@router.delete("/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")
    await db.delete(model)
    return {"detail": "Model config deleted"}


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")

    try:
        client = create_llm_client(model)
        response = await client.complete("Hello, respond with OK.", {})
        return ModelTestResponse(
            success=True,
            response=response.text,
            latency_ms=response.latency_ms,
        )
    except Exception as e:
        return ModelTestResponse(
            success=False,
            error=str(e),
        )
