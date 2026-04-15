from pydantic import BaseModel, EmailStr, ConfigDict, Field
from decimal import Decimal
from datetime import date
from utils.enums import TrxTypeEnum, InstrumentType


class BaseTrx(BaseModel):
    type_: TrxTypeEnum
    instrument_id: int
    units: int = Field(gt=0)
    rate: Decimal
    charges: Decimal = Decimal("0")
    date_created: date | None = None


class CreateTrx(BaseTrx):
    user_id: int


class ResponseTrx(BaseTrx):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    instrument: str | None = None


class PatchTrx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int  # Remove this after auth implementation
    type_: TrxTypeEnum | None = None
    instrument_id: int | None = None
    units: int | None = None
    rate: Decimal | None = None
    charges: Decimal | None = None
    date_created: date | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class UserPrivate(UserPublic):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr | None = None
    phone_no: str | None = None
    image_path: str | None = None


class CreateUser(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone_no: str | None = None
    image_path: str | None = None
    image_file_name: str | None = None


class PatchUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    email: EmailStr
    phone_no: str | None = None


class BaseHoldings(BaseModel):
    instrument_id: int
    quantity: int
    average_rate: Decimal


class CreateHoldings(BaseHoldings):
    pass


class ResponseHoldings(BaseHoldings):
    model_config = ConfigDict(from_attributes=True)

    instrument: str | None = None


class PatchHoldings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_units: int | None = None
    average_rate: Decimal | None = None


class BaseInstrument(BaseModel):
    type_: InstrumentType
    symbol: str = Field(max_length=20)
    name: str


class CreateInstrument(BaseInstrument):
    pass


class ResponseInstrument(BaseInstrument):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PatchInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_: InstrumentType | None = None
    symbol: str | None = None
    name: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str


class PaginatedResponse(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class PaginatedTransactions(PaginatedResponse):
    transactions: list[ResponseTrx]


class PaginatedHoldings(PaginatedResponse):
    holdings: list[ResponseHoldings]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangedPasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
