# app/db/models/availability.py
from sqlalchemy import Column, Integer, Time, Date, ForeignKey, Boolean, DateTime, String, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ProviderAvailability(Base):
    """
    Recurring weekly availability for a provider.
    weekday: 0 (Monday) .. 6 (Sunday)
    start_time, end_time: times (HH:MM:SS)
    """
    __tablename__ = "provider_availabilities"
    __table_args__ = (
        CheckConstraint('weekday BETWEEN 1 AND 7'),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weekday = Column(Integer, nullable=False)   # store 1–7
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)

    provider = relationship("User", back_populates="availabilities")


class ProviderTimeOff(Base):
    """
    One-off time off or block for a provider.
    Use for vacations, breaks, special blocks.
    start_date/start_time and end_date/end_time define the blocked window.
    If you want whole-day time off, set start_time/end_time to NULL or 00:00/23:59.
    """
    __tablename__ = "provider_timeoffs"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)  # optional for whole day
    end_time = Column(Time, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    provider = relationship("User", back_populates="timeoffs")
