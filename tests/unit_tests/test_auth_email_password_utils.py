"""
Guards: auth.py and email_utils.py
Contract: password reset token helpers and email dispatch behavior.
"""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import email_utils
from auth import generate_reset_token, hash_reset_token

pytestmark = [pytest.mark.unit]


def test_generate_reset_token_returns_unique_urlsafe_token_when_called_twice():
    first = generate_reset_token()
    second = generate_reset_token()

    assert isinstance(first, str)
    assert isinstance(second, str)
    assert first != second
    assert len(first) >= 43
    assert len(second) >= 43


def test_hash_reset_token_returns_sha256_hex_digest_when_token_is_provided():
    digest = hash_reset_token("plain-token")

    assert digest == "23fb79e20d37abf2418d78115eb0cc8c74b52f4ed8b91dda7fc03a1d41fc15e3"
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


@pytest.mark.asyncio
async def test_send_email_calls_aiosmtplib_send_when_email_payload_is_valid(
    monkeypatch,
):
    mock_send = AsyncMock()
    monkeypatch.setattr(email_utils.aiosmtplib, "send", mock_send)
    monkeypatch.setattr(email_utils.settings, "mail_from", "no-reply@example.com")
    monkeypatch.setattr(email_utils.settings, "mail_server", "smtp.example.com")
    monkeypatch.setattr(email_utils.settings, "mail_port", 587)
    monkeypatch.setattr(email_utils.settings, "mail_username", "")
    monkeypatch.setattr(
        email_utils.settings,
        "mail_password",
        SimpleNamespace(get_secret_value=lambda: ""),
    )
    monkeypatch.setattr(email_utils.settings, "mail_use_tls", True)

    await email_utils.send_email(
        to_email="user@example.com",
        subject="Subject",
        plain_text="hello",
        html_content="<p>Hello</p>",
    )

    assert mock_send.await_count == 1
    sent_message = mock_send.await_args.args[0]
    assert sent_message["From"] == "no-reply@example.com"
    assert sent_message["To"] == "user@example.com"
    assert sent_message["Subject"] == "Subject"


@pytest.mark.asyncio
async def test_send_pwd_reset_email_calls_send_with_reset_link_when_token_provided(
    monkeypatch,
):
    mock_send_email = AsyncMock()
    mock_template = SimpleNamespace(
        render=lambda **kwargs: f"<p>{kwargs['username']} - {kwargs['reset_url']}</p>"
    )

    monkeypatch.setattr(email_utils.settings, "front_end_url", "http://frontend.test")
    monkeypatch.setattr(
        email_utils.templates.env, "get_template", lambda _: mock_template
    )
    monkeypatch.setattr(email_utils, "send_email", mock_send_email)

    await email_utils.send_password_reset_email(
        to_email="user@example.com",
        username="alice",
        token="plain-token",
    )

    assert mock_send_email.await_count == 1
    call_kwargs = mock_send_email.await_args.kwargs
    assert call_kwargs["to_email"] == "user@example.com"
    assert call_kwargs["subject"] == "Reset Your Password - FastAPI Blog"
    assert (
        "http://frontend.test/reset-password?token=plain-token"
        in call_kwargs["plain_text"]
    )
    assert (
        "http://frontend.test/reset-password?token=plain-token"
        in call_kwargs["html_content"]
    )
