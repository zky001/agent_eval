from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False)
    raw_response = Column(Text, nullable=True)
    parsed_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    evaluation_details = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="result")
