# app/api/routes/provider_dashboard.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime
from typing import List, Optional

from app.db.base import get_db
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.review import Review
from app.db.models.user import User
from app.db.models.availability import ProviderAvailability
from app.schemas.provider_dashboard import (
    SummaryResponse,
    EarningsResponse,
    EarningsBreakdownItem,
    BookingsStatsResponse,
    ReviewsResponse,
    ReviewMini,
    ActivityResponse,
    TopServiceItem,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/provider/dashboard", tags=["provider-dashboard"])


# --------------------------
# 1) /provider/dashboard/summary
# --------------------------
@router.get("/summary", response_model=SummaryResponse)
def provider_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    provider_id = current_user.id

    # Total bookings
    total_bookings = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id).scalar() or 0

    # By status
    completed = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "completed").scalar() or 0
    pending = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "pending").scalar() or 0
    cancelled = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "canceled").scalar() or 0
    rejected = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "rejected").scalar() or 0

    # Earnings - sum only completed bookings
    total_earnings = db.query(func.coalesce(func.sum(Booking.amount), 0)).filter(
        Booking.provider_id == provider_id, Booking.status == "completed"
    ).scalar() or 0.0

    # Current month earnings (local server month)
    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year
    current_month_earnings = db.query(func.coalesce(func.sum(Booking.amount), 0)).filter(
        Booking.provider_id == provider_id,
        Booking.status == "completed",
        func.extract("month", Booking.created_at) == current_month,
        func.extract("year", Booking.created_at) == current_year
    ).scalar() or 0.0

    # Average rating from reviews table
    avg_rating = db.query(func.avg(Review.rating)).filter(Review.provider_id == provider_id).scalar()
    avg_rating = float(avg_rating) if avg_rating is not None else None

    # Top service by number of bookings
    top_q = (
        db.query(Booking.service_id, func.count(Booking.id).label("cnt"))
        .filter(Booking.provider_id == provider_id)
        .group_by(Booking.service_id)
        .order_by(desc("cnt"))
        .limit(1)
        .all()
    )
    top_service = None
    if top_q:
        svc_id, cnt = top_q[0]
        svc = db.query(Service).filter(Service.id == svc_id).first()
        if svc:
            top_service = TopServiceItem(service_id=svc.id, service_name=svc.name, count=int(cnt))

    return SummaryResponse(
        total_bookings=int(total_bookings),
        completed=int(completed),
        pending=int(pending),
        cancelled=int(cancelled),
        rejected=int(rejected),
        total_earnings=float(total_earnings),
        current_month_earnings=float(current_month_earnings),
        average_rating=avg_rating,
        top_service=top_service,
    )


# --------------------------
# 2) /provider/dashboard/earnings?month=&year=
# --------------------------
@router.get("/earnings", response_model=EarningsResponse)
def provider_earnings(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    provider_id = current_user.id
    now = datetime.utcnow()
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    # Total earnings and completed bookings for the month
    total_earnings = db.query(func.coalesce(func.sum(Booking.amount), 0)).filter(
        Booking.provider_id == provider_id,
        Booking.status == "completed",
        func.extract("month", Booking.created_at) == month,
        func.extract("year", Booking.created_at) == year,
    ).scalar() or 0.0

    completed_bookings = db.query(func.count(Booking.id)).filter(
        Booking.provider_id == provider_id,
        Booking.status == "completed",
        func.extract("month", Booking.created_at) == month,
        func.extract("year", Booking.created_at) == year,
    ).scalar() or 0

    # Breakdown by service
    rows = (
        db.query(Service.name, func.count(Booking.id).label("cnt"), func.coalesce(func.sum(Booking.amount), 0).label("value"))
        .join(Booking, Booking.service_id == Service.id)
        .filter(
            Booking.provider_id == provider_id,
            Booking.status == "completed",
            func.extract("month", Booking.created_at) == month,
            func.extract("year", Booking.created_at) == year,
        )
        .group_by(Service.name)
        .order_by(desc("value"))
        .all()
    )

    breakdown = [EarningsBreakdownItem(service_name=r[0], count=int(r[1]), value=float(r[2] or 0.0)) for r in rows]

    return EarningsResponse(
        provider_id=provider_id,
        month=month,
        year=year,
        total_earnings=float(total_earnings),
        completed_bookings=int(completed_bookings),
        breakdown=breakdown,
    )


# --------------------------
# 3) /provider/dashboard/bookings/stats
# --------------------------
@router.get("/bookings/stats", response_model=BookingsStatsResponse)
def provider_bookings_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    provider_id = current_user.id
    total = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id).scalar() or 0
    completed = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "completed").scalar() or 0
    pending = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "pending").scalar() or 0
    cancelled = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "canceled").scalar() or 0
    rejected = db.query(func.count(Booking.id)).filter(Booking.provider_id == provider_id, Booking.status == "rejected").scalar() or 0

    completion_rate = f"{(completed / total * 100):.1f}%" if total > 0 else "0.0%"

    return BookingsStatsResponse(
        total=int(total),
        completed=int(completed),
        pending=int(pending),
        cancelled=int(cancelled),
        rejected=int(rejected),
        completion_rate=completion_rate,
    )


