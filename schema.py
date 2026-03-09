from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from enum import Enum

class TypeEnum(str, Enum):
    BUY = 'buy'
    SELL = 'sell'


class BaseTransaction(BaseModel):
    type: TypeEnum
    date : str
    entity_name: str
    units: int
    rate: float

class CreateTransaction(BaseTransaction):
    id: int
    user_id: int

class ResponseTransaction(BaseTransaction):
    pass