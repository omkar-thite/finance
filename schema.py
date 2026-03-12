from pydantic import BaseModel, EmailStr, ConfigDict
from enum import Enum
from decimal import Decimal
from datetime import datetime


class TypeEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class BaseTrx(BaseModel):
    user_id: int
    type: TypeEnum
    instrument: str
    units: int
    rate: Decimal
    charges: Decimal = Decimal("0")


class CreateTrx(BaseTrx):
    pass


class ResponseTrx(BaseTrx):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: datetime
    pass


class BaseUser(BaseModel):
    username: str
    email: EmailStr


class CreateUser(BaseUser):
    image_path: str | None = None
    # password: str


class ResponseUser(BaseUser):
    model_config = ConfigDict(from_attributes=True)
    id: int
