# app/api/routes/availability.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta
from typing import List

from app.db.base import get_db
from app.db.models.user import User
from app.db.models.availability import ProviderAvailability, ProviderTimeOff
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.schemas.availability import (
    ProviderAvailabilityCreate,
    ProviderAvailabilityResponse,
    ProviderTimeOffCreate,
    ProviderTimeOffResponse,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/availability", tags=["availability"])



@router.post("/provider/weekly", response_model=ProviderAvailabilityResponse)
def add_weekly_availability(payload: ProviderAvailabilityCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can add availability")

    # validate start_time < end_time
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    avail = ProviderAvailability(
        provider_id=current_user.id,
        weekday=payload.weekday,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_active=payload.is_active
    )
    db.add(avail)
    db.commit()
    db.refresh(avail)
    return avail



@router.get("/provider/weekly", response_model=List[ProviderAvailabilityResponse])
def list_weekly_availability(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can view")
    return db.query(ProviderAvailability).filter(ProviderAvailability.provider_id == current_user.id).all()



@router.post("/provider/timeoff", response_model=ProviderTimeOffResponse)
def add_timeoff(payload: ProviderTimeOffCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can add time off")

    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    timeoff = ProviderTimeOff(
        provider_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        reason=payload.reason
    )
    db.add(timeoff)
    db.commit()
    db.refresh(timeoff)
    return timeoff



@router.get("/provider/timeoff", response_model=List[ProviderTimeOffResponse])
def list_timeoffs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can view")
    return db.query(ProviderTimeOff).filter(ProviderTimeOff.provider_id == current_user.id).all()



# Slot generation + conflict detection (core logic)


def overlaps(start1, end1, start2, end2):
    return max(start1, start2) < min(end1, end2)

def get_provider_bookings_on_date(db: Session, provider_id: int, dt: date):
    # returns list of (start_datetime, end_datetime)
    rows = db.query(Booking).filter(Booking.provider_id == provider_id, Booking.booking_date == dt).all()
    result = []
    for r in rows:
        svc = db.query(Service).filter(Service.id == r.service_id).first()
        duration = svc.duration_minutes if svc else 60
        start_dt = datetime.combine(r.booking_date, r.booking_time)
        end_dt = start_dt + timedelta(minutes=duration)
        result.append((start_dt, end_dt))
    return result

def is_blocked_by_timeoff(db: Session, provider_id: int, slot_start_dt: datetime, slot_end_dt: datetime):
    # find any timeoff that overlaps this slot
    timeoffs = db.query(ProviderTimeOff).filter(ProviderTimeOff.provider_id == provider_id).all()
    for t in timeoffs:
        # for each date in the timeoff date range, build blocked start/end datetimes
        cur = t.start_date
        while cur <= t.end_date:
            # compute block start/end datetimes for that day
            if t.start_time and t.end_time:
                block_start = datetime.combine(cur, t.start_time)
                block_end = datetime.combine(cur, t.end_time)
            else:
                # full day block
                block_start = datetime.combine(cur, time.min)
                block_end = datetime.combine(cur, time.max)
            if overlaps(block_start, block_end, slot_start_dt, slot_end_dt):
                return True
            cur = cur + timedelta(days=1)
    return False



@router.get("/provider/{provider_id}/slots", response_model=List[str])
def get_available_slots_for_date(
    provider_id: int,
    service_id: int = Query(..., description="service id to determine duration"),
    date_str: str = Query(..., description="date in YYYY-MM-DD"),
    interval_minutes: int = Query(30, description="slot step in minutes"),
    db: Session = Depends(get_db),
):
    """
    Returns available slot start times (ISO strings) for provider on given date.
    Steps:
      - find weekday availabilities for that weekday
      - for each availability window, generate slots using interval_minutes
      - for each slot ensure it doesn't overlap existing bookings or timeoffs
      - ensure slot + service.duration fits inside the availability window
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    duration = service.duration_minutes

    weekday = target_date.weekday() + 1 # 0..6
    avail_windows = db.query(ProviderAvailability).filter(
        ProviderAvailability.provider_id == provider_id,
        ProviderAvailability.weekday == weekday,
        ProviderAvailability.is_active == True
    ).all()

    slots = []
    # existing bookings and timeoffs for date
    existing_bookings = get_provider_bookings_on_date(db, provider_id, target_date)

    for w in avail_windows:
        # window start/end as datetimes on target_date
        window_start = datetime.combine(target_date, w.start_time)
        window_end = datetime.combine(target_date, w.end_time)

        # generate slots starting at window_start, stepping by interval_minutes
        slot_start = window_start
        while slot_start + timedelta(minutes=duration) <= window_end:
            slot_end = slot_start + timedelta(minutes=duration)
            # check overlap with bookings
            conflict = False
            for b_start, b_end in existing_bookings:
                if overlaps(b_start, b_end, slot_start, slot_end):
                    conflict = True
                    break
            if conflict:
                slot_start += timedelta(minutes=interval_minutes)
                continue

            # check timeoffs
            if is_blocked_by_timeoff(db, provider_id, slot_start, slot_end):
                slot_start += timedelta(minutes=interval_minutes)
                continue

            # slot available
            slots.append(slot_start.isoformat())
            slot_start += timedelta(minutes=interval_minutes)

    return slots
