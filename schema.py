from pydantic import BaseModel, EmailStr, ConfigDict
from enum import Enum
from decimal import Decimal
from datetime import date


class TypeEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class BaseTrx(BaseModel):
    # Base contains the common fields, but we make them optional for the "Base"
    type: TypeEnum
    instrument: str
    units: int
    rate: Decimal
    charges: Decimal = Decimal("0")


class CreateTrx(BaseTrx):
    user_id: int
    date_created: date | None = None


class ResponseTrx(BaseTrx):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_created: date


class PatchTrx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int  # Remove this after auth implementation
    type: TypeEnum | None = None
    instrument: str | None = None
    units: int | None = None
    rate: Decimal | None = None
    charges: Decimal | None = None
    date_created: date | None = None


class UserBase(BaseModel):
    username: str


class UserContact(UserBase):
    email: EmailStr
    phone_no: str | None = None


class CreateUser(UserContact):
    image_file_name: str | None = None
    pass


class ResponseUser(UserBase):
    id: int
    pass


class PatchUser(UserBase):
    user_id: int  # Remove this after auth implementation
    username: str
    email: EmailStr
    phone_no: str | None = None
    image_file_name: str | None = None
