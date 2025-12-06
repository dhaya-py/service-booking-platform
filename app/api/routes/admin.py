# app/api/routes/admin.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta

from app.db.base import get_db
from app.db.models.user import User
from app.db.models.service import Service
from app.db.models.booking import Booking
from app.db.models.review import Review
from app.schemas.admin import (
    UserListItem,
    ServiceListItem,
    BookingAdminItem,
    DashboardAdminResponse,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: User):
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return True


# -------------------------
# 1. List users (filterable)
# -------------------------
@router.get("/users", response_model=List[UserListItem])
def list_users(
    role: Optional[str] = Query(None, description="customer/provider/admin"),
    active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if active is not None:
        q = q.filter(User.is_active == active)

    offset = (page - 1) * per_page
    users = q.order_by(User.id).offset(offset).limit(per_page).all()
    return users


# --------------------------------------------------
# 2. Activate / Deactivate a user (soft)
# --------------------------------------------------
@router.put("/users/{user_id}/activate")
def set_user_active(
    user_id: int,
    active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.is_active = bool(active)
    db.commit()
    db.refresh(u)
    return {"ok": True, "user_id": u.id, "is_active": u.is_active}


# --------------------------------------------------
# 3. Approve / Reject provider application
# --------------------------------------------------
@router.put("/providers/{provider_id}/approve")
def approve_provider(
    provider_id: int,
    approve: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    provider = db.query(User).filter(User.id == provider_id, User.role == "provider").first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_provider_approved = bool(approve)
    db.commit()
    db.refresh(provider)
    return {"ok": True, "provider_id": provider.id, "is_provider_approved": provider.is_provider_approved}


# --------------------------------------------------
# 4. List services (filterable) and enable/disable service
# --------------------------------------------------
@router.get("/services", response_model=List[ServiceListItem])
def list_services(
    provider_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    q = db.query(Service)
    if provider_id:
        q = q.filter(Service.provider_id == provider_id)
    if category_id:
        q = q.filter(Service.category_id == category_id)
    if active is not None:
        q = q.filter(Service.is_active == active)
    offset = (page - 1) * per_page
    return q.order_by(Service.id.desc()).offset(offset).limit(per_page).all()


@router.put("/services/{service_id}/toggle")
def toggle_service(
    service_id: int,
    active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    svc = db.query(Service).filter(Service.id == service_id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    svc.is_active = bool(active)
    db.commit()
    db.refresh(svc)
    return {"ok": True, "service_id": svc.id, "is_active": svc.is_active}


# --------------------------------------------------
# 5. Bookings: list & update status
# --------------------------------------------------
@router.get("/bookings", response_model=List[BookingAdminItem])
def admin_list_bookings(
    provider_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    q = db.query(Booking)
    if provider_id:
        q = q.filter(Booking.provider_id == provider_id)
    if customer_id:
        q = q.filter(Booking.customer_id == customer_id)
    if status:
        q = q.filter(Booking.status == status)
    if date_from:
        try:
            dtf = datetime.fromisoformat(date_from)
            q = q.filter(Booking.created_at >= dtf)
        except Exception:
            raise HTTPException(status_code=400, detail="date_from must be ISO datetime")
    if date_to:
        try:
            dtt = datetime.fromisoformat(date_to)
            q = q.filter(Booking.created_at <= dtt)
        except Exception:
            raise HTTPException(status_code=400, detail="date_to must be ISO datetime")

    offset = (page - 1) * per_page
    rows = q.order_by(Booking.created_at.desc()).offset(offset).limit(per_page).all()
    return rows


@router.put("/bookings/{booking_id}/status")
def admin_update_booking_status(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # optional: validate status is in a known set
    booking.status = status
    db.commit()
    db.refresh(booking)
    return {"ok": True, "booking_id": booking.id, "status": booking.status}


# --------------------------------------------------
# 6. Reviews moderation
# --------------------------------------------------
@router.delete("/reviews/{review_id}")
def admin_delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    # soft-delete or hard delete depending on your policy. We'll hard-delete for now:
    db.delete(r)
    db.commit()
    return {"ok": True, "deleted_review_id": review_id}


# --------------------------------------------------
# 7. Admin summary (platform KPIs)
# --------------------------------------------------
@router.get("/summary", response_model=DashboardAdminResponse)
def admin_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_providers = db.query(func.count(User.id)).filter(User.role == "provider").scalar() or 0
    total_services = db.query(func.count(Service.id)).scalar() or 0
    total_bookings = db.query(func.count(Booking.id)).scalar() or 0
    last_7 = datetime.utcnow() - timedelta(days=7)
    bookings_last_7 = db.query(func.count(Booking.id)).filter(Booking.created_at >= last_7).scalar() or 0
    return DashboardAdminResponse(
        total_users=int(total_users),
        total_providers=int(total_providers),
        total_services=int(total_services),
        total_bookings=int(total_bookings),
        bookings_last_7=int(bookings_last_7),
    )
