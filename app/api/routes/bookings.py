from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.base import get_db
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse
from app.core.security import get_current_user

from datetime import datetime, timedelta
from app.db.models.availability import ProviderAvailability, ProviderTimeOff
from app.api.routes.availability import is_blocked_by_timeoff, overlaps, get_provider_bookings_on_date, is_blocked_by_timeoff

router = APIRouter(prefix="/bookings", tags=["bookings"])

# Customer creates booking

@router.post("/customer", response_model=BookingResponse)
def create_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Step 1: Only customers allowed
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can create bookings")

    # Step 2: Validate service exists
    service = db.query(Service).filter(Service.id == booking.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Step 3: Validate provider exists & is provider
    provider = db.query(User).filter(
        User.id == booking.provider_id, User.role == "provider"
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")


    # inside create_booking, after validating service and provider:

    weekday = booking.booking_date.weekday() + 1

    # validate requested slot against availability/duration/conflicts
    requested_start = datetime.combine(booking.booking_date, booking.booking_time)
    requested_end = requested_start + timedelta(minutes=service.duration_minutes)

    # 1) check provider has weekly availability that contains this slot
    
    avail_windows = db.query(ProviderAvailability).filter(
        ProviderAvailability.provider_id == booking.provider_id,
        ProviderAvailability.weekday == weekday,
        ProviderAvailability.is_active == True
    ).all()
    if not avail_windows:
        raise HTTPException(status_code=400, detail="Provider has no availability on this day")

    # ensure at least one window fully contains the requested slot
    ok_window = False
    for w in avail_windows:
        window_start = datetime.combine(booking.booking_date, w.start_time)
        window_end = datetime.combine(booking.booking_date, w.end_time)
        if requested_start >= window_start and requested_end <= window_end:
            ok_window = True
            break
    if not ok_window:
        raise HTTPException(status_code=400, detail="Requested time is outside provider availability")

    # 2) check conflict with existing bookings
    existing = get_provider_bookings_on_date(db, booking.provider_id, booking.booking_date)
    for b_start, b_end in existing:
        if overlaps(b_start, b_end, requested_start, requested_end):
            raise HTTPException(status_code=400, detail="Requested time overlaps an existing booking")

    # 3) check provider timeoffs
    if is_blocked_by_timeoff(db, booking.provider_id, requested_start, requested_end):
        raise HTTPException(status_code=400, detail="Requested time falls during provider time off")


    # Step 4: Create booking
    new_booking = Booking(
        customer_id=current_user.id,
        provider_id=booking.provider_id,
        service_id=booking.service_id,
        booking_date=booking.booking_date,
        booking_time=booking.booking_time,
        address=booking.address,
        amount=booking.amount,
        status="pending",
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return new_booking



# Customer cancels booking

@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Customers only")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    # Rule 1: Only pending bookings can be canceled
    if booking.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel booking because it is already {booking.status}",
        )

    booking.status = "canceled"

    db.commit()
    db.refresh(booking)

    return booking



# Customer views their bookings

@router.get("/customer/me", response_model=list[BookingResponse])
def customer_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Customers only")

    bookings = db.query(Booking).filter(
        Booking.customer_id == current_user.id
    ).order_by(Booking.created_at.desc()).all()

    return bookings



# Provider views their bookings

@router.get("/provider/me", response_model=list[BookingResponse])
def provider_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can view this")

    bookings = db.query(Booking).filter(
        Booking.provider_id == current_user.id
    ).order_by(Booking.created_at.desc()).all()

    return bookings


# Provider accepts booking

@router.post("/{booking_id}/accept", response_model=BookingResponse)
def accept_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="Booking already handled")

    booking.status = "accepted"
    db.commit()
    db.refresh(booking)
    return booking


# Provider rejects booking


@router.post("/{booking_id}/reject", response_model=BookingResponse)
def reject_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="Booking already handled")

    booking.status = "rejected"
    db.commit()
    db.refresh(booking)
    return booking


# Provider completes booking

@router.post("/{booking_id}/complete", response_model=BookingResponse)
def complete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking.status != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted bookings can be completed")

    booking.status = "completed"
    db.commit()
    db.refresh(booking)
    return booking




# Admin views all bookings

@router.get("/admin/all", response_model=list[BookingResponse])
def admin_all_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    bookings = db.query(Booking).order_by(Booking.created_at.desc()).all()

    return bookings
