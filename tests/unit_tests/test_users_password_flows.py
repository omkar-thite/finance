"""
Guards: routes/users.py and routes/front_view.py
Contract: password reset/change API and password-related HTML routes.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import models
import routes.users as users_route
from auth import get_current_user
from database import get_db
from main import app
from tests.helpers.db_mocks import mock_scalar_result

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def override_get_db(mock_db_session):
    async def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield mock_db_session


@pytest.fixture
def override_current_user():
    fake_user = SimpleNamespace(
        id=101,
        auth=SimpleNamespace(password_hash="existing-password-hash"),
    )

    async def _override_current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = _override_current_user
    yield fake_user


@pytest.fixture(autouse=True)
def enable_password_reset_feature(monkeypatch):
    monkeypatch.setattr(users_route, "is_email_configured", lambda: True)


async def test_get_login_page_returns_200_when_route_is_requested(async_client):
    response = await async_client.get("/login")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_get_forgot_password_page_returns_200_when_route_is_requested(
    async_client,
):
    response = await async_client.get("/forgot-password")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_get_reset_password_page_sets_no_referrer_header_when_route_is_requested(
    async_client,
):
    response = await async_client.get("/reset-password")

    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"


async def test_forgot_password_returns_503_when_email_not_configured(
    async_client,
    monkeypatch,
):
    monkeypatch.setattr(users_route, "is_email_configured", lambda: False)

    response = await async_client.post(
        "/api/users/forgot-password",
        json={"email": "alice@example.com"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Password reset is not available because mail is not configured."
    }


async def test_reset_password_returns_503_when_email_not_configured(
    async_client,
    monkeypatch,
):
    monkeypatch.setattr(users_route, "is_email_configured", lambda: False)

    response = await async_client.post(
        "/api/users/reset-password",
        json={"token": "valid-token", "new_password": "new-password-1"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Password reset is not available because mail is not configured."
    }


async def test_forgot_password_returns_202_with_generic_message_when_user_exists(
    async_client,
    override_get_db,
    monkeypatch,
):
    user = SimpleNamespace(id=7, username="alice", email="alice@example.com")
    override_get_db.execute.side_effect = [
        mock_scalar_result(user),
        mock_scalar_result(None),
    ]

    mock_send_email = AsyncMock()
    monkeypatch.setattr(users_route.models, "User", models.Users, raising=False)
    monkeypatch.setattr(users_route, "generate_reset_token", lambda: "plain-token")
    monkeypatch.setattr(users_route, "hash_reset_token", lambda _: "hashed-token")
    monkeypatch.setattr(users_route, "send_password_reset_email", mock_send_email)

    response = await async_client.post(
        "/api/users/forgot-password",
        json={"email": "alice@example.com"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": "If an account with that email exists, "
        "you will receive an password reset instructions.."
    }
    override_get_db.add.assert_called_once()
    override_get_db.commit.assert_awaited_once()


async def test_forgot_password_returns_202_null_body_when_user_does_not_exist(
    async_client,
    override_get_db,
    monkeypatch,
):
    override_get_db.execute.return_value = mock_scalar_result(None)
    monkeypatch.setattr(users_route.models, "User", models.Users, raising=False)

    response = await async_client.post(
        "/api/users/forgot-password",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 202
    assert response.json() is None


async def test_forgot_password_returns_422_when_email_is_missing(
    async_client,
    override_get_db,
):
    response = await async_client.post("/api/users/forgot-password", json={})

    assert response.status_code == 422


async def test_reset_password_returns_400_when_token_does_not_exist(
    async_client,
    override_get_db,
):
    override_get_db.execute.return_value = mock_scalar_result(None)

    response = await async_client.post(
        "/api/users/reset-password",
        json={"token": "unknown", "new_password": "new-password-1"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token."}


async def test_reset_password_returns_400_when_token_is_expired(
    async_client,
    override_get_db,
):
    expired_token = SimpleNamespace(
        id=12,
        user_id=7,
        expires_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    override_get_db.execute.side_effect = [
        mock_scalar_result(expired_token),
        mock_scalar_result(None),
    ]

    response = await async_client.post(
        "/api/users/reset-password",
        json={"token": "expired-token", "new_password": "new-password-1"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token."}
    override_get_db.commit.assert_awaited_once()


async def test_reset_password_returns_200_when_token_is_valid(
    async_client,
    override_get_db,
    monkeypatch,
):
    valid_token = SimpleNamespace(
        id=13,
        user_id=7,
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    user = SimpleNamespace(id=7)
    override_get_db.execute.side_effect = [
        mock_scalar_result(valid_token),
        mock_scalar_result(user),
        mock_scalar_result(None),
    ]

    monkeypatch.setattr(users_route.models, "User", models.Users, raising=False)
    monkeypatch.setattr(users_route, "hash_reset_token", lambda _: "hashed")
    monkeypatch.setattr(users_route, "hash_password", lambda _: "new-password-hash")

    response = await async_client.post(
        "/api/users/reset-password",
        json={"token": "valid-token", "new_password": "new-password-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Password has been reset successfully. "
        "You can now log in with your new password."
    }
    override_get_db.commit.assert_awaited_once()


async def test_reset_password_returns_422_when_new_password_is_too_short(
    async_client,
    override_get_db,
):
    response = await async_client.post(
        "/api/users/reset-password",
        json={"token": "valid-token", "new_password": "short"},
    )

    assert response.status_code == 422


async def test_change_password_returns_401_when_user_is_unauthenticated(async_client):
    response = await async_client.patch(
        "/api/users/me/password",
        json={
            "current_password": "old-password-1",
            "new_password": "new-password-1",
        },
    )

    assert response.status_code == 401


async def test_change_password_returns_400_when_current_password_is_incorrect(
    async_client,
    override_get_db,
    override_current_user,
    monkeypatch,
):
    monkeypatch.setattr(users_route, "verify_password", lambda *_: False)

    response = await async_client.patch(
        "/api/users/me/password",
        json={
            "current_password": "wrong-password",
            "new_password": "new-password-1",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is incorrect."}


async def test_change_password_returns_400_when_new_password_matches_current_password(
    async_client,
    override_get_db,
    override_current_user,
    monkeypatch,
):
    monkeypatch.setattr(users_route, "verify_password", lambda *_: True)

    response = await async_client.patch(
        "/api/users/me/password",
        json={
            "current_password": "same-password-1",
            "new_password": "same-password-1",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "New password must be different from current password."
    }


async def test_change_password_returns_200_when_payload_is_valid(
    async_client,
    override_get_db,
    override_current_user,
    monkeypatch,
):
    monkeypatch.setattr(users_route, "verify_password", lambda *_: True)
    monkeypatch.setattr(users_route, "hash_password", lambda _: "updated-password-hash")
    override_get_db.execute.return_value = mock_scalar_result(None)

    response = await async_client.patch(
        "/api/users/me/password",
        json={
            "current_password": "old-password-1",
            "new_password": "new-password-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully."}
    assert override_current_user.auth.password_hash == "updated-password-hash"
    override_get_db.commit.assert_awaited_once()


async def test_change_password_returns_400_when_auth_record_is_missing(
    async_client,
    override_get_db,
):
    fake_user = SimpleNamespace(id=101, auth=None)

    async def _override_current_user_without_auth():
        return fake_user

    app.dependency_overrides[get_current_user] = _override_current_user_without_auth

    response = await async_client.patch(
        "/api/users/me/password",
        json={
            "current_password": "old-password-1",
            "new_password": "new-password-1",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "User authentication record not found."}


async def test_change_password_returns_422_when_required_field_is_missing(
    async_client,
    override_get_db,
    override_current_user,
):
    response = await async_client.patch(
        "/api/users/me/password",
        json={"new_password": "new-password-1"},
    )

    assert response.status_code == 422
