from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models import RoleEnum

"""
This file defines Pydantic models for data entering and leaving your API.
BaseModel which these classes inherit from is Pydantic’s validation/model class.
These are used to validate request bodies and serialize responses.

models.py = DB representation / persistence
schemas.py = API contract / validation

"""

class HoldingCreate(BaseModel):
    ticker: str
    shares: float
    purchase_price: float
    purchase_date: date
    sale_price: Optional[float] = None
    sale_date: Optional[date] = None


class HoldingRead(HoldingCreate):
    id: str
    portfolio_id: str

    """
    HoldingRead is intended to represent data coming from a SQLAlchemy ORM object. 
    SQLAlchemy objects expose fields as attributes, e.g. holding.id, holding.ticker.
    from_attributes=True allows Pydantic to build HoldingRead from that object directly.

    Without it:
    Pydantic would expect a dict like {"id": "...", "ticker": "..."}
    With it:
    Pydantic can also accept a SQLAlchemy model instance or any object with matching attributes
    
    This is useful when a route returns ORM objects; and you want FastAPI/Pydantic to serialize them as response models automatically
    So, really this is just a Pydantic configuration option that makes HoldingRead ORM-friendly.
    """
    model_config = {"from_attributes": True}


class PortfolioRead(BaseModel):
    id: str
    owner_id: str
    name: str
    holdings: list[HoldingRead]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: str
    email: str
    name: str
    role: RoleEnum
    created_at: datetime

    model_config = {"from_attributes": True}
