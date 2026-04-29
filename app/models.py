import enum
from datetime import UTC, date, datetime
from nanoid import generate
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

"""
models.py = DB representation / persistence
schemas.py = API contract / validation

Defines your database tables and ORM classes with SQLAlchemy.
"""
class Base(DeclarativeBase):
    pass


class RoleEnum(str, enum.Enum):
    manager = "manager"
    member = "member"


class User(Base):
    __tablename__ = "users"

    '''
    mapped_column is the modern replacement for the traditional Column construct when using the SQLAlchemy ORM. Works with Python type hints (PEP 484) to provide better IDE support and static type checking.
    
    Type-Hint Integration: It automatically derives database types and nullability from Python type annotations used with Mapped[]. For example, Mapped[int] implies nullable=False, while Mapped[Optional[int]] implies nullable=True.
    Superior to Column: While Column is still part of SQLAlchemy Core, mapped_column is ORM-aware, allowing it to handle ORM-specific configuration that the Core layer cannot.
    Declarative Mapping: It is the standard for the Annotated Declarative Table style, making model definitions more concise and readable.
    '''
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(generate()))
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

    # lambda below is python's anonymous func. Without it, if you specified, default=uuid.uuid4() → would call once when the module loads and reuse the same value for every row. With the lambda keyword, this passes a callable to SQLAlchemy, so SQLAlchemy calls it each time a new row is created
    # I just replaced uuid with nanoid which is more user-friendly https://planetscale.com/blog/why-we-chose-nanoids-for-planetscales-api 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(generate()))
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

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(generate()))
    portfolio_id: Mapped[str] = mapped_column(String, ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String)
    shares: Mapped[float] = mapped_column(Float)
    purchase_price: Mapped[float] = mapped_column(Float)
    purchase_date: Mapped[date] = mapped_column(Date)
    sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sale_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
