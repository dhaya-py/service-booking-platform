# app/schemas/availability.py
from pydantic import BaseModel, Field, conint
from typing import Optional
from datetime import time, date, datetime

class ProviderAvailabilityCreate(BaseModel):
    weekday: conint(ge=1, le=7) = Field(..., description="1=Mon, 2=Tue, …, 7=Sun")
    start_time: time
    end_time: time
    is_active: Optional[bool] = True

class ProviderAvailabilityResponse(ProviderAvailabilityCreate):
    id: int
    provider_id: int

    class Config:
        from_attributes = True

class ProviderTimeOffCreate(BaseModel):
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = None

class ProviderTimeOffResponse(ProviderTimeOffCreate):
    id: int
    provider_id: int
    created_at: datetime

    class Config:
        from_attributes = True
