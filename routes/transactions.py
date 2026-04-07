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
from auth import CurrentUser

from utils.app_services import update_user_holdings, get_user

router = APIRouter()


# Get transaction by id
@router.get("/{id}", response_model=ResponseTrx)
async def get_transaction_api(id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(
        select(models.Transactions).where(models.Transactions.id == id)
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
    result = await db.execute(select(models.Transactions))
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

    new_trx = models.Transactions(
        type=trx.type,
        instrument_id=trx.instrument_id,
        units=trx.units,
        rate=trx.rate,
        user_id=user.id,
        charges=trx.charges,
    )
    db.add(new_trx)
    await db.flush()

    await update_user_holdings(db, user.id, trx.instrument_id)

    await db.commit()
    await db.refresh(new_trx)

    return new_trx


# Patch: Update a transaction
@router.patch("/", status_code=status.HTTP_200_OK, response_model=ResponseTrx)
async def patch_trx(
    trx_update_data: PatchTrx,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != trx_update_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's transactions",
        )

    user = await db.get(models.Users, trx_update_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = await db.get(models.Transactions, trx_update_data.id)

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

    old_instrument_id = trx.instrument_id

    update_data = trx_update_data.model_dump(
        exclude_unset=True,
        exclude={"id", "user_id"},
    )

    # Update fields of transaction with new values
    for field, value in update_data.items():
        setattr(trx, field, value)

    await db.flush()

    # change holdings for old instrument if instrument is updated in transaction
    if old_instrument_id != trx.instrument_id:
        await update_user_holdings(db, trx.user_id, old_instrument_id)

    # change holdings for new instrument
    await update_user_holdings(db, trx.user_id, trx.instrument_id)

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

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = await db.get(models.Transactions, trx_id)
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

    instrument_id = trx.instrument_id

    await db.delete(trx)
    await db.flush()

    await update_user_holdings(db, user_id, instrument_id)
    await db.commit()
