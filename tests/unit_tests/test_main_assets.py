"""
Guards: main.py
Contract: validates asset routes and transaction-driven asset recalculation behavior.
"""

from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.exceptions import HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from utils.app_services import _recalculate_asset_from_transactions
from main import app

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


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as async_client:
        yield async_client


@pytest.fixture
def created_user_payload():
    return {
        "username": "asset_user",
        "email": "asset_user@example.com",
        "image_path": "",
    }


@pytest_asyncio.fixture
async def created_user(client, created_user_payload):
    response = await client.post("/api/users/", json=created_user_payload)
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def second_user(client):
    response = await client.post(
        "/api/users/",
        json={"username": "asset_user_2", "email": "asset_user_2@example.com"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def buy_transaction_payload(created_user):
    return {
        "user_id": created_user["id"],
        "type": "buy",
        "instrument": "AAPL",
        "units": 10,
        "rate": 100.0,
    }


@pytest_asyncio.fixture
async def created_buy_transaction(client, buy_transaction_payload):
    response = await client.post("/api/transactions/", json=buy_transaction_payload)
    assert response.status_code == 201
    return response.json()


async def _get_user_assets(client: AsyncClient, user_id: int) -> list[dict]:
    response = await client.get(f"/api/users/{user_id}/assets")
    assert response.status_code == 200
    return response.json()


async def test_create_transaction_assigns_asset_id_when_buy_transaction_is_created(
    client, buy_transaction_payload, created_user
):
    response = await client.post("/api/transactions/", json=buy_transaction_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"] is not None

    assets = await _get_user_assets(client, created_user["id"])
    assert len(assets) == 1
    assert assets[0]["instrument"] == "AAPL"
    assert assets[0]["total_units"] == 10
    assert assets[0]["average_rate"] == "100.0000"


async def test_create_transaction_updates_weighted_average_when_second_buy_is_created(
    client, created_user
):
    first_buy = {
        "user_id": created_user["id"],
        "type": "buy",
        "instrument": "AAPL",
        "units": 10,
        "rate": 100.0,
    }
    second_buy = {
        "user_id": created_user["id"],
        "type": "buy",
        "instrument": "AAPL",
        "units": 10,
        "rate": 120.0,
    }

    first_response = await client.post("/api/transactions/", json=first_buy)
    second_response = await client.post("/api/transactions/", json=second_buy)

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assets = await _get_user_assets(client, created_user["id"])
    assert len(assets) == 1
    assert assets[0]["total_units"] == 20
    assert assets[0]["average_rate"] == "110.0000"


async def test_create_transaction_returns_400_when_sell_units_exceed_holdings(
    client, created_user
):
    response = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "sell",
            "instrument": "AAPL",
            "units": 1,
            "rate": 90.0,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Sell units exceed available holdings"}


async def test_patch_transaction_reassigns_asset_when_instrument_changes(
    client, created_user, created_buy_transaction
):
    patch_payload = {
        "id": created_buy_transaction["id"],
        "user_id": created_user["id"],
        "instrument": "MSFT",
        "type": "buy",
        "units": 10,
        "rate": 100.0,
    }

    response = await client.patch("/api/transactions/", json=patch_payload)

    assert response.status_code == 200
    patched = response.json()
    assert patched["instrument"] == "MSFT"
    assert patched["asset_id"] is not None

    assets = await _get_user_assets(client, created_user["id"])
    assert len(assets) == 1
    assert assets[0]["instrument"] == "MSFT"
    assert assets[0]["total_units"] == 10
    assert assets[0]["average_rate"] == "100.0000"


async def test_patch_transaction_updates_asset_when_units_change_same_instrument(
    client, created_user, created_buy_transaction
):
    patch_payload = {
        "id": created_buy_transaction["id"],
        "user_id": created_user["id"],
        "units": 25,
    }

    response = await client.patch("/api/transactions/", json=patch_payload)

    assert response.status_code == 200
    patched = response.json()
    assert patched["units"] == 25
    assert patched["asset_id"] is not None

    assets = await _get_user_assets(client, created_user["id"])
    assert len(assets) == 1
    assert assets[0]["instrument"] == "AAPL"
    assert assets[0]["total_units"] == 25
    assert assets[0]["average_rate"] == "100.0000"


async def test_get_user_assets_returns_200_with_empty_list_when_user_has_no_assets(
    client, created_user
):
    response = await client.get(f"/api/users/{created_user['id']}/assets")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_user_assets_returns_404_when_user_does_not_exist(client):
    response = await client.get("/api/users/9999/assets")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


async def test_create_user_assets_returns_200_with_asset_when_payload_is_valid(
    client, created_user
):
    payload = {
        "instrument": "GOOG",
        "total_units": 11,
        "average_rate": "152.2500",
    }

    response = await client.post(
        f"/api/users/{created_user['id']}/assets", json=payload
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == created_user["id"]
    assert body["instrument"] == "GOOG"
    assert body["total_units"] == 11
    assert body["average_rate"] == "152.2500"


async def test_create_user_assets_returns_404_when_user_does_not_exist(client):
    payload = {
        "instrument": "GOOG",
        "total_units": 11,
        "average_rate": "152.2500",
    }

    response = await client.post("/api/users/9999/assets", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


async def test_create_user_assets_returns_422_when_required_field_is_missing(
    client, created_user
):
    payload = {
        "instrument": "GOOG",
        "total_units": 11,
    }

    response = await client.post(
        f"/api/users/{created_user['id']}/assets", json=payload
    )

    assert response.status_code == 422


async def test_patch_user_assets_returns_200_with_recalculated_asset_when_ids_match(
    client, created_user, created_buy_transaction
):
    existing_asset = (await _get_user_assets(client, created_user["id"]))[0]

    payload = {
        "id": existing_asset["id"],
        "user_id": created_user["id"],
    }

    response = await client.patch(
        f"/api/users/{created_user['id']}/assets/{existing_asset['id']}",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == existing_asset["id"]
    assert body["instrument"] == "AAPL"
    assert body["total_units"] == 10
    assert body["average_rate"] == "100.0000"


async def test_patch_user_assets_returns_404_when_asset_does_not_exist(
    client, created_user
):
    payload = {
        "id": 9999,
        "user_id": created_user["id"],
    }

    response = await client.patch(
        f"/api/users/{created_user['id']}/assets/9999",
        json=payload,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


async def test_patch_user_assets_returns_400_when_path_and_payload_ids_do_not_match(
    client, created_user, created_buy_transaction
):
    existing_asset = (await _get_user_assets(client, created_user["id"]))[0]
    payload = {
        "id": existing_asset["id"] + 1,
        "user_id": created_user["id"],
    }

    response = await client.patch(
        f"/api/users/{created_user['id']}/assets/{existing_asset['id']}",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Path and payload user/asset ids must match"}


async def test_patch_user_assets_returns_400_when_holdings_fields_are_provided(
    client, created_user, created_buy_transaction
):
    existing_asset = (await _get_user_assets(client, created_user["id"]))[0]
    payload = {
        "id": existing_asset["id"],
        "user_id": created_user["id"],
        "total_units": 900,
    }

    response = await client.patch(
        f"/api/users/{created_user['id']}/assets/{existing_asset['id']}",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Asset holdings are derived from transactions. Patch transactions instead."
    }


async def test_patch_user_assets_returns_404_when_asset_belongs_to_different_user(
    client, created_user, second_user, created_buy_transaction
):
    existing_asset = (await _get_user_assets(client, created_user["id"]))[0]
    payload = {
        "id": existing_asset["id"],
        "user_id": second_user["id"],
    }

    response = await client.patch(
        f"/api/users/{second_user['id']}/assets/{existing_asset['id']}",
        json=payload,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


async def test_patch_user_assets_returns_422_when_payload_contains_extra_field(
    client, created_user, created_buy_transaction
):
    existing_asset = (await _get_user_assets(client, created_user["id"]))[0]
    payload = {
        "id": existing_asset["id"],
        "user_id": created_user["id"],
        "unknown": "value",
    }

    response = await client.patch(
        f"/api/users/{created_user['id']}/assets/{existing_asset['id']}",
        json=payload,
    )

    assert response.status_code == 422


async def test_recalculate_asset_from_transactions_raise_error_when_sell_exceeds_units(
    db_session, created_user, client
):
    buy_response = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument": "NFLX",
            "units": 1,
            "rate": 10.0,
        },
    )
    assert buy_response.status_code == 201

    await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "sell",
            "instrument": "NFLX",
            "units": 1,
            "rate": 10.0,
        },
    )

    over_sell_response = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "sell",
            "instrument": "NFLX",
            "units": 1,
            "rate": 10.0,
        },
    )
    assert over_sell_response.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await _recalculate_asset_from_transactions(
            db_session, created_user["id"], "NFLX"
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "Sell units exceed available holdings"


async def test_recalculate_asset_from_transactions_returns_none_when_all_units_are_sold(
    client, created_user
):
    buy_response = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument": "ORCL",
            "units": 3,
            "rate": 50.0,
        },
    )
    assert buy_response.status_code == 201

    sell_response = await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "sell",
            "instrument": "ORCL",
            "units": 3,
            "rate": 70.0,
        },
    )
    assert sell_response.status_code == 201

    assets_response = await client.get(f"/api/users/{created_user['id']}/assets")
    assert assets_response.status_code == 200
    assert assets_response.json() == []


async def test_get_user_assets_returns_instrument_snapshot_when_multiple_assets_exist(
    client, created_user
):
    await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument": "AAPL",
            "units": 2,
            "rate": 101.0,
        },
    )
    await client.post(
        "/api/transactions/",
        json={
            "user_id": created_user["id"],
            "type": "buy",
            "instrument": "MSFT",
            "units": 3,
            "rate": 201.0,
        },
    )

    response = await client.get(f"/api/users/{created_user['id']}/assets")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    instruments = {item["instrument"] for item in body}
    assert instruments == {"AAPL", "MSFT"}


async def test_create_user_assets_stores_decimal_exactly_when_decimal_string_is_supplied(
    client, created_user
):
    payload = {
        "instrument": "AMZN",
        "total_units": 7,
        "average_rate": str(Decimal("99.1250")),
    }

    response = await client.post(
        f"/api/users/{created_user['id']}/assets", json=payload
    )

    assert response.status_code == 200
    assert response.json()["average_rate"] == "99.1250"
