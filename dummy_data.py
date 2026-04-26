import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import delete, select

import models
from database import AsyncSessionLocal, engine
from main import app
from utils.enums import InstrumentType

USERS = [
    {
        "username": "alpha_investor",
        "email": "alpha@example.com",
        "password": "   ",
    },
    {
        "username": "beta_trader",
        "email": "beta@example.com",
        "password": "TestPassword2!",
    },
    {
        "username": "gamma_holder",
        "email": "gamma@example.com",
        "password": "TestPassword3!",
    },
    {
        "username": "delta_quant",
        "email": "delta@example.com",
        "password": "TestPassword4!",
    },
]

INSTRUMENTS = [
    {
        "symbol": "RELIANCE",
        "name": "Reliance Industries",
        "type_": InstrumentType.EQ,
    },
    {
        "symbol": "INFY",
        "name": "Infosys",
        "type_": InstrumentType.EQ,
    },
    {
        "symbol": "NIFTYBEES",
        "name": "Nippon India ETF Nifty BeES",
        "type_": InstrumentType.ETF,
    },
    {
        "symbol": "HDFCBANK",
        "name": "HDFC Bank",
        "type_": InstrumentType.EQ,
    },
    {
        "symbol": "ICICIBANK",
        "name": "ICICI Bank",
        "type_": InstrumentType.EQ,
    },
]

TRANSACTIONS_PER_USER = 18
PROFILE_PICS_DIR = None


async def clear_existing_data() -> None:
    if PROFILE_PICS_DIR:
        for file in PROFILE_PICS_DIR.iterdir():
            if file.is_file() and file.name != ".gitkeep":
                file.unlink()

    async with AsyncSessionLocal() as db:
        await db.execute(delete(models.Holdings))
        await db.execute(delete(models.Transactions))
        await db.execute(delete(models.UserBankDetails))
        await db.execute(delete(models.UserContact))
        await db.execute(delete(models.UserAuth))
        await db.execute(delete(models.Users))
        await db.execute(delete(models.Instruments))
        await db.commit()

    print("Cleared existing users, transactions, holdings, and instruments")


async def create_instruments() -> list[int]:
    instrument_ids: list[int] = []

    async with AsyncSessionLocal() as db:
        for payload in INSTRUMENTS:
            instrument = models.Instruments(
                symbol=payload["symbol"],
                name=payload["name"],
                type_=payload["type_"],
            )
            db.add(instrument)

        await db.commit()

        for payload in INSTRUMENTS:
            result = await db.execute(
                select(models.Instruments.id).where(
                    models.Instruments.symbol == payload["symbol"]
                )
            )
            instrument_id = result.scalar_one_or_none()
            if instrument_id is None:
                continue
            instrument_ids.append(instrument_id)

    print(f"Created {len(instrument_ids)} instruments")
    return instrument_ids


async def create_users_and_tokens(client: httpx.AsyncClient) -> list[dict]:
    users: list[dict] = []

    for user_data in USERS:
        create_user_resp = await client.post(
            "/api/users/",
            json={
                "username": user_data["username"],
                "email": user_data["email"],
                "password": user_data["password"],
            },
        )
        create_user_resp.raise_for_status()
        created_user = create_user_resp.json()

        login_resp = await client.post(
            "/api/users/token",
            data={
                "username": user_data["email"],
                "password": user_data["password"],
            },
        )
        login_resp.raise_for_status()
        token = login_resp.json()["access_token"]

        users.append(
            {
                "id": created_user["id"],
                "username": created_user["username"],
                "token": token,
            }
        )

        print(f"Created user: {created_user['username']}")

    return users


def build_transaction_payload(
    user_id: int,
    instrument_id: int,
    transaction_index: int,
    user_index: int,
) -> dict:
    trade_date = date.today() - timedelta(
        days=(TRANSACTIONS_PER_USER - transaction_index) + (user_index * 2)
    )
    units = 5 + ((transaction_index + user_index) % 9)
    rate = 90 + (transaction_index * 3) + (user_index * 2)
    charges = (transaction_index % 4) * 1.25

    return {
        "user_id": user_id,
        "type_": "buy",
        "instrument_id": instrument_id,
        "units": units,
        "rate": f"{rate:.2f}",
        "charges": f"{charges:.2f}",
        "date_created": trade_date.isoformat(),
    }


async def create_transactions(
    client: httpx.AsyncClient,
    users: list[dict],
    instrument_ids: list[int],
) -> None:
    total_created = 0

    for user_index, user in enumerate(users):
        print(f"Creating {TRANSACTIONS_PER_USER} transactions for {user['username']}")

        for transaction_index in range(TRANSACTIONS_PER_USER):
            instrument_id = instrument_ids[
                (transaction_index + user_index) % len(instrument_ids)
            ]
            payload = build_transaction_payload(
                user_id=user["id"],
                instrument_id=instrument_id,
                transaction_index=transaction_index,
                user_index=user_index,
            )

            create_trx_resp = await client.post(
                "/api/transactions/",
                json=payload,
            )
            create_trx_resp.raise_for_status()
            total_created += 1

    print(f"Created {total_created} transactions in total")


async def populate() -> None:
    started_at = datetime.now(UTC)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://localhost",
    ) as client:
        await clear_existing_data()
        instrument_ids = await create_instruments()

        if not instrument_ids:
            raise RuntimeError("No instruments were created. Aborting seeding.")

        users = await create_users_and_tokens(client)
        await create_transactions(client, users, instrument_ids)

    await engine.dispose()

    elapsed = datetime.now(UTC) - started_at
    print("Done seeding dummy data")
    print(f"Users: {len(USERS)}")
    print(f"Transactions per user: {TRANSACTIONS_PER_USER}")
    print(f"Total transactions: {len(USERS) * TRANSACTIONS_PER_USER}")
    print(f"Elapsed: {elapsed.total_seconds():.2f}s")


if __name__ == "__main__":
    asyncio.run(populate())
