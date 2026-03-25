from typing import Annotated

from fastapi import APIRouter, status, Depends
from fastapi.exceptions import HTTPException
from utils.app_services import update_user_holdings, get_user


from schema import (
    ResponseTrx,
    CreateUser,
    ResponseUser,
    PatchUser,
    CreateHoldings,
    ResponseHoldings,
    PatchHoldings,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from utils.error_messages import ErrorMessages

router = APIRouter()


# Get user by id
@router.get("/{user_id}", response_model=ResponseUser)
async def get_user_api(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.User.NOT_FOUND
        )
    return user


# Get all users
@router.get("/", response_model=list[ResponseUser])
async def get_users_api(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Users).options(selectinload(models.Users.contact))
    )
    return result.scalars().all()


# Post: Create a user
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ResponseUser)
async def create_user(user: CreateUser, db: Annotated[AsyncSession, Depends(get_db)]):
    # Check if username exists
    result = await db.execute(
        select(models.Users).where(models.Users.username == user.username)
    )
    username = result.scalars().first()

    if username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.USERNAME_EXISTS,
        )

    email_exists = await db.execute(
        select(models.UserContact).where(models.UserContact.email == user.email)
    )
    email_exists = email_exists.scalars().first()

    phone_exists = None
    if user.phone_no is not None:
        phone_exists = await db.execute(
            select(models.UserContact).where(
                models.UserContact.phone_no == user.phone_no
            )
        )
        phone_exists = phone_exists.scalars().first()

    if email_exists or phone_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.EMAIL_OR_PHONE_EXISTS,
        )

    new_contact = models.UserContact(email=user.email, phone_no=user.phone_no)
    new_user = models.Users(
        username=user.username,
        contact=new_contact,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


# Patch: Update a user
@router.patch("/", status_code=status.HTTP_200_OK, response_model=ResponseUser)
async def patch_user(
    user_update_data: PatchUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    # TODO: Extract user id from current session
    # user_id = ...

    user = await db.get(models.Users, user_update_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    update_data = user_update_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    # Commit post to database
    await db.commit()
    await db.refresh(user)

    return user


# Delete: Delete a user
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    # TODO: Extract user id from current session
    # user_id = ...

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    await db.delete(user)
    await db.commit()


# Get all transaction of specific user
@router.get("/{user_id}/transactions", response_model=list[ResponseTrx])
async def get_user_transactions_api(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await get_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Transactions).where(models.Transactions.user_id == user_id)
    )
    transactions = result.scalars().all()

    return transactions


# Get user's holdings
@router.get("/{user_id}/holdings", response_model=list[ResponseHoldings])
async def get_user_assets_api(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):

    # TODO: Get user_id from current session after implementing
    # authenticte with passed user_id

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Holdings)
        .options(selectinload(models.Holdings.transactions))
        .where(models.Holdings.user_id == user_id)
    )
    holdings = result.scalars().all()
    return holdings


# Create holding for user
@router.post("/{user_id}/holdings", response_model=ResponseHoldings)
async def create_user_holdings_api(
    user_id: int,
    create_holding: CreateHoldings,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    new_holding = models.Holdings(
        instrument_id=create_holding.instrument_id,
        quantity=create_holding.quantity,
        average_rate=create_holding.average_rate,
        user_id=user.id,
    )
    db.add(new_holding)
    await db.commit()
    await db.refresh(new_holding, attribute_names=["transactions"])

    return new_holding


# Patch user's holding
@router.patch("/{user_id}/holdings/{holding_id}", response_model=ResponseHoldings)
async def patch_user_holdings_api(
    user_id: int,
    holding_id: int,
    holding_update_data: PatchHoldings,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    holding = await db.get(models.Holdings, (user_id, holding_id))

    if not holding or holding.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    update_data = holding_update_data.model_dump(exclude_unset=True)
    if any(
        field in update_data for field in ("instrument", "total_units", "average_rate")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Holding holdings are derived from transactions. "
            "Patch transactions instead.",
        )

    refreshed_holding = await update_user_holdings(db, user_id, holding.instrument_id)
    if refreshed_holding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    await db.commit()
    await db.refresh(refreshed_holding)

    return refreshed_holding
