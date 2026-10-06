from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
    UniqueConstraint
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from database.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    google_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False
    )

    name: Mapped[str | None] = mapped_column(
        String(255)
    )

    picture: Mapped[str | None] = mapped_column(
        String(1000)
    )

    trackings: Mapped[list["Tracking"]] = relationship(
        "Tracking", back_populates="user", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    url: Mapped[str] = mapped_column(
        String(1000),
        unique=True,
        nullable=False
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    image_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True
    )


    current_price: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    prices: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    trackings: Mapped[list["Tracking"]] = relationship(
        "Tracking", back_populates="product", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
        index=True
    )

    price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="prices"
    )

class Tracking(Base):

    __tablename__ = "trackings"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_tracking_user_product"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False
    )

    target_price: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    alert_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="trackings")
    product: Mapped["Product"] = relationship("Product", back_populates="trackings")
