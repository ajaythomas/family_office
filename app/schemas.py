from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models import RoleEnum


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
