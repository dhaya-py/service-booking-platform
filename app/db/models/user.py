# app/db/models/user.py
from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

# association table defined here (or you can put in separate module)
provider_categories = Table(
    "provider_categories",
    Base.metadata,
    Column("provider_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="customer", server_default="customer")

    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    description = Column(String, nullable=True)


    # if this user is a provider, this relationship links to categories
    categories = relationship(
        "Category",
        secondary=provider_categories,
        back_populates="providers",
        lazy="selectin"
    )

     # One-to-many with Service (IMPORTANT)
    services = relationship(
        "Service",
        back_populates="provider",
        lazy="selectin"
    )

