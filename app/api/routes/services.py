# app/api/routes/services.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models.service import Service
from app.db.models.category import Category
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse
from app.core.security import get_current_user
from app.db.models.user import User


router = APIRouter(prefix="/services", tags=["services"])

# Provider creates service

@router.post("/provider/services", response_model=ServiceResponse)
def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only providers can create services
    if current_user.role != "provider":
        raise HTTPException(status_code=403, detail="Only providers can create services")

    # Validate category exists
    category = db.query(Category).filter(Category.id == service_data.category_id).first()
    if not category:
        raise HTTPException(404, detail="Category not found")

    new_service = Service(
        provider_id=current_user.id,
        category_id=service_data.category_id,
        name=service_data.name,
        description=service_data.description,
        price=service_data.price,
        discount_price=service_data.discount_price,
        duration_minutes=service_data.duration_minutes,
        is_active=service_data.is_active,
    )

    db.add(new_service)
    db.commit()
    db.refresh(new_service)

    return new_service


# Provider views their services

@router.get("/provider/services", response_model=list[ServiceResponse])
def get_my_services(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "provider":
        raise HTTPException(403, "Only providers can view their services")

    services = db.query(Service).filter(Service.provider_id == current_user.id).all()
    return services


# Provider updates their service

@router.put("/provider/services/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    update_data: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(404, "Service not found")

    # Permission check
    if service.provider_id != current_user.id:
        raise HTTPException(403, "You cannot edit another provider's service")

    # Update fields one-by-one
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service



# Provider deletes their service

@router.delete("/provider/services/{service_id}")
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(404, "Service not found")

    if service.provider_id != current_user.id:
        raise HTTPException(403, "You cannot delete another provider's service")

    service.is_active = False

    db.commit()
    return {"message": "Service deactivated successfully"}



# Get services by category

@router.get("/services/category/{category_id}", response_model=list[ServiceResponse])
def get_services_by_category(category_id: int, db: Session = Depends(get_db)):
    services = (
        db.query(Service)
        .filter(Service.category_id == category_id, Service.is_active == True)
        .all()
    )
    return services


# Get services by provider

@router.get("/providers/{provider_id}/services", response_model=list[ServiceResponse])
def get_provider_services(provider_id: int, db: Session = Depends(get_db)):
    services = (
        db.query(Service)
        .filter(Service.provider_id == provider_id, Service.is_active == True)
        .all()
    )
    return services
