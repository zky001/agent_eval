from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base
from app.utils import utcnow


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)
    api_base_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    model_id = Column(String, nullable=False)
    default_params = Column(Text, default="{}")
    # USD per 1M tokens; None = cost tracking disabled for this model
    input_price_per_million = Column(Float, nullable=True)
    output_price_per_million = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
