import enum
import uuid
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RoleEnum(str, enum.Enum):
    manager = "manager"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    google_sub: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum), default=RoleEnum.member)
    google_calendar_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    portfolio: Mapped[Optional["Portfolio"]] = relationship(
        "Portfolio", back_populates="owner", uselist=False
    )


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String, default="My Portfolio")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    owner: Mapped["User"] = relationship("User", back_populates="portfolio")
    holdings: Mapped[list["Holding"]] = relationship(
        "Holding", back_populates="portfolio", cascade="all, delete-orphan"
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String, ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String)
    shares: Mapped[float] = mapped_column(Float)
    purchase_price: Mapped[float] = mapped_column(Float)
    purchase_date: Mapped[date] = mapped_column(Date)
    sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sale_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
