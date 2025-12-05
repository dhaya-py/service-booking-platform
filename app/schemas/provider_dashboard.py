# app/schemas/provider_dashboard.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TopServiceItem(BaseModel):
    service_id: int
    service_name: str
    count: int

class SummaryResponse(BaseModel):
    total_bookings: int
    completed: int
    pending: int
    cancelled: int
    rejected: int
    total_earnings: float
    current_month_earnings: float
    average_rating: float | None
    top_service: Optional[TopServiceItem] = None

    class Config:
        from_attributes = True

class EarningsBreakdownItem(BaseModel):
    service_name: str
    count: int
    value: float

class EarningsResponse(BaseModel):
    provider_id: int
    month: int
    year: int
    total_earnings: float
    completed_bookings: int
    breakdown: List[EarningsBreakdownItem]

    class Config:
        from_attributes = True

class BookingsStatsResponse(BaseModel):
    total: int
    completed: int
    pending: int
    cancelled: int
    rejected: int
    completion_rate: str  # e.g. "89.4%"

    class Config:
        from_attributes = True

class ReviewMini(BaseModel):
    id: int
    rating: int
    comment: Optional[str]
    customer_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewsResponse(BaseModel):
    average_rating: float | None
    reviews: List[ReviewMini]

    class Config:
        from_attributes = True

class ActivityResponse(BaseModel):
    last_booking_date: Optional[datetime]
    last_service_added: Optional[datetime]
    availability_strength: float  # 0..100 percentage
    profile_completion: int  # 0..100 percent

    class Config:
        from_attributes = True
