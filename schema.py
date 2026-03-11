from pydantic import BaseModel, EmailStr
from enum import Enum


class TypeEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class BaseTrx(BaseModel):
    user_id: int
    type: TypeEnum
    entity_name: str
    units: int
    rate: float


class CreateTrx(BaseTrx):
    pass


class ResponseTrx(BaseTrx):
    pass


class BaseUser(BaseModel):
    username: str
    email: EmailStr


class CreateUser(BaseUser):
    image_path: str | None = None
    # password: str


class ResponseUser(BaseUser):
    pass
