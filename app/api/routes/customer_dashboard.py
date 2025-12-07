# app/api/routes/customer_dashboard.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, date, timedelta
from typing import List

from app.db.base import get_db
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.user import User
from app.db.models.review import Review
from app.db.models.category import Category
from app.schemas.customer_dashboard import (
    CustomerDashboardResponse,
    CustomerOverview,
    BookingMini,
    RecommendationItem,
    SpendingPoint,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/customer/dashboard", tags=["customer-dashboard"])


@router.get("", response_model=CustomerDashboardResponse)
def customer_dashboard(
    limit_recommend: int = Query(6, ge=1, le=20),
    months_spending: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user or current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Customers only")

    customer_id = current_user.id
    today = datetime.utcnow().date()

    # --- Overview ---
    total_bookings = db.query(func.count(Booking.id)).filter(Booking.customer_id == customer_id).scalar() or 0
    completed = db.query(func.count(Booking.id)).filter(Booking.customer_id == customer_id, Booking.status == "completed").scalar() or 0
    canceled = db.query(func.count(Booking.id)).filter(Booking.customer_id == customer_id, Booking.status == "canceled").scalar() or 0
    pending = db.query(func.count(Booking.id)).filter(Booking.customer_id == customer_id, Booking.status == "pending").scalar() or 0

    total_spent = db.query(func.coalesce(func.sum(Booking.amount), 0)).filter(
        Booking.customer_id == customer_id, Booking.status == "completed"
    ).scalar() or 0.0

    # average rating given by this customer (if Review.customer_id exists)
    try:
        avg_rating_given = db.query(func.avg(Review.rating)).filter(Review.customer_id == customer_id).scalar()
        avg_rating_given = float(avg_rating_given) if avg_rating_given is not None else None
    except Exception:
        avg_rating_given = None

    overview = CustomerOverview(
        total_bookings=int(total_bookings),
        completed=int(completed),
        canceled=int(canceled),
        pending=int(pending),
        total_spent=float(total_spent),
        avg_rating_given=avg_rating_given,
    )

    # --- Upcoming bookings (future) ---
    upcoming_rows = (
        db.query(Booking, Service, User)
        .join(Service, Booking.service_id == Service.id)
        .join(User, Booking.provider_id == User.id)
        .filter(Booking.customer_id == customer_id)
        .filter(Booking.status.in_(["pending", "accepted"]))  # pending or accepted
        .filter(Booking.booking_date >= today)
        .order_by(Booking.booking_date.asc(), Booking.booking_time.asc())
        .limit(10)
        .all()
    )

    upcoming = []
    for b, svc, prov in upcoming_rows:
        upcoming.append(
            BookingMini(
                id=b.id,
                service_id=svc.id,
                service_name=svc.name,
                provider_id=prov.id,
                provider_name=prov.name,
                booking_date=b.booking_date,
                booking_time=str(b.booking_time) if getattr(b, "booking_time", None) else None,
                amount=float(b.amount or 0.0),
                status=b.status,
            )
        )

    # --- Past bookings (limit 20) ---
    past_rows = (
        db.query(Booking, Service, User)
        .join(Service, Booking.service_id == Service.id)
        .join(User, Booking.provider_id == User.id)
        .filter(Booking.customer_id == customer_id)
        .filter(Booking.status.in_(["completed", "canceled", "rejected"]))
        .order_by(Booking.booking_date.desc(), Booking.created_at.desc())
        .limit(20)
        .all()
    )

    past = []
    for b, svc, prov in past_rows:
        past.append(
            BookingMini(
                id=b.id,
                service_id=svc.id,
                service_name=svc.name,
                provider_id=prov.id,
                provider_name=prov.name,
                booking_date=b.booking_date,
                booking_time=str(b.booking_time) if getattr(b, "booking_time", None) else None,
                amount=float(b.amount or 0.0),
                status=b.status,
            )
        )

    # --- Simple recommendations:
    # Strategy:
    # - find top categories customer booked in last 180 days; recommend top-rated services from those categories
    six_months_ago = today - timedelta(days=180)
    category_counts = (
        db.query(Service.category_id, func.count(Booking.id).label("cnt"))
        .join(Booking, Booking.service_id == Service.id)
        .filter(Booking.customer_id == customer_id, Booking.booking_date >= six_months_ago)
        .group_by(Service.category_id)
        .order_by(desc("cnt"))
        .limit(3)
        .all()
    )
    recs = []
    if category_counts:
        cat_ids = [r[0] for r in category_counts if r[0]]
        # pick top-rated services in those categories
        rows = (
            db.query(Service, User)
            .join(User, Service.provider_id == User.id)
            .filter(Service.category_id.in_(cat_ids), Service.is_active == True)
            .order_by(desc(func.coalesce(User.avg_rating, 0)), desc(Service.created_at))
            .limit(limit_recommend)
            .all()
        )
        for svc, prov in rows:
            recs.append(
                RecommendationItem(
                    service_id=svc.id,
                    service_name=svc.name,
                    provider_id=prov.id,
                    provider_name=prov.name,
                    price=float(svc.price or 0.0),
                    avg_rating=float(prov.avg_rating) if getattr(prov, "avg_rating", None) is not None else None,
                )
            )
    else:
        # fallback: top popular services overall
        rows = (
            db.query(Service, User, func.coalesce(func.count(Booking.id), 0).label("bookings_count"))
            .join(User, Service.provider_id == User.id)
            .outerjoin(Booking, Booking.service_id == Service.id)
            .filter(Service.is_active == True)
            .group_by(Service.id, User.id)
            .order_by(desc("bookings_count"), desc(func.coalesce(User.avg_rating, 0)))
            .limit(limit_recommend)
            .all()
        )
        for svc, prov, _cnt in rows:
            recs.append(
                RecommendationItem(
                    service_id=svc.id,
                    service_name=svc.name,
                    provider_id=prov.id,
                    provider_name=prov.name,
                    price=float(svc.price or 0.0),
                    avg_rating=float(prov.avg_rating) if getattr(prov, "avg_rating", None) is not None else None,
                )
            )

    # --- Spending summary (month wise last N months) ---
    spend_points = []
    for i in range(months_spending - 1, -1, -1):
        start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        # define month start and end
        month_start = start
        # approximate month end by next month first day - 1 second
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        total_spent_m = (
            db.query(func.coalesce(func.sum(Booking.amount), 0))
            .filter(
                Booking.customer_id == customer_id,
                Booking.status == "completed",
                Booking.created_at >= month_start,
                Booking.created_at < next_month,
            )
            .scalar()
            or 0.0
        )
        spend_points.append(SpendingPoint(month=month_start.strftime("%b"), year=month_start.year, total_spent=float(total_spent_m)))

    return CustomerDashboardResponse(
        overview=overview,
        upcoming=upcoming,
        past=past,
        recommendations=recs,
        spending_summary=spend_points,
    )
