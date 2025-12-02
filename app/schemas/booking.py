from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import Optional

# --- CREATE ---
class BookingCreate(BaseModel):
    service_id: int
    provider_id: int
    booking_date: date
    booking_time: time
    address: str
    amount: float


# --- UPDATE (Provider or Admin) ---
class BookingUpdate(BaseModel):
    status: Optional[str] = Field(
        default=None,
        description="Allowed values: pending, accepted, rejected, completed, canceled"
    )


# --- RESPONSE ---
class BookingResponse(BaseModel):
    id: int
    customer_id: int
    provider_id: int
    service_id: int
    booking_date: date
    booking_time: time
    address: str
    amount: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
