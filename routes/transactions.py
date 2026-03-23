from typing import Annotated

from fastapi import status, Depends, APIRouter
from fastapi.exceptions import HTTPException

from schema import (
    CreateTrx,
    ResponseTrx,
    PatchTrx,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from utils.error_messages import ErrorMessages

from utils.app_services import _recalculate_asset_from_transactions, get_user

router = APIRouter()


# Get transaction by id
@router.get("/{id}", response_model=ResponseTrx)
async def get_transaction_api(id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(
        select(models.Transaction).where(models.Transaction.id == id)
    )
    tx = result.scalars().first()

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.Transaction.NOT_FOUND,
        )

    return tx


# Get all transactions from table
@router.get("/", response_model=list[ResponseTrx])
async def get_all_transactions_api(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Transaction))
    txs = result.scalars().all()
    return txs


# Post: Create a transaction
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseTrx,
)
async def create_transaction_api(
    trx: CreateTrx, db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await get_user(db, trx.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    new_trx = models.Transaction(
        type=trx.type,
        instrument=trx.instrument,
        units=trx.units,
        rate=trx.rate,
        user_id=user.id,
        charges=trx.charges,
    )
    db.add(new_trx)
    await db.flush()

    asset = await _recalculate_asset_from_transactions(db, user.id, trx.instrument)
    new_trx.asset_id = asset.id if asset else None

    await db.commit()
    await db.refresh(new_trx)

    return new_trx


# Patch: Update a transaction
@router.patch("/", status_code=status.HTTP_200_OK, response_model=ResponseTrx)
async def patch_trx(
    trx_update_data: PatchTrx, db: Annotated[AsyncSession, Depends(get_db)]
):
    # TODO: Get user id from session
    # user_id =

    # TODO: Authnticate user id with session user id
    # ...

    user = await db.get(models.User, trx_update_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = await db.get(models.Transaction, trx_update_data.id)

    if not trx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.Transaction.NOT_FOUND,
        )

    if trx.user_id != trx_update_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.Transaction.USER_NOT_OWNER,
        )

    old_instrument = trx.instrument

    update_data = trx_update_data.model_dump(
        exclude_unset=True,
        exclude={"id", "user_id"},
    )

    # Update fields of transaction with new values
    for field, value in update_data.items():
        setattr(trx, field, value)

    await db.flush()

    # change asset's holdings for old instrument if instrument is updated in transaction
    if old_instrument != trx.instrument:
        await _recalculate_asset_from_transactions(db, trx.user_id, old_instrument)

    # change asset's holdings for new instrument
    current_asset = await _recalculate_asset_from_transactions(
        db, trx.user_id, trx.instrument
    )
    trx.asset_id = current_asset.id if current_asset else None

    # Commit post to database
    await db.commit()
    await db.refresh(trx)

    return trx


# Delete: Delete a transaction
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trx(
    user_id: int, trx_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):

    # TODO: Extract user id from current session
    # user_id = ...

    user = await db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = await db.get(models.Transaction, trx_id)
    if not trx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.Transaction.NOT_FOUND,
        )

    if trx.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.Transaction.USER_NOT_OWNER,
        )

    instrument = trx.instrument

    await db.delete(trx)
    await db.flush()

    await _recalculate_asset_from_transactions(db, user_id, instrument)
    await db.commit()
