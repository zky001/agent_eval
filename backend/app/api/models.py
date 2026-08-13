import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    ModelTestResponse,
)
from app.services.llm_clients import create_llm_client
from app.utils import utcnow

router = APIRouter(prefix="/models", tags=["models"])


def _mask_key(api_key: str) -> str:
    """Only expose the last 4 chars to confirm a key is set."""
    return "sk-..." + api_key[-4:] if len(api_key) > 4 else "****"


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

    return ModelConfigResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        api_base_url=model.api_base_url,
        api_key=_mask_key(model.api_key) if model.api_key else None,
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
        created_at=utcnow(),
        updated_at=utcnow(),
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

    # The API only ever returns a masked key, so an edit form may echo the
    # mask back. Treat empty/masked values as "keep the existing key" instead
    # of overwriting the real key with the mask.
    if "api_key" in update_data:
        new_key = update_data["api_key"]
        if not new_key or (model.api_key and new_key == _mask_key(model.api_key)):
            update_data.pop("api_key")

    for key, value in update_data.items():
        setattr(model, key, value)

    model.updated_at = utcnow()
    await db.flush()
    await db.refresh(model)
    return _model_to_response(model)


@router.delete("/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")

    run_count = (
        await db.execute(
            select(func.count(EvaluationRun.id)).where(
                EvaluationRun.model_config_id == model_id
            )
        )
    ).scalar() or 0
    if run_count:
        raise HTTPException(
            status_code=409,
            detail=f"Model is referenced by {run_count} evaluation run(s); delete those runs first",
        )

    await db.delete(model)
    return {"detail": "Model config deleted"}


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model config not found")

    client = None
    try:
        client = create_llm_client(model)
        response = await client.complete("Hello, respond with OK.", {"max_tokens": 32})
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
    finally:
        if client is not None:
            await client.aclose()
