from fastapi import status
from fastapi.exceptions import HTTPException
from utils.enums import TrxTypeEnum
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models


async def get_user(db: AsyncSession, user_id: int) -> models.User | None:
    return await db.get(models.User, user_id)


async def _recalculate_asset_from_transactions(
    db: AsyncSession, user_id: int, instrument: str
) -> models.Asset | None:

    # Get user's transactions with input instrument
    transactions = await db.execute(
        select(models.Transaction)
        .options(
            selectinload(models.Transaction.user),
            selectinload(models.Transaction.asset),
        )
        .where(
            models.Transaction.user_id == user_id,
            models.Transaction.instrument == instrument,
        )
        .order_by(models.Transaction.id)
    )
    transactions = transactions.scalars().all()

    if not transactions:
        # When an instrument has no transactions left (e.g. after patch/delete),
        # remove any stale asset snapshot for that instrument.
        asset_result = await db.execute(
            select(models.Asset).where(
                models.Asset.user_id == user_id,
                models.Asset.instrument == instrument,
            )
        )
        stale_asset = asset_result.scalars().first()
        if stale_asset is not None:
            await db.delete(stale_asset)
            await db.flush()
        return None

    # Get current insturment asset of user
    asset = await db.execute(
        select(models.Asset)
        .options(selectinload(models.Asset.transactions))
        .where(
            models.Asset.user_id == user_id,
            models.Asset.instrument == instrument,
        )
    )
    asset = asset.scalars().first()

    if not asset:
        asset = None

    total_units = 0
    average_rate = Decimal("0")

    for trx in transactions:
        if trx.type == TrxTypeEnum.BUY:
            old_cost = average_rate * total_units
            new_cost = Decimal(trx.rate) * trx.units
            total_units += trx.units
            average_rate = (old_cost + new_cost) / total_units
            continue
        # SELL
        if trx.units > total_units:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sell units exceed available holdings",
            )
        total_units -= trx.units
        if total_units == 0:
            average_rate = Decimal("0")

    # Delet asset if emptied from holdings
    if total_units == 0:
        if asset is not None:
            for trx in transactions:
                trx.asset_id = None
            await db.delete(asset)
            await db.flush()
        return None

    if asset is None:
        asset = models.Asset(
            instrument=instrument,
            total_units=total_units,
            average_rate=average_rate,
            user_id=user_id,
        )
        db.add(asset)
        await db.flush()
    else:
        asset.total_units = total_units
        asset.average_rate = average_rate

    for trx in transactions:
        trx.asset_id = asset.id

    return asset
