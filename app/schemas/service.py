# app/schemas/service.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.schemas.category import CategoryMiniResponse
from app.schemas.user import UserResponse


# Shared fields
class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    discount_price: Optional[float] = None
    duration_minutes: int
    is_active: Optional[bool] = True


# Provider creates service
class ServiceCreate(ServiceBase):
    category_id: int


# Provider updates service
class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    category_id: Optional[int] = None


# What API returns
class ServiceResponse(BaseModel):
    id: int

    name: str
    description: Optional[str]
    price: float
    discount_price: Optional[float]
    duration_minutes: int
    is_active: bool

    category: CategoryMiniResponse
    provider: UserResponse

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
