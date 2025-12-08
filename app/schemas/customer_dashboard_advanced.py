# app/schemas/customer_dashboard_advanced.py
from pydantic import BaseModel
from typing import List, Optional

class RecentProviderItem(BaseModel):
    provider_id: int
    provider_name: Optional[str]
    last_booking_date: Optional[str]
    avg_rating: Optional[float]

class CategoryInterestItem(BaseModel):
    category_id: int
    category_name: Optional[str]
    bookings_count: int

class RepeatProviderItem(BaseModel):
    provider_id: int
    provider_name: Optional[str]
    times_booked: int

class CustomerAdvancedResponse(BaseModel):
    recent_providers: List[RecentProviderItem]
    category_interest: List[CategoryInterestItem]
    repeat_providers: List[RepeatProviderItem]
    book_again_suggestions: List[int]  # service_id list (simple)
