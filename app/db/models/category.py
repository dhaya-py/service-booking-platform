# app/db/models/category.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    providers = relationship(
        "User",
        secondary="provider_categories",  # or use the Table object reference if in scope
        back_populates="categories",
        lazy="selectin"
    )

    services = relationship(
    "Service",
    back_populates="category",
    lazy="selectin"
    )

