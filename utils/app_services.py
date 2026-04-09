from fastapi import status
from fastapi.exceptions import HTTPException
from utils.enums import TrxTypeEnum
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models


async def get_user(db: AsyncSession, user_id: int) -> models.Users | None:
    return await db.get(models.Users, user_id)


async def update_user_holdings(
    db: AsyncSession, user_id: int, instrument_id: int
) -> models.Holdings | None:

    # Get user's transactions with input instrument
    transactions = await db.execute(
        select(models.Transactions)
        .options(
            selectinload(models.Transactions.user),
        )
        .where(
            models.Transactions.user_id == user_id,
            models.Transactions.instrument_id == instrument_id,
        )
        .order_by(models.Transactions.id)
    )
    transactions = transactions.scalars().all()

    if not transactions:
        # When an instrument has no transactions left (e.g. after patch/delete),
        # remove any stale holdings snapshot for that instrument.
        result = await db.execute(
            select(models.Holdings).where(
                models.Holdings.user_id == user_id,
                models.Holdings.instrument_id == instrument_id,
            )
        )
        stale_holdings = result.scalars().first()
        if stale_holdings is not None:
            await db.delete(stale_holdings)
            await db.flush()
        return None

    # Get current insturment holding of user
    holding = await db.execute(
        select(models.Holdings).where(
            models.Holdings.user_id == user_id,
            models.Holdings.instrument_id == instrument_id,
        )
    )
    holding = holding.scalars().first()

    if not holding:
        holding = None

    total_units = 0
    average_rate = Decimal("0")

    for trx in transactions:
        trx_type = getattr(trx, "type_", getattr(trx, "type", None))
        if trx_type == TrxTypeEnum.BUY or trx_type == TrxTypeEnum.BUY.value:
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

    # Delete holding if emptied from holdings
    if total_units == 0:
        if holding is not None:
            await db.delete(holding)
            await db.flush()
        return None

    if holding is None:
        holding = models.Holdings(
            instrument_id=instrument_id,
            quantity=total_units,
            average_rate=average_rate,
            user_id=user_id,
        )
        db.add(holding)
        await db.flush()
    else:
        holding.quantity = total_units
        holding.average_rate = average_rate
        await db.flush()

    return holding
