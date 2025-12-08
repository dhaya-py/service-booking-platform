# app/api/routes/customer_dashboard_advanced.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List

from app.db.base import get_db
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.user import User
from app.db.models.category import Category
from app.schemas.customer_dashboard_advanced import (
    CustomerAdvancedResponse,
    RecentProviderItem,
    CategoryInterestItem,
    RepeatProviderItem,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/customer/dashboard/advanced", tags=["customer-dashboard-advanced"])

@router.get("", response_model=CustomerAdvancedResponse)
def customer_dashboard_advanced(limit_recent: int = Query(6, ge=1, le=20), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user or current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Customers only")
    cid = current_user.id
    now = datetime.utcnow().date()

    # 1) recent providers — last 6 providers customer interacted with (by booking date)
    recent_rows = (
        db.query(Booking.provider_id, func.max(Booking.created_at).label('last_date'))
        .filter(Booking.customer_id == cid)
        .group_by(Booking.provider_id)
        .order_by(desc('last_date'))
        .limit(limit_recent)
        .all()
    )
    recent_providers = []
    for prov_id, last_date in recent_rows:
        prov = db.query(User).filter(User.id == prov_id).first()
        recent_providers.append(RecentProviderItem(provider_id=int(prov_id), provider_name=prov.name if prov else None, last_booking_date=str(last_date.date()) if last_date else None, avg_rating=float(getattr(prov,'avg_rating',0) or 0)))

    # 2) category interest - categories user booked most in last 180 days
    six_months = datetime.utcnow().date() - timedelta(days=180)
    cat_rows = (
        db.query(Service.category_id, func.count(Booking.id).label('cnt'))
        .join(Booking, Booking.service_id == Service.id)
        .filter(Booking.customer_id == cid, Booking.booking_date >= six_months)
        .group_by(Service.category_id)
        .order_by(desc('cnt'))
        .limit(6)
        .all()
    )
    category_interest = []
    for cat_id, cnt in cat_rows:
        cat = db.query(Category).filter(Category.id == cat_id).first()
        category_interest.append(CategoryInterestItem(category_id=int(cat_id), category_name=cat.name if cat else None, bookings_count=int(cnt)))

    # 3) repeat providers - providers booked more than once by this customer
    repeat_rows = (
        db.query(Booking.provider_id, func.count(Booking.id).label('times'))
        .filter(Booking.customer_id == cid)
        .group_by(Booking.provider_id)
        .having(func.count(Booking.id) > 1)
        .order_by(desc('times'))
        .all()
    )
    repeat_providers = []
    for prov_id, times in repeat_rows:
        prov = db.query(User).filter(User.id == prov_id).first()
        repeat_providers.append(RepeatProviderItem(provider_id=int(prov_id), provider_name=prov.name if prov else None, times_booked=int(times)))

    # 4) simple "book again" suggestions - services the user used previously but not in last 30 days (encourage repeat)
    last_30 = datetime.utcnow().date() - timedelta(days=30)
    prev_services = (
        db.query(Booking.service_id, func.count(Booking.id).label('cnt'))
        .filter(Booking.customer_id == cid)
        .group_by(Booking.service_id)
        .order_by(desc('cnt'))
        .limit(10)
        .all()
    )
    suggestions = []
    for svc_id, cnt in prev_services:
        # check last booking date for this service
        last_booking = db.query(func.max(Booking.booking_date)).filter(Booking.customer_id == cid, Booking.service_id == svc_id).scalar()
        if not last_booking or last_booking < last_30:
            suggestions.append(int(svc_id))
    # keep unique and limit
    suggestions = suggestions[:6]

    return CustomerAdvancedResponse(
        recent_providers=recent_providers,
        category_interest=category_interest,
        repeat_providers=repeat_providers,
        book_again_suggestions=suggestions
    )
