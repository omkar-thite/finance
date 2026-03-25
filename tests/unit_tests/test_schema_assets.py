"""
Guards: schema.py
Contract: validates holdings schema acceptance and rejection behavior.
"""

import pytest
from pydantic import ValidationError

from schema import CreateHoldings, PatchHoldings, ResponseHoldings

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class _HoldingsSource:
    def __init__(self):
        self.instrument_id = 10
        self.user_id = 2
        self.quantity = 12
        self.average_rate = "123.4500"


async def test_create_holdings_parses_payload_when_fields_are_valid():
    payload = {
        "instrument_id": 10,
        "quantity": 12,
        "average_rate": "123.4500",
        "user_id": 2,
    }

    parsed = CreateHoldings.model_validate(payload)

    assert parsed.instrument_id == 10
    assert parsed.quantity == 12
    assert str(parsed.average_rate) == "123.4500"
    assert parsed.user_id == 2


async def test_create_holdings_raises_validation_error_when_required_field_is_missing():
    payload = {
        "instrument_id": 10,
        "quantity": 12,
    }

    with pytest.raises(ValidationError) as exc_info:
        CreateHoldings.model_validate(payload)

    assert "user_id" in str(exc_info.value)


async def test_patch_holdings_parses_payload_when_supported_fields_are_provided():
    payload = {
        "total_units": 9,
        "average_rate": "45.6000",
    }

    parsed = PatchHoldings.model_validate(payload)

    assert parsed.total_units == 9
    assert str(parsed.average_rate) == "45.6000"


async def test_patch_holdings_raises_validation_error_when_extra_field_is_provided():
    payload = {
        "total_units": 1,
        "extra": "not_allowed",
    }

    with pytest.raises(ValidationError) as exc_info:
        PatchHoldings.model_validate(payload)

    assert "Extra inputs are not permitted" in str(exc_info.value)


async def test_response_holdings_reads_attributes_when_model_is_built_from_orm_like_source():
    source = _HoldingsSource()

    parsed = ResponseHoldings.model_validate(source, from_attributes=True)

    assert parsed.instrument_id == 10
    assert parsed.quantity == 12
    assert str(parsed.average_rate) == "123.4500"
