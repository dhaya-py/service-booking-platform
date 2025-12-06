# app/schemas/admin.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserListItem(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    is_provider_approved: Optional[bool] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ServiceListItem(BaseModel):
    id: int
    provider_id: int
    name: str
    price: float
    is_active: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class BookingAdminItem(BaseModel):
    id: int
    customer_id: int
    provider_id: int
    service_id: int
    amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardAdminResponse(BaseModel):
    total_users: int
    total_providers: int
    total_services: int
    total_bookings: int
    bookings_last_7_days: int

    class Config:
        from_attributes = True
