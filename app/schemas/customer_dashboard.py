# app/schemas/customer_dashboard.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date

class BookingMini(BaseModel):
    id: int
    service_id: int
    service_name: Optional[str]
    provider_id: int
    provider_name: Optional[str]
    booking_date: date
    booking_time: Optional[str]
    amount: float
    status: str

    class Config:
        from_attributes = True

class RecommendationItem(BaseModel):
    service_id: int
    service_name: str
    provider_id: int
    provider_name: Optional[str]
    price: float
    avg_rating: Optional[float]

    class Config:
        from_attributes = True

class SpendingPoint(BaseModel):
    month: str
    year: int
    total_spent: float

class CustomerOverview(BaseModel):
    total_bookings: int
    completed: int
    canceled: int
    pending: int
    total_spent: float
    avg_rating_given: Optional[float]

    class Config:
        from_attributes = True

class CustomerDashboardResponse(BaseModel):
    overview: CustomerOverview
    upcoming: List[BookingMini]
    past: List[BookingMini]
    recommendations: List[RecommendationItem]
    spending_summary: List[SpendingPoint]

    class Config:
        from_attributes = True
