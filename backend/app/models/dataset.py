from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    dataset_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source_path = Column(String, nullable=True)
    total_items = Column(Integer, default=0)
    metadata_ = Column("metadata_", Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("DatasetItem", back_populates="dataset", cascade="all, delete-orphan")
    evaluation_runs = relationship("EvaluationRun", back_populates="dataset")


class DatasetItem(Base):
    __tablename__ = "dataset_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    item_index = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    reference_answer = Column(Text, nullable=True)
    metadata_ = Column("metadata_", Text, default="{}")

    dataset = relationship("Dataset", back_populates="items")
    tasks = relationship("Task", back_populates="dataset_item")

    __table_args__ = (
        UniqueConstraint("dataset_id", "item_index", name="uq_dataset_item_index"),
    )