# --------------------------
# 4) /provider/dashboard/reviews
# --------------------------
@router.get("/reviews", response_model=ReviewsResponse)
def provider_reviews(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    provider_id = current_user.id
    avg_rating = db.query(func.avg(Review.rating)).filter(Review.provider_id == provider_id).scalar()
    avg_rating = float(avg_rating) if avg_rating is not None else None

    rows = db.query(Review).filter(Review.provider_id == provider_id).order_by(Review.created_at.desc()).limit(limit).all()

    reviews = []
    for r in rows:
        # try to fetch customer name if present
        try:
            customer_name = r.customer.name
        except Exception:
            customer_name = None
        reviews.append(ReviewMini(id=r.id, rating=r.rating, comment=r.comment, customer_name=customer_name, created_at=r.created_at))

    return ReviewsResponse(average_rating=avg_rating, reviews=reviews)


# --------------------------
# 5) /provider/dashboard/activity
# --------------------------
@router.get("/activity", response_model=ActivityResponse)
def provider_activity(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Providers only")

    provider_id = current_user.id

    # last booking created_at
    last_booking = db.query(Booking).filter(Booking.provider_id == provider_id).order_by(Booking.created_at.desc()).first()
    last_booking_date = last_booking.created_at if last_booking else None

    # last service added - best-effort if Service has created_at
    last_service = None
    try:
        last_service = db.query(Service).filter(Service.provider_id == provider_id).order_by(Service.created_at.desc()).first()
        last_service_added = last_service.created_at if last_service else None
    except Exception:
        last_service_added = None

    # availability strength - percent of weekdays with at least one active availability window
    total_weekdays = 7
    active_days = db.query(func.count(func.distinct(ProviderAvailability.weekday))).filter(
        ProviderAvailability.provider_id == provider_id, ProviderAvailability.is_active == True
    ).scalar() or 0
    availability_strength = (int(active_days) / total_weekdays) * 100

    # profile completion - heuristic: check some fields on user and services and categories
    profile_score = 0
    checks = 0
    # field checks
    for attr in ("name", "phone", "address", "description"):
        checks += 1
        if getattr(current_user, attr, None):
            profile_score += 1

    # services count check
    svc_count = db.query(func.count(Service.id)).filter(Service.provider_id == provider_id).scalar() or 0
    checks += 1
    if svc_count > 0:
        profile_score += 1

    # categories (many-to-many) count
    # best effort: if relationship exists
    cat_count = 0
    try:
        cat_count = len(current_user.categories or [])
    except Exception:
        cat_count = 0
    checks += 1
    if cat_count > 0:
        profile_score += 1

    profile_completion = int((profile_score / checks) * 100) if checks > 0 else 0

    return ActivityResponse(
        last_booking_date=last_booking_date,
        last_service_added=last_service_added,
        availability_strength=float(round(availability_strength, 2)),
        profile_completion=int(profile_completion),
    )
