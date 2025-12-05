# app/schemas/search.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SimpleCategory(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class SimpleProvider(BaseModel):
    id: int
    name: str
    email: Optional[str]
    avg_rating: Optional[float] = None

    class Config:
        from_attributes = True

class ServiceSearchItem(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    discount_price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: bool
    category: Optional[SimpleCategory]
    provider: Optional[SimpleProvider]
    bookings_count: int = 0

    class Config:
        from_attributes = True

class SearchResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[ServiceSearchItem]
    