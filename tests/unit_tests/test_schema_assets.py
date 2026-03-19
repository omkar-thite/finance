"""
Guards: schema.py
Contract: validates asset schema acceptance and rejection behavior.
"""

import pytest
from pydantic import ValidationError

from schema import CreateAsset, PatchAsset, ResponseAsset

pytestmark = pytest.mark.unit


class _AssetSource:
    def __init__(self):
        self.id = 10
        self.user_id = 2
        self.instrument = "AAPL"
        self.total_units = 12
        self.average_rate = "123.4500"


def test_create_asset_parses_payload_when_fields_are_valid():
    payload = {
        "instrument": "AAPL",
        "total_units": 12,
        "average_rate": "123.4500",
    }

    parsed = CreateAsset.model_validate(payload)

    assert parsed.instrument == "AAPL"
    assert parsed.total_units == 12
    assert str(parsed.average_rate) == "123.4500"


def test_create_asset_raises_validation_error_when_required_field_is_missing():
    payload = {
        "instrument": "AAPL",
        "total_units": 12,
    }

    with pytest.raises(ValidationError) as exc_info:
        CreateAsset.model_validate(payload)

    assert "average_rate" in str(exc_info.value)


def test_patch_asset_parses_minimal_payload_when_only_required_ids_are_provided():
    payload = {
        "id": 1,
        "user_id": 9,
    }

    parsed = PatchAsset.model_validate(payload)

    assert parsed.id == 1
    assert parsed.user_id == 9
    assert parsed.instrument is None
    assert parsed.total_units is None
    assert parsed.average_rate is None


def test_patch_asset_raises_validation_error_when_extra_field_is_provided():
    payload = {
        "id": 1,
        "user_id": 9,
        "extra": "not_allowed",
    }

    with pytest.raises(ValidationError) as exc_info:
        PatchAsset.model_validate(payload)

    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_response_asset_reads_attributes_when_model_is_built_from_orm_like_source():
    source = _AssetSource()

    parsed = ResponseAsset.model_validate(source, from_attributes=True)

    assert parsed.id == 10
    assert parsed.user_id == 2
    assert parsed.instrument == "AAPL"
    assert parsed.total_units == 12
    assert str(parsed.average_rate) == "123.4500"
