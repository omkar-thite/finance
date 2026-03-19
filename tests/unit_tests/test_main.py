"""
Guards: main.py
Contract: unit coverage for API and HTML routes, including patch/delete flows.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.unit

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# CREATE TABLES ONCE (Session Scope)
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Creates the tables exactly once for the entire test run."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ROLLBACK AFTER EVERY TEST (Function Scope)
@pytest.fixture()
def db_session():
    """Starts a transaction for a test, and rolls it back when the test finishes."""
    connection = engine.connect()
    transaction = connection.begin()

    # Bind the session to the specific connection handling the transaction
    session = TestingSessionLocal(bind=connection)

    yield session  # The test runs here

    # Teardown: close session, rollback the transaction to wipe data, close connection
    session.close()
    transaction.rollback()
    connection.close()


# 4. OVERRIDE FASTAPI DEPENDENCY
@pytest.fixture(autouse=True)
def override_get_db_dependency(db_session):
    """Forces FastAPI to use our transactional test session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    # Clean up the override after the test
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def created_user(client):
    response = client.post(
        "/api/users/",
        json={"username": "alice", "email": "alice@example.com", "image_path": ""},
    )
    assert response.status_code == 201

    return response.json()


@pytest.fixture
def created_transaction(client, created_user):
    resp = client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument": "AAPL",
            "units": 10,
            "rate": 150.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def another_user(client):
    response = client.post(
        "/api/users/",
        json={"username": "charlie", "email": "charlie@example.com", "image_path": ""},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def another_transaction(client, another_user):
    resp = client.post(
        "/api/transactions/",
        json={
            "user_id": another_user["id"],
            "type": "buy",
            "instrument": "MSFT",
            "units": 3,
            "rate": 250.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ── Users ─────────────────────────────────────────────────────────────────────


class TestCreateUser:
    def test_success(self, client):
        resp = client.post(
            "/api/users/",
            json={"username": "bob", "email": "bob@example.com", "image_path": ""},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "bob"
        assert "id" in data

    def test_duplicate_username(self, client, created_user):
        resp = client.post(
            "/api/users/",
            json={"username": "alice", "email": "other@example.com", "image_path": ""},
        )
        assert resp.status_code == 400
        assert "Username already exists" in resp.json()["detail"]

    def test_duplicate_email(self, client, created_user):
        resp = client.post(
            "/api/users/",
            json={"username": "other", "email": "alice@example.com", "image_path": ""},
        )
        assert resp.status_code == 400
        assert "email/phone already exists" in resp.json()["detail"]


class TestGetAllUsers:
    def test_empty(self, client):
        assert client.get("/api/users/").json() == []

    def test_lists_created_user(self, client, created_user):
        resp = client.get("/api/users/")
        assert any(u["id"] == created_user["id"] for u in resp.json())


# ── Transactions ───────────────────────────────────────────────────────────────


class TestCreateTransaction:
    def test_buy(self, client, created_user):
        resp = client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "buy",
                "instrument": "TSLA",
                "units": 5,
                "rate": 200.0,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "buy"

    def test_sell(self, client, created_user):
        resp = client.post(
            "/api/transactions/",
            json={
                "user_id": created_user["id"],
                "type": "sell",
                "instrument": "GOOG",
                "units": 2,
                "rate": 100.0,
            },
        )
        assert resp.status_code == 400
        assert "Sell units exceed available holdings" in resp.json()["detail"]

    def test_unknown_user(self, client):
        resp = client.post(
            "/api/transactions/",
            json={
                "user_id": 9999,
                "type": "buy",
                "instrument": "AAPL",
                "units": 1,
                "rate": 1.0,
            },
        )
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]


class TestGetTransaction:
    def test_existing(self, client, created_transaction):
        resp = client.get(f"/api/transactions/{created_transaction['id']}")
        assert resp.status_code == 200

    def test_not_found(self, client):
        assert client.get("/api/transactions/9999").status_code == 404


class TestGetAllTransactions:
    def test_empty_returns(self, client):
        response = client.get("/api/transactions/")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_list(self, client, created_transaction):
        resp = client.get("/api/transactions/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestGetUserTransactions:
    def test_returns_transactions(self, client, created_user, created_transaction):
        resp = client.get(f"/api/users/{created_user['id']}/transactions/")
        assert resp.status_code == 200
        assert resp.json()[0]["user_id"] == created_user["id"]

    def test_unknown_user(self, client):
        response = client.get("/api/users/9999/transactions/")
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_empty_list_for_new_user(self, client, created_user):
        resp = client.get(f"/api/users/{created_user['id']}/transactions/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPatchUser:
    @pytest.mark.unit
    def test_patch_user_returns_200_when_payload_is_valid(self, client, created_user):
        payload = {
            "user_id": created_user["id"],
            "username": "alice_updated",
            "email": "alice.updated@example.com",
            "phone_no": "1234567890",
            "image_file_name": "avatar.png",
        }

        resp = client.patch("/api/users/", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"id": created_user["id"], "username": "alice_updated"}

    @pytest.mark.unit
    def test_patch_user_returns_404_when_user_does_not_exist(self, client):
        payload = {
            "user_id": 9999,
            "username": "ghost",
            "email": "ghost@example.com",
        }

        resp = client.patch("/api/users/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    def test_patch_user_returns_422_when_required_field_is_missing(
        self, client, created_user
    ):
        payload = {
            "user_id": created_user["id"],
            "username": "alice_updated",
        }

        resp = client.patch("/api/users/", json=payload)

        assert resp.status_code == 422


class TestDeleteUser:
    @pytest.mark.unit
    def test_delete_user_returns_204_when_user_exists(self, client, created_user):
        resp = client.delete(f"/api/users/?user_id={created_user['id']}")

        assert resp.status_code == 204
        assert resp.content == b""

        users_resp = client.get("/api/users/")
        assert users_resp.status_code == 200
        assert all(u["id"] != created_user["id"] for u in users_resp.json())

    @pytest.mark.unit
    def test_delete_user_returns_404_when_user_does_not_exist(self, client):
        resp = client.delete("/api/users/?user_id=9999")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    def test_delete_user_returns_422_when_user_id_query_param_is_missing(self, client):
        resp = client.delete("/api/users/")

        assert resp.status_code == 422


class TestPatchTransaction:
    @pytest.mark.unit
    def test_patch_transaction_returns_200_when_payload_is_valid(
        self, client, created_transaction
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": created_transaction["user_id"],
            "instrument": "NVDA",
            "units": 42,
            "rate": 321.5,
        }

        resp = client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_transaction["id"]
        assert data["user_id"] == created_transaction["user_id"]
        assert data["instrument"] == "NVDA"
        assert data["units"] == 42
        assert data["rate"] == "321.5000"

    @pytest.mark.unit
    def test_patch_transaction_returns_404_when_user_does_not_exist(
        self, client, created_transaction
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": 9999,
            "instrument": "NVDA",
        }

        resp = client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    def test_patch_transaction_returns_404_when_transaction_does_not_exist(
        self, client, created_user
    ):
        payload = {
            "id": 9999,
            "user_id": created_user["id"],
            "instrument": "NVDA",
        }

        resp = client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    def test_patch_transaction_returns_422_when_payload_contains_extra_fields(
        self, client, created_transaction
    ):
        payload = {
            "id": created_transaction["id"],
            "user_id": created_transaction["user_id"],
            "instrument": "NVDA",
            "unknown_field": "should_fail",
        }

        resp = client.patch("/api/transactions/", json=payload)

        assert resp.status_code == 422


class TestDeleteTransaction:
    @pytest.mark.unit
    def test_delete_transaction_returns_204_when_user_owns_transaction(
        self, client, created_transaction
    ):
        resp = client.delete(
            f"/api/transactions/?user_id={created_transaction['user_id']}"
            f"&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 204
        assert resp.content == b""

        get_resp = client.get(f"/api/transactions/{created_transaction['id']}")
        assert get_resp.status_code == 404
        assert get_resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    def test_delete_transaction_returns_404_when_user_does_not_exist(
        self, client, created_transaction
    ):
        resp = client.delete(
            f"/api/transactions/?user_id=9999&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 404
        assert resp.json() == {"detail": "User not found"}

    @pytest.mark.unit
    def test_delete_transaction_returns_404_when_transaction_does_not_exist(
        self, client, created_user
    ):
        resp = client.delete(
            f"/api/transactions/?user_id={created_user['id']}&trx_id=9999"
        )

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Transaction not found"}

    @pytest.mark.unit
    def test_delete_transaction_returns_400_when_transaction_does_not_belong_to_user(
        self, client, created_transaction, another_user
    ):
        resp = client.delete(
            f"/api/transactions/?user_id={another_user['id']}"
            f"&trx_id={created_transaction['id']}"
        )

        assert resp.status_code == 400
        assert resp.json() == {"detail": "Transaction does not belong to user"}

    @pytest.mark.unit
    def test_delete_transaction_returns_422_when_query_parameters_are_missing(
        self, client
    ):
        resp = client.delete("/api/transactions/")

        assert resp.status_code == 422


# -------------------- HTML ENDPOINT TESTS ------------------- #


class TestHomePageHTML:
    def test_home_page_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestUserHomePageHTML:
    def test_existing_user_renders(self, client, created_user):
        user_id = created_user["id"]
        resp = client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert created_user["username"] in resp.text  # check user data appears in HTML

    def test_unknown_user_returns_404_html(self, client):
        resp = client.get("/users/9999")
        assert resp.status_code == 404
        # Since it's not an /api/ path, it should render error.html, not JSON
        assert "text/html" in resp.headers["content-type"]


class TestUserTransactionsPageHTML:
    def test_renders_transactions(self, client, created_user, created_transaction):
        resp = client.get(f"/users/{created_user['id']}/transactions")
        assert resp.status_code == 200
        assert created_transaction["instrument"] in resp.text

    def test_unknown_user_returns_404_html(self, client):
        resp = client.get("/users/9999/transactions")
        assert resp.status_code == 404
        assert "text/html" in resp.headers["content-type"]


class TestAllTransactionsPageHTML:
    def test_renders_page(self, client):
        resp = client.get("/transactions/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
