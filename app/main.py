from fastapi import FastAPI
from app.db.base import Base, engine
from app.api.routes import auth
from app.api.routes import admin as admin_router
from app.api.routes import provider as provider_router
from app.api.routes import category as category_router
from app.api.routes import services as services_router

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