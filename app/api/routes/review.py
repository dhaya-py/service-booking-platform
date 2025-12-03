# app/api/routes/reviews.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models.review import Review
from app.db.models.booking import Booking
from app.db.models.user import User
from app.schemas.review import ReviewCreate, ReviewResponse
from app.core.security import get_current_user, require_admin

router = APIRouter(prefix="/reviews", tags=["reviews"])

# Helper: recalc provider aggregates
def _recalculate_provider_rating(db: Session, provider: User):
    # compute from reviews table
    rows = db.query(Review).filter(Review.provider_id == provider.id).all()
    total = len(rows)
    if total == 0:
        provider.avg_rating = 0.0
        provider.total_reviews = 0
    else:
        s = sum(r.rating for r in rows)
        provider.avg_rating = float(s) / total
        provider.total_reviews = total
    db.add(provider)
    db.commit()

# Create review (customer)
@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(review_in: ReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # only customers can create reviews
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can create reviews")

    # Verify booking exists
    booking = db.query(Booking).filter(Booking.id == review_in.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Booking must belong to current user
    if booking.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Booking does not belong to you")

    # Booking must be completed
    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Can only review completed bookings")

    # Enforce one review per booking (db unique + check)
    existing = db.query(Review).filter(Review.booking_id == review_in.booking_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Review for this booking already exists")

    # provider must exist and must be the booking's provider
    provider = db.query(User).filter(User.id == booking.provider_id, User.role == "provider").first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # create review
    review = Review(
        booking_id = booking.id,
        customer_id = current_user.id,
        provider_id = provider.id,
        rating = review_in.rating,
        comment = review_in.comment,
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    # update provider aggregates (recalculate for correctness; fine for small scale)
    _recalculate_provider_rating(db, provider)

    return review

# List reviews for a provider (public)
@router.get("/provider/{provider_id}", response_model=List[ReviewResponse])
def list_provider_reviews(provider_id: int, db: Session = Depends(get_db)):
    reviews = db.query(Review).filter(Review.provider_id == provider_id).order_by(Review.created_at.desc()).all()
    return reviews

# Admin: delete a review (and recalc)
@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_review(review_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    provider = db.query(User).filter(User.id == review.provider_id).first()
    db.delete(review)
    db.commit()

    # recalc provider aggregates
    if provider:
        _recalculate_provider_rating(db, provider)

    return
