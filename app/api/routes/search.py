# app/api/routes/search.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import Optional
from datetime import datetime

from app.db.base import get_db
from app.db.models.service import Service
from app.db.models.user import User
from app.db.models.category import Category
from app.db.models.booking import Booking
from app.db.models.availability import ProviderAvailability, ProviderTimeOff
from app.schemas.search import SearchResponse, ServiceSearchItem, SimpleCategory, SimpleProvider
from app.core.security import get_current_user  # if you want to allow auth-based adjustments, otherwise can be optional

router = APIRouter(prefix="/search", tags=["search"])


def overlaps(start1, end1, start2, end2):
    return max(start1, start2) < min(end1, end2)


def provider_has_availability_on_date(db: Session, provider_id: int, target_date: datetime.date) -> bool:
    """
    Simple availability check:
    - provider has at least one active ProviderAvailability row matching target_date weekday (1..7)
    - and provider does not have an all-day timeoff covering that date
    This is a *fast* pre-filter (not slot-level verification).
    """
    weekday = target_date.isoweekday()   # 1..7
    avail_count = db.query(func.count(ProviderAvailability.id)).filter(
        ProviderAvailability.provider_id == provider_id,
        ProviderAvailability.weekday == weekday,
        ProviderAvailability.is_active == True
    ).scalar() or 0
    if avail_count == 0:
        return False

    # check if there's a full-day timeoff covering that date (timeoff defined via start_date/end_date)
    toffs = db.query(ProviderTimeOff).filter(
        ProviderTimeOff.provider_id == provider_id,
        ProviderTimeOff.start_date <= target_date,
        ProviderTimeOff.end_date >= target_date
    ).all()
    # if any timeoff is full day (start_time and end_time are null) treat as blocked
    for t in toffs:
        if t.start_time is None and t.end_time is None:
            return False
    return True


@router.get("/services", response_model=SearchResponse)
def search_services(
    q: Optional[str] = Query(None, description="Search keywords (name + description)"),
    category_id: Optional[int] = Query(None),
    provider_id: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None, ge=0.0),
    max_price: Optional[float] = Query(None, ge=0.0),
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0),
    duration_max: Optional[int] = Query(None, ge=1),
    availability_date: Optional[str] = Query(None, description="YYYY-MM-DD — filter providers who have availability that date"),
    sort: Optional[str] = Query("relevance", description="relevance | price_asc | price_desc | rating_desc | popularity | newest"),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Search services with filters, sorting, and pagination.
    - `q` does a case-insensitive partial match on name & description (use FTS later)
    - `availability_date` is a fast pre-filter: provider has weekly availability on that weekday and no full-day timeoff
    """

    # Base query: services joined to provider and category, left join bookings for popularity
    # We will aggregate bookings_count and rely on provider.avg_rating column for rating sort/filter
    base = (
        db.query(
            Service,
            Category,
            User,  # provider
            func.coalesce(func.count(Booking.id), 0).label("bookings_count")
        )
        .join(User, Service.provider_id == User.id)
        .outerjoin(Category, Service.category_id == Category.id)
        .outerjoin(Booking, Booking.service_id == Service.id)
        .filter(Service.is_active == True)
        .group_by(Service.id, Category.id, User.id)
    )

    # Filters
    if q:
        # simple keyword search (ILIKE). Later replace with full-text.
        q_like = f"%{q.strip()}%"
        base = base.filter(
            (Service.name.ilike(q_like)) | (Service.description.ilike(q_like))
        )

    if category_id:
        base = base.filter(Service.category_id == category_id)

    if provider_id:
        base = base.filter(Service.provider_id == provider_id)

    if min_price is not None:
        base = base.filter(Service.price >= min_price)

    if max_price is not None:
        base = base.filter(Service.price <= max_price)

    if duration_max is not None:
        base = base.filter(Service.duration_minutes <= duration_max)

    if min_rating is not None:
        # prefer provider.avg_rating column; if not set, provider may have avg_rating null -> treat as 0
        base = base.filter(func.coalesce(User.avg_rating, 0) >= min_rating)

    # Availability filter (optional)
    if availability_date:
        try:
            target_date = datetime.strptime(availability_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="availability_date must be YYYY-MM-DD")

        # Get providers who have availability on that date (fast approach)
        subq = (
            db.query(ProviderAvailability.provider_id)
            .filter(ProviderAvailability.weekday == target_date.isoweekday(), ProviderAvailability.is_active == True)
            .distinct()
        ).subquery()

        base = base.filter(Service.provider_id.in_(subq))

        # Also filter out providers that have full-day timeoff for that date
        # (This is optional — heavy but useful)
        blocked_providers = (
            db.query(ProviderTimeOff.provider_id)
            .filter(ProviderTimeOff.start_date <= target_date, ProviderTimeOff.end_date >= target_date)
            .filter(ProviderTimeOff.start_time.is_(None), ProviderTimeOff.end_time.is_(None))
            .distinct()
            .subquery()
        )
        base = base.filter(~Service.provider_id.in_(blocked_providers))

    # Sorting
    if sort == "price_asc":
        base = base.order_by(asc(Service.price))
    elif sort == "price_desc":
        base = base.order_by(desc(Service.price))
    elif sort == "rating_desc":
        # using provider.avg_rating if available
        base = base.order_by(desc(func.coalesce(User.avg_rating, 0)))
    elif sort == "popularity":
        base = base.order_by(desc("bookings_count"))
    elif sort == "newest":
        base = base.order_by(desc(Service.created_at))
    else:
        # relevance = combination: name match first, then bookings_count, then rating
        # since we have simple ILIKE, just prefer bookings_count desc, rating desc
        base = base.order_by(desc("bookings_count"), desc(func.coalesce(User.avg_rating, 0)))

    # Pagination
    total = base.count()
    offset = (page - 1) * per_page
    rows = base.offset(offset).limit(per_page).all()

    items = []
    for svc, cat, prov, bookings_count in rows:
        category_obj = SimpleCategory(id=cat.id, name=cat.name) if cat else None
        provider_obj = SimpleProvider(id=prov.id, name=prov.name, email=prov.email, avg_rating=float(prov.avg_rating) if prov.avg_rating is not None else None)
        item = ServiceSearchItem(
            id=svc.id,
            name=svc.name,
            description=svc.description,
            price=float(svc.price),
            discount_price=float(svc.discount_price) if getattr(svc, "discount_price", None) is not None else None,
            duration_minutes=getattr(svc, "duration_minutes", None),
            is_active=svc.is_active,
            category=category_obj,
            provider=provider_obj,
            bookings_count=int(bookings_count or 0),
        )
        items.append(item)

    return SearchResponse(total=int(total or 0), page=page, per_page=per_page, items=items)
