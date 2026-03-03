from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base


class WeightUnit(str, enum.Enum):
    lbs = "lbs"
    kg = "kg"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    authentik_sub = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    weight_unit = Column(SAEnum(WeightUnit), default=WeightUnit.lbs, nullable=False)
    dark_mode = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    workout_logs = relationship("WorkoutLog", back_populates="user")
    personal_records = relationship("PersonalRecord", back_populates="user")
