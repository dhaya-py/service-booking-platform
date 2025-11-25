from fastapi import FastAPI
from app.db.base import Base, engine
from app.api.routes import auth


app = FastAPI()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Service Booking Platform API running"}


app.include_router(auth.router, prefix="/api/auth")
