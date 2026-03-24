from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    model_config_id = Column(Integer, ForeignKey("model_configs.id"), nullable=False)
    status = Column(String, default="pending", nullable=False)
    params_override = Column(Text, default="{}")
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    aggregate_score = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="evaluation_runs")
    model_config = relationship("ModelConfig")
    tasks = relationship("Task", back_populates="run", cascade="all, delete-orphan")
