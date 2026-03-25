"""
Guards: main.py
Contract: validates transaction routes and holdings service behavior after holdings refactor.
"""

from decimal import Decimal
from types import SimpleNamespace
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import models
from database import Base, get_db
from main import app
import routes.transactions as transactions_route
from tests.helpers.db_mocks import mock_scalar_result, mock_scalars_all
from utils.app_services import update_user_holdings

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = TestingSessionLocal(bind=connection)

        yield session

        await session.close()
        await transaction.rollback()


@pytest_asyncio.fixture(autouse=True)
async def override_get_db_dependency(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
def mock_route_holdings_update(monkeypatch):
    mock_update = AsyncMock(return_value=None)
    monkeypatch.setattr(transactions_route, "update_user_holdings", mock_update)
    return mock_update


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
            "username": "asset_user",
            "email": "asset_user@example.com",
            "image_file_name": "",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_instrument(db_session):
    instrument = models.Instruments(symbol="AAPL", type="equity", name="Apple Inc")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest_asyncio.fixture
async def second_instrument(db_session):
    instrument = models.Instruments(symbol="MSFT", type="equity", name="Microsoft")
    db_session.add(instrument)
    await db_session.flush()
    return instrument


@pytest.fixture
def buy_transaction_payload(created_user, created_instrument):
    return {
        "user_id": created_user["id"],
        "type": "buy",
        "instrument_id": created_instrument.id,
        "units": 10,
        "rate": 100.0,
    }


@pytest_asyncio.fixture
async def created_buy_transaction(client, buy_transaction_payload):
    response = await client.post("/api/transactions/", json=buy_transaction_payload)
    assert response.status_code == 201
    return response.json()


async def _get_user_holdings(client: AsyncClient, user_id: int) -> list[dict]:
    response = await client.get(f"/api/users/{user_id}/holdings")
    assert response.status_code == 200
    return response.json()


async def test_create_transaction_returns_201_when_payload_is_valid(
    client, buy_transaction_payload
):
    response = await client.post("/api/transactions/", json=buy_transaction_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "buy"
    assert body["instrument_id"] == buy_transaction_payload["instrument_id"]
    assert body["units"] == 10
    assert body["rate"] == "100.0000"


async def test_patch_transaction_updates_instrument_id_when_instrument_changes(
    client, created_user, created_buy_transaction, second_instrument
):
    patch_payload = {
        "id": 1,
        "user_id": created_user["id"],
        "instrument_id": second_instrument.id,
        "type": "buy",
        "units": 10,
        "rate": 100.0,
    }

    response = await client.patch("/api/transactions/", json=patch_payload)

    assert response.status_code == 200
    patched = response.json()
    assert patched["instrument_id"] == second_instrument.id


async def test_patch_transaction_updates_units_when_payload_contains_units(
    client, created_user, created_buy_transaction
):
    patch_payload = {
        "id": 1,
        "user_id": created_user["id"],
        "units": 25,
    }

    response = await client.patch("/api/transactions/", json=patch_payload)

    assert response.status_code == 200
    patched = response.json()
    assert patched["units"] == 25


async def test_get_user_holdings_returns_empty_list_when_user_has_no_holdings(
    client, created_user
):
    response = await client.get(f"/api/users/{created_user['id']}/holdings")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_user_holdings_returns_404_when_user_does_not_exist(client):
    response = await client.get("/api/users/9999/holdings")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


async def test_update_user_holdings_raises_400_when_sell_units_exceed_available_units():
    db = AsyncMock()
    sell_txn = SimpleNamespace(type="sell", units=1, rate=Decimal("10.0000"))

    db.execute.side_effect = [
        mock_scalars_all([sell_txn]),
        mock_scalar_result(None),
    ]

    with pytest.raises(Exception) as exc_info:
        await update_user_holdings(db, user_id=1, instrument_id=101)

    assert "Sell units exceed available holdings" in str(exc_info.value)


async def test_update_user_holdings_none_when_no_transactions_and_stale_holding():
    db = AsyncMock()
    stale_holding = SimpleNamespace(user_id=1, instrument_id=101)

    db.execute.side_effect = [
        mock_scalars_all([]),
        mock_scalar_result(stale_holding),
    ]

    result = await update_user_holdings(db, user_id=1, instrument_id=101)

    assert result is None
    db.delete.assert_awaited_once_with(stale_holding)


async def test_update_user_holdings_updates_existing_holding_when_buy_transactions_exist():
    db = AsyncMock()
    first_buy = SimpleNamespace(type="buy", units=2, rate=Decimal("100.0000"))
    second_buy = SimpleNamespace(type="buy", units=2, rate=Decimal("200.0000"))
    existing_holding = SimpleNamespace(
        user_id=1,
        instrument_id=101,
        quantity=0,
        average_rate=Decimal("0.0000"),
    )

    db.execute.side_effect = [
        mock_scalars_all([first_buy, second_buy]),
        mock_scalar_result(existing_holding),
    ]

    result = await update_user_holdings(db, user_id=1, instrument_id=101)

    assert result is existing_holding
    assert existing_holding.quantity == 4
    assert existing_holding.average_rate == Decimal("150.0000")
