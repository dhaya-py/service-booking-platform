# app/schemas/review.py
from pydantic import BaseModel, Field, conint
from typing import Optional
from datetime import datetime

class ReviewCreate(BaseModel):
    booking_id: int
    rating: conint(ge=1, le=5) = Field(..., description="Rating 1-5")
    comment: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    booking_id: int
    customer_id: int
    provider_id: int
    rating: int
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
