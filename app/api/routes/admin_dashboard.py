# app/api/routes/admin_dashboard.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, date
from typing import List, Dict

from app.db.base import get_db
from app.db.models.user import User
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.category import Category
from app.db.models.review import Review
from app.schemas.admin_dashboard import (
    AdminDashboardResponse,
    KPIItem,
    ProviderEarningsItem,
    CategoryEarningsItem,
    TrendPoint,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def require_admin(current_user: User):
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return True


@router.get("", response_model=AdminDashboardResponse)
def admin_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    now = datetime.utcnow()
    today = now.date()
    last_30 = now - timedelta(days=30)
    last_7 = now - timedelta(days=7)

    # KPIs
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_providers = db.query(func.count(User.id)).filter(User.role == "provider").scalar() or 0
    total_services = db.query(func.count(Service.id)).scalar() or 0
    total_bookings = db.query(func.count(Booking.id)).scalar() or 0
    bookings_today = db.query(func.count(Booking.id)).filter(func.date(Booking.created_at) == today).scalar() or 0
    bookings_last_7_days = db.query(func.count(Booking.id)).filter(Booking.created_at >= last_7).scalar() or 0

    kpis = KPIItem(
        total_users=int(total_users),
        total_providers=int(total_providers),
        total_services=int(total_services),
        total_bookings=int(total_bookings),
        bookings_today=int(bookings_today),
        bookings_last_7_days=int(bookings_last_7_days),
    )

    # bookings by status
    status_counts_q = db.query(Booking.status, func.count(Booking.id)).group_by(Booking.status).all()
    bookings_by_status = {row[0]: int(row[1]) for row in status_counts_q}

    # top providers by earnings (completed bookings)
    prov_rows = (
        db.query(
            Booking.provider_id,
            func.coalesce(func.sum(Booking.amount), 0).label("sum_earn"),
            func.count(func.nullif(Booking.status != "completed", True)).label("completed_count")
        )
        .filter(Booking.status == "completed")
        .group_by(Booking.provider_id)
        .order_by(desc("sum_earn"))
        .limit(10)
        .all()
    )
    top_providers = []
    for provider_id, sum_earn, completed_count in prov_rows:
        prov = db.query(User).filter(User.id == provider_id).first()
        top_providers.append(ProviderEarningsItem(
            provider_id=int(provider_id),
            provider_name=prov.name if prov else None,
            total_earnings=float(sum_earn or 0.0),
            completed_bookings=int(completed_count or 0),
        ))

    # earnings by category
    cat_rows = (
        db.query(
            Service.category_id,
            func.coalesce(func.sum(Booking.amount), 0).label("sum_earn")
        )
        .join(Booking, Booking.service_id == Service.id)
        .filter(Booking.status == "completed")
        .group_by(Service.category_id)
        .order_by(desc("sum_earn"))
        .limit(20)
        .all()
    )
    earnings_by_category = []
    for cat_id, sum_earn in cat_rows:
        cat = db.query(Category).filter(Category.id == cat_id).first()
        earnings_by_category.append(CategoryEarningsItem(
            category_id=int(cat_id),
            category_name=cat.name if cat else None,
            total_earnings=float(sum_earn or 0.0),
        ))

    # bookings & earnings trend last 30 days
    trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        day_start = datetime.combine(d, datetime.min.time())
        day_end = datetime.combine(d, datetime.max.time())
        bookings_count = db.query(func.count(Booking.id)).filter(Booking.created_at >= day_start, Booking.created_at <= day_end).scalar() or 0
        earnings_sum = db.query(func.coalesce(func.sum(Booking.amount), 0)).filter(Booking.status == "completed", Booking.created_at >= day_start, Booking.created_at <= day_end).scalar() or 0.0
        trend.append(TrendPoint(date=day_start, bookings=int(bookings_count), earnings=float(earnings_sum)))

    return AdminDashboardResponse(
        kpis=kpis,
        bookings_by_status=bookings_by_status,
        top_providers_by_earnings=top_providers,
        earnings_by_category=earnings_by_category,
        bookings_trend_last_30_days=trend,
    )
