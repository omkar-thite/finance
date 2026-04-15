from __future__ import annotations

from datetime import UTC, datetime, date

from sqlalchemy import (
    DateTime,
    Date,
    Integer,
    String,
    TEXT,
    Enum,
    Numeric,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from utils.enums import TrxTypeEnum, InstrumentType
from decimal import Decimal


class Users(Base):

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    image_file_name: Mapped[str | None] = mapped_column(String(120))
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
    transactions: Mapped[list[Transactions]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    holdings: Mapped[list[Holdings]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def image_path(self) -> str | None:
        if self.image_file_name:
            return f"media/profile_pics/{self.image_file_name}"
        return None

    @property
    def email(self) -> str | None:
        if self.contact:
            return self.contact.email
        return None

    @property
    def phone_no(self) -> str | None:
        if self.contact:
            return self.contact.phone_no
        return None


class UserContact(Base):
    __tablename__ = "users_contact"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), default=None, nullable=True
    )
    phone_no: Mapped[str | None] = mapped_column(
        String(12), default=None, unique=True, nullable=True
    )
    user: Mapped[Users] = relationship(back_populates="contact")


class UserAuth(Base):
    __tablename__ = "users_auth"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    user: Mapped[Users] = relationship(back_populates="auth")


class UserBankDetails(Base):
    __tablename__ = "users_bank_details"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, nullable=False, index=True
    )
    user: Mapped[Users] = relationship(back_populates="bank_details")
    pass


class Transactions(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type_: Mapped[TrxTypeEnum] = mapped_column(Enum(TrxTypeEnum), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    charges: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=True, default=0)
    date_created: Mapped[date] = mapped_column(
        Date(),
        default=lambda: date.today(),
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), nullable=False, index=True
    )

    user: Mapped[Users] = relationship(back_populates="transactions")
    holdings: Mapped[Holdings] = relationship(back_populates="transactions")
    instrument_rel: Mapped[Instruments] = relationship("Instruments", lazy="selectin")

    @property
    def instrument(self) -> str | None:
        rel = self.__dict__.get("instrument_rel")
        return rel.name if rel else None

    __table_args__ = (CheckConstraint("units > 0", name="transactions_units_gt_0"),)


class Instruments(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    type_: Mapped[InstrumentType] = mapped_column(Enum(InstrumentType), nullable=False)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)


class Holdings(Base):
    __tablename__ = "holdings"

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, primary_key=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), nullable=False, primary_key=True
    )
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"), nullable=True, index=True
    )

    user: Mapped[Users] = relationship(back_populates="holdings")
    transactions: Mapped[list[Transactions]] = relationship(back_populates="holdings")
    instrument_rel: Mapped[Instruments] = relationship("Instruments", lazy="selectin")

    @property
    def instrument(self) -> str | None:
        rel = self.__dict__.get("instrument_rel")
        return rel.name if rel else None


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[Users] = relationship(back_populates="reset_tokens")
