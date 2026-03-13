from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Enum, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from schema import TypeEnum
from decimal import Decimal


class User(Base):

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    image_file_name: Mapped[str | None] = mapped_column(String(120))
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    date_account_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    # Relationships
    # uselist=False makes these 1:1 relationships
    contact: Mapped[UserContact] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    auth: Mapped[UserAuth] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    bank_details: Mapped[UserBankDetails] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def image_path(self) -> str | None:
        if self.image_file_name:
            return f"media/profile_pics/{self.image_file_name}"
        return None


class UserContact(Base):
    __tablename__ = "users_contact"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), default=None, nullable=True)
    phone_no: Mapped[str] = mapped_column(
        String(12), default=None, unique=True, nullable=True
    )
    user: Mapped[User] = relationship(back_populates="contact")


class UserAuth(Base):
    __tablename__ = "users_auth"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(250), nullable=True, default=None)
    user: Mapped[User] = relationship(back_populates="auth")


class UserBankDetails(Base):
    __tablename__ = "users_bank_details"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    user: Mapped[User] = relationship(back_populates="bank_details")
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[TypeEnum] = mapped_column(Enum(TypeEnum), nullable=False)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    charges: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=True, default=0)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    user: Mapped[User] = relationship(back_populates="transactions")
