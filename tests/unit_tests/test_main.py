"""
Guards: main.py
Contract: unit coverage for API and HTML routes, including patch/delete flows.
"""

import pytest
import pytest_asyncio
from datetime import date
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from main import app
from database import Base, get_db
from sqlalchemy.pool import StaticPool
import models

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
)


# CREATE TABLES ONCE (Session Scope)
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Creates the tables exactly once for the entire test run."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


# ROLLBACK AFTER EVERY TEST (Function Scope)
@pytest_asyncio.fixture()
async def db_session():
    """Starts a transaction for a test, and rolls it back when the test finishes."""
    async with engine.connect() as connection:
        transaction = await connection.begin()

        # Bind the session to the specific connection handling the transaction
        session = TestingSessionLocal(bind=connection)

        yield session  # The test runs here

        # Teardown: close session and rollback the transaction to wipe data
        await session.close()
        await transaction.rollback()


# 4. OVERRIDE FASTAPI DEPENDENCY
@pytest_asyncio.fixture(autouse=True)
async def override_get_db_dependency(db_session):
    """Forces FastAPI to use our transactional test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    # Clean up the override after the test
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def created_user(client):
    response = await client.post(
        "/api/users/",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "alice-secret",
            "image_path": "",
        },
    )
    assert response.status_code == 201

    return response.json()


@pytest_asyncio.fixture
async def created_transaction(client, created_user, instrument_aapl):
    resp = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument_id": instrument_aapl.id,
            "units": 10,
            "rate": 150.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    if "instrument" not in body:
        body["instrument"] = "AAPL"
    if "user_id" not in body:
        body["user_id"] = created_user["id"]
    return body


@pytest_asyncio.fixture
async def another_user(client):
    response = await client.post(
        "/api/users/",
        json={
            "username": "charlie",
            "email": "charlie@example.com",
            "password": "charlie-secret",
            "image_path": "",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def another_transaction(client, another_user, instrument_msft):
    resp = await client.post(
        "/api/transactions/",
        json={
            "user_id": another_user["id"],
            "type": "buy",
            "instrument_id": instrument_msft.id,
            "units": 3,
            "rate": 250.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def instrument_tsla(db_session):
    instrument = models.Instruments(symbol="TSLA", type="equity", name="Tesla")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def instrument_goog(db_session):
    instrument = models.Instruments(symbol="GOOG", type="equity", name="Google")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def instrument_msft(db_session):
    instrument = models.Instruments(symbol="MSFT", type="equity", name="Microsoft")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def instrument_aapl(db_session):
    instrument = models.Instruments(symbol="AAPL", type="equity", name="Apple")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def instrument_meta(db_session):
    instrument = models.Instruments(symbol="META", type="equity", name="Meta")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def instrument_nvda(db_session):
    instrument = models.Instruments(symbol="NVDA", type="equity", name="Nvidia")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


# ── Users ─────────────────────────────────────────────────────────────────────


class TestCreateUser:
    async def test_success(self, client):
        resp = await client.post(
            "/api/users/",
            json={
                "username": "bob",
                "email": "bob@example.com",
                "password": "bob-secret",
                "image_path": "",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "bob"
        assert "id" in data

    async def test_duplicate_username(self, client, created_user):
        resp = await client.post(
            "/api/users/",
            json={
                "username": "alice",
                "email": "other@example.com",
                "password": "other-secret",
                "image_path": "",
            },
        )
        assert resp.status_code == 400
        assert "Username already exists" in resp.json()["detail"]

    async def test_duplicate_email(self, client, created_user):
        resp = await client.post(
            "/api/users/",
            json={
                "username": "other",
                "email": "alice@example.com",
                "password": "other-secret",
                "image_path": "",
            },
        )
        assert resp.status_code == 400
        assert "email/phone already exists" in resp.json()["detail"]

    async def test_missing_password_returns_422(self, client):
        resp = await client.post(
            "/api/users/",
            json={"username": "bob", "email": "bob@example.com", "image_path": ""},
        )

        assert resp.status_code == 422


class TestAuthentication:
    async def test_login_returns_bearer_token(self, client, created_user):
        resp = await client.post(
            "/api/users/token",
            data={"username": "alice@example.com", "password": "alice-secret"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_rejects_invalid_password(self, client, created_user):
        resp = await client.post(
            "/api/users/token",
            data={"username": "alice@example.com", "password": "wrong-password"},
        )

        assert resp.status_code == 401
        assert resp.json() == {"detail": "Incorrect email or password"}

    async def test_me_returns_current_user_when_token_is_valid(
        self, client, created_user
    ):
        login_resp = await client.post(
            "/api/users/token",
            data={"username": "alice@example.com", "password": "alice-secret"},
        )
        token = login_resp.json()["access_token"]

        me_resp = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert me_resp.status_code == 200
        body = me_resp.json()
        assert body["id"] == created_user["id"]
        assert body["username"] == created_user["username"]

    async def test_me_rejects_invalid_token(self, client):
        resp = await client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert resp.status_code == 401


class TestGetAllUsers:
    async def test_empty(self, client):
        response = await client.get("/api/users/")
        assert response.json() == []

    async def test_lists_created_user(self, client, created_user):
        resp = await client.get("/api/users/")
        assert any(u["id"] == created_user["id"] for u in resp.json())


class TestGetUserById:
    @pytest.mark.unit
    async def test_get_user_by_id_returns_200_when_user_exists(
        self, client, created_user
    ):
        response = await client.get(f"/api/users/{created_user['id']}")

        assert response.status_code == 200
        assert response.json() == {
            "id": created_user["id"],
            "username": created_user["username"],
        }

    @pytest.mark.unit
    async def test_get_user_by_id_returns_422_when_path_user_id_is_not_an_integer(
        self, client
    ):
        response = await client.get("/api/users/not-an-int")

        assert response.status_code == 422


# ── Transactions ───────────────────────────────────────────────────────────────


class TestCreateTransaction:
    async def test_buy(self, client, created_user, instrument_tsla):
        resp = await client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "buy",
                "instrument_id": instrument_tsla.id,
                "units": 5,
                "rate": 200.0,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "buy"

    async def test_sell(self, client, created_user, instrument_goog):
        resp = await client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "sell",
                "instrument_id": instrument_goog.id,
                "units": 2,
                "rate": 100.0,
            },
        )
        assert resp.status_code == 400
        assert "Sell units exceed available holdings" in resp.json()["detail"]

    async def test_unknown_user(self, client, instrument_aapl):
        resp = await client.post(
            "/api/transactions/",
            json={
                "user_id": 9999,
                "type": "buy",
                "instrument_id": instrument_aapl.id,
                "units": 1,
                "rate": 1.0,
            },
        )
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    @pytest.mark.unit
    async def test_create_transaction_returns_422_when_units_is_zero(
        self, client, created_user, instrument_aapl
    ):
        response = await client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "buy",
                "instrument_id": instrument_aapl.id,
                "units": 0,
                "rate": 10.0,
            },
        )

        assert response.status_code == 422

    @pytest.mark.unit
    async def test_create_transaction_persists_charges_and_ignores_date_created(
        self, client, created_user, instrument_meta
    ):
        supplied_date = "2000-01-01"
        response = await client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "buy",
                "instrument_id": instrument_meta.id,
                "units": 2,
                "rate": 123.45,
                "charges": "12.3400",
                "date_created": supplied_date,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["charges"] == "12.3400"
        assert body["date_created"] != supplied_date
        assert body["date_created"] == str(date.today())


class TestGetTransaction:
    async def test_existing(self, client, created_transaction):
        resp = await client.get(f"/api/transactions/{created_transaction['id']}")
        assert resp.status_code == 200

    async def test_not_found(self, client):
        response = await client.get("/api/transactions/9999")
        assert response.status_code == 404


class TestGetAllTransactions:
    async def test_empty_returns(self, client):
        response = await client.get("/api/transactions/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_list(self, client, created_transaction):
        resp = await client.get("/api/transactions/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestGetUserTransactions:
    async def test_returns_transactions(
        self, client, created_user, created_transaction
    ):
        resp = await client.get(f"/api/users/{created_user['id']}/transactions/")
        assert resp.status_code == 200
        assert resp.json()[0]["user_id"] == created_user["id"]

    async def test_unknown_user(self, client):
        response = await client.get("/api/users/9999/transactions/")
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    async def test_empty_list_for_new_user(self, client, created_user):
        resp = await client.get(f"/api/users/{created_user['id']}/transactions/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPatchUser:
    @pytest.mark.unit
    async def test_patch_user_returns_200_when_payload_is_valid(
        self, client, created_user
    ):
        payload = {
            "user_id": created_user["id"],
            "username": "alice_updated",
            "email": "alice.updated@example.com",
            "phone_no": "1234567890",
            "image_file_name": "avatar.png",
        }

        resp = await client.patch("/api/users/", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"id": created_user["id"], "username": "alice_updated"}

    @pytest.mark.unit
    async def test_patch_user_returns_404_when_user_does_not_exist(self, client):
        payload = {
            "user_id": 9999,
            "username": "ghost",
            "email": "ghost@example.com",
        }

        resp = await client.patch("/api/users/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    async def test_patch_user_returns_422_when_required_field_is_missing(
        self, client, created_user
    ):
        payload = {
            "user_id": created_user["id"],
            "username": "alice_updated",
        }

        resp = await client.patch("/api/users/", json=payload)

        assert resp.status_code == 422


class TestDeleteUser:
    @pytest.mark.unit
    async def test_delete_user_returns_204_when_user_exists(self, client, created_user):
        resp = await client.delete(f"/api/users/?user_id={created_user['id']}")

        assert resp.status_code == 204
        assert resp.content == b""

        users_resp = await client.get("/api/users/")
        assert users_resp.status_code == 200
        assert all(u["id"] != created_user["id"] for u in users_resp.json())

    @pytest.mark.unit
    async def test_delete_user_returns_404_when_user_does_not_exist(self, client):
        resp = await client.delete("/api/users/?user_id=9999")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    async def test_delete_user_returns_422_when_user_id_query_param_is_missing(
        self, client
    ):
        resp = await client.delete("/api/users/")

        assert resp.status_code == 422


class TestPatchTransaction:
    @pytest.mark.unit
    async def test_patch_transaction_returns_200_when_payload_is_valid(
        self, client, created_transaction, instrument_nvda
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": created_transaction["user_id"],
            "instrument_id": instrument_nvda.id,
            "units": 42,
            "rate": 321.5,
        }

        resp = await client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_transaction["id"]
        assert data["user_id"] == created_transaction["user_id"]
        assert data["instrument_id"] == instrument_nvda.id
        assert data["units"] == 42
        assert data["rate"] == "321.5000"

    @pytest.mark.unit
    async def test_patch_transaction_returns_404_when_user_does_not_exist(
        self, client, created_transaction, instrument_nvda
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": 9999,
            "instrument_id": instrument_nvda.id,
        }

        resp = await client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    async def test_patch_transaction_returns_404_when_transaction_does_not_exist(
        self, client, created_user, instrument_nvda
    ):
        payload = {
            "id": 9999,
            "user_id": created_user["id"],
            "instrument_id": instrument_nvda.id,
        }

        resp = await client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    async def test_patch_transaction_returns_422_when_payload_contains_extra_fields(
        self, client, created_transaction, instrument_nvda
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": created_transaction["user_id"],
            "instrument_id": instrument_nvda.id,
            "unknown_field": "should_fail",
        }

        resp = await client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_patch_transaction_reflects_date_created_in_response_when_date_is_provided(
        self, client, created_transaction
    ):
        patched_date = "2020-02-02"
        payload = {
            "id": created_transaction["id"],
            "user_id": created_transaction["user_id"],
            "date_created": patched_date,
        }

        response = await client.patch("/api/transactions/", json=payload)

        assert response.status_code == 200
        assert response.json()["date_created"] == patched_date


class TestDeleteTransaction:
    @pytest.mark.unit
    async def test_delete_transaction_returns_204_when_user_owns_transaction(
        self, client, created_transaction
    ):
        resp = await client.delete(
            f"/api/transactions/?user_id={created_transaction['user_id']}"
            f"&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 204
        assert resp.content == b""

        get_resp = await client.get(f"/api/transactions/{created_transaction['id']}")
        assert get_resp.status_code == 404
        assert get_resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    async def test_delete_transaction_returns_404_when_user_does_not_exist(
        self, client, created_transaction
    ):
        resp = await client.delete(
            f"/api/transactions/?user_id=9999&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    async def test_delete_transaction_returns_404_when_transaction_does_not_exist(
        self, client, created_user
    ):
        resp = await client.delete(
            f"/api/transactions/?user_id={created_user['id']}&trx_id=9999"
        )

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    async def test_delete_transaction_returns_400_when_transaction_does_not_belong_to_user(
        self, client, created_transaction, another_user
    ):
        resp = await client.delete(
            f"/api/transactions/?user_id={another_user['id']}"
            f"&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 400
        assert resp.json() == {"detail": "Transaction does not belong to user"}

    @pytest.mark.unit
    async def test_delete_transaction_returns_422_when_query_parameters_are_missing(
        self, client
    ):
        resp = await client.delete("/api/transactions/")

        assert resp.status_code == 422


# -------------------- HTML ENDPOINT TESTS ------------------- #


class TestHomePageHTML:
    async def test_home_page_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestUserHomePageHTML:
    async def test_existing_user_renders(self, client, created_user):
        user_id = created_user["id"]
        resp = await client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert created_user["username"] in resp.text  # check user data appears in HTML

    async def test_unknown_user_returns_404_html(self, client):
        resp = await client.get("/users/9999")
        assert resp.status_code == 404
        # Since it's not an /api/ path, it should render error.html, not JSON
        assert "text/html" in resp.headers["content-type"]


class TestUserTransactionsPageHTML:
    async def test_renders_transactions(
        self, client, created_user, created_transaction
    ):
        resp = await client.get(f"/users/{created_user['id']}/transactions")
        assert resp.status_code == 200
        assert str(created_transaction["instrument_id"]) in resp.text

    async def test_unknown_user_returns_404_html(self, client):
        resp = await client.get("/users/9999/transactions")
        assert resp.status_code == 404
        assert "text/html" in resp.headers["content-type"]


class TestAllTransactionsPageHTML:
    async def test_renders_page(self, client):
        resp = await client.get("/transactions/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
