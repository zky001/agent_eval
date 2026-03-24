from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_item_id = Column(Integer, ForeignKey("dataset_items.id"), nullable=False)
    status = Column(String, default="pending", nullable=False)
    dispatched_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    run = relationship("EvaluationRun", back_populates="tasks")
    dataset_item = relationship("DatasetItem", back_populates="tasks")
    result = relationship("Result", back_populates="task", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "dataset_item_id", name="uq_run_dataset_item"),
    )
