from fastapi import FastAPI
from app.db.base import Base, engine
from app.api.routes import auth
from app.api.routes import admin as admin_router
from app.api.routes import provider as provider_router
from app.api.routes import category as category_router
from app.api.routes import services as services_router
from app.api.routes import bookings as bookings_router
from app.api.routes import review as review_router
from app.api.routes import availability as availability_router
from app.api.routes import providers_dashboard as providers_dashboard_router
from app.api.routes import search as search_router
from app.api.routes import customer_dashboard as customer_dashboard_router
from app.api.routes import admin_dashboard as admin_dashboard_router


app = FastAPI()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Service Booking Platform API running"}


app.include_router(auth.router, prefix="/api/auth")
app.include_router(admin_router.router)
app.include_router(provider_router.router)
app.include_router(category_router.router)
app.include_router(services_router.router)
app.include_router(bookings_router.router)
app.include_router(review_router.router)
app.include_router(availability_router.router)
app.include_router(providers_dashboard_router.router)
app.include_router(search_router.router)
app.include_router(customer_dashboard_router.router)
app.include_router(admin_dashboard_router.router)