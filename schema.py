from pydantic import BaseModel, EmailStr, ConfigDict, Field
from decimal import Decimal
from datetime import date
from utils.enums import TrxTypeEnum, InstrumentType


class BaseTrx(BaseModel):
    # Base contains the common fields, but we make them optional for the "Base"
    type: TrxTypeEnum
    instrument: str
    units: int = Field(gt=0)
    rate: Decimal
    charges: Decimal = Decimal("0")


class CreateTrx(BaseTrx):
    user_id: int
    date_created: date | None = None


class ResponseTrx(BaseTrx):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    asset_id: int | None = None
    date_created: date


class PatchTrx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int  # Remove this after auth implementation
    type: TrxTypeEnum | None = None
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


class BaseAsset(BaseModel):
    instrument: str
    total_units: int
    average_rate: Decimal


class CreateAsset(BaseAsset):
    pass


class ResponseAsset(BaseAsset):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


class PatchAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    instrument: str | None = None
    total_units: int | None = None
    average_rate: Decimal | None = None


class BaseHolding(BaseModel):
    instrument_id: int
    quantity: int
    average_rate: Decimal


class CreateHodling(BaseHolding):
    pass


class ResponseHolding(BaseHolding):
    pass


class PatchHolding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str | None = None
    quantity: int | None = None
    average_rate: Decimal | None = None


class BaseInstrument(BaseModel):
    type: InstrumentType
    symbol: str = Field(max_length=20)
    name: str


class CreateInstrument(BaseInstrument):
    pass


class ResponseInstrument(BaseInstrument):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PatchInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: InstrumentType | None = None
    symbol: str | None = None
    name: str | None = None
