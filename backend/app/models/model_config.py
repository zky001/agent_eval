from sqlalchemy import Column, DateTime, Integer, String, Text

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
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
