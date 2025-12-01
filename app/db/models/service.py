# app/db/models/service.py

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean, Float, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))

    # Basic details
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Pricing
    price = Column(Float, nullable=False)
    discount_price = Column(Float, nullable=True)  # OPTIONAL

    # Duration (in minutes)
    duration_minutes = Column(Integer, nullable=False, default=60)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    provider = relationship("User", back_populates="services")
    category = relationship("Category", back_populates="services")
