from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import utcnow


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)
    model_config_id = Column(Integer, ForeignKey("model_configs.id"), nullable=False, index=True)
    judge_model_config_id = Column(Integer, ForeignKey("model_configs.id"), nullable=True)
    status = Column(String, default="pending", nullable=False, index=True)
    params_override = Column(Text, default="{}")
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    aggregate_score = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    error_message = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="evaluation_runs")
    # Two FKs point at model_configs (candidate + judge); the join must be explicit
    model_config = relationship("ModelConfig", foreign_keys=[model_config_id])
    judge_model_config = relationship("ModelConfig", foreign_keys=[judge_model_config_id])
    tasks = relationship("Task", back_populates="run", cascade="all, delete-orphan")
