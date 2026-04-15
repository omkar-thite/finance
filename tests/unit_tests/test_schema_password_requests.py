"""
Guards: schema.py
Contract: validates password reset/change request schemas.
"""

import pytest
from pydantic import ValidationError

from schema import ChangedPasswordRequest, ForgotPasswordRequest, ResetPasswordRequest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_forgot_password_request_parses_email_when_payload_is_valid():
    payload = {"email": "alice@example.com"}

    parsed = ForgotPasswordRequest.model_validate(payload)

    assert str(parsed.email) == "alice@example.com"


async def test_forgot_password_request_raises_validation_error_when_email_is_invalid():
    payload = {"email": "not-an-email"}

    with pytest.raises(ValidationError):
        ForgotPasswordRequest.model_validate(payload)


async def test_forgot_password_request_raises_validation_error_when_email_exceeds_max_length():
    domain = f"{'a' * 53}.{'b' * 53}.com"
    too_long_email = f"{'u' * 9}@{domain}"
    payload = {"email": too_long_email}

    with pytest.raises(ValidationError) as exc_info:
        ForgotPasswordRequest.model_validate(payload)

    assert "at most 120 items after validation" in str(exc_info.value)


async def test_reset_password_request_parses_payload_when_token_and_password_are_valid():
    payload = {
        "token": "reset-token",
        "new_password": "new-password-1",
    }

    parsed = ResetPasswordRequest.model_validate(payload)

    assert parsed.token == "reset-token"
    assert parsed.new_password == "new-password-1"


async def test_reset_password_request_raises_validation_error_when_new_password_is_too_short():
    payload = {
        "token": "reset-token",
        "new_password": "short",
    }

    with pytest.raises(ValidationError) as exc_info:
        ResetPasswordRequest.model_validate(payload)

    assert "at least 8 characters" in str(exc_info.value)


async def test_changed_password_request_parses_payload_when_both_passwords_are_provided():
    payload = {
        "current_password": "current-password-1",
        "new_password": "new-password-1",
    }

    parsed = ChangedPasswordRequest.model_validate(payload)

    assert parsed.current_password == "current-password-1"
    assert parsed.new_password == "new-password-1"


async def test_changed_pwd_request_raises_val_error_when_new_password_is_too_short():
    payload = {
        "current_password": "current-password-1",
        "new_password": "short",
    }

    with pytest.raises(ValidationError) as exc_info:
        ChangedPasswordRequest.model_validate(payload)

    assert "at least 8 characters" in str(exc_info.value)
