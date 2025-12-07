# app/schemas/admin_dashboard.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class KPIItem(BaseModel):
    total_users: int
    total_providers: int
    total_services: int
    total_bookings: int
    bookings_today: int
    bookings_last_7_days: int

    class Config:
        from_attributes = True

class ProviderEarningsItem(BaseModel):
    provider_id: int
    provider_name: Optional[str]
    total_earnings: float
    completed_bookings: int

    class Config:
        from_attributes = True

class CategoryEarningsItem(BaseModel):
    category_id: int
    category_name: Optional[str]
    total_earnings: float

    class Config:
        from_attributes = True

class TrendPoint(BaseModel):
    date: datetime
    bookings: int
    earnings: float

    class Config:
        from_attributes = True

class AdminDashboardResponse(BaseModel):
    kpis: KPIItem
    bookings_by_status: dict
    top_providers_by_earnings: List[ProviderEarningsItem]
    earnings_by_category: List[CategoryEarningsItem]
    bookings_trend_last_30_days: List[TrendPoint]

    class Config:
        from_attributes = True
