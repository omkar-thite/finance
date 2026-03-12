from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from schema import TypeEnum
from decimal import Decimal


class User(Base):

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    image_file: Mapped[str | None] = mapped_column(String(120))
    transactions: Mapped[list[Transaction]] = relationship(back_populates="user")

    @property
    def image_path(self) -> str | None:
        if self.image_file:
            return f"media/profile_pics/{self.image_file}"

        return None


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[TypeEnum] = mapped_column(Enum(TypeEnum), nullable=False)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    charges: Mapped[Decimal] = mapped_column(Numeric, nullable=True, default=0)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    user: Mapped[User] = relationship(back_populates="transactions")
