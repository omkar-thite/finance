from typing import Annotated

from fastapi import APIRouter, status, Depends
from fastapi.exceptions import HTTPException
from utils.app_services import _recalculate_asset_from_transactions, get_user


from schema import (
    ResponseTrx,
    CreateUser,
    ResponseUser,
    PatchUser,
    CreateAsset,
    ResponseAsset,
    PatchAsset,
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
        select(models.User).options(selectinload(models.User.contact))
    )
    return result.scalars().all()


# Post: Create a user
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ResponseUser)
async def create_user(user: CreateUser, db: Annotated[AsyncSession, Depends(get_db)]):
    # Check if username exists
    result = await db.execute(
        select(models.User).where(models.User.username == user.username)
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
    new_user = models.User(
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

    user = await db.get(models.User, user_update_data.user_id)

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

    user = await db.get(models.User, user_id)

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
        select(models.Transaction).where(models.Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    return transactions


# Get user's assets
@router.get("/{user_id}/assets", response_model=list[ResponseAsset])
async def get_user_assets_api(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):

    # TODO: Get user_id from current session after implementing
    # authenticte with passed user_id

    user = await db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Asset)
        .options(selectinload(models.Asset.transactions))
        .where(models.Asset.user_id == user_id)
    )
    assets = result.scalars().all()
    return assets


# Create asset for user
@router.post("/{user_id}/assets", response_model=ResponseAsset)
async def create_user_assets_api(
    user_id: int,
    create_asset: CreateAsset,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = await db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    new_asset = models.Asset(
        instrument=create_asset.instrument,
        total_units=create_asset.total_units,
        average_rate=create_asset.average_rate,
        user_id=user.id,
    )
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset, attribute_names=["transactions"])

    return new_asset


# Patch user's asset
@router.patch("/{user_id}/assets/{asset_id}", response_model=ResponseAsset)
async def patch_user_assets_api(
    user_id: int,
    asset_id: int,
    asset_update_data: PatchAsset,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = await db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    asset = await db.get(models.Asset, asset_id)

    if not asset or asset.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if asset_update_data.id != asset_id or asset_update_data.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path and payload user/asset ids must match",
        )

    update_data = asset_update_data.model_dump(exclude_unset=True)
    if any(
        field in update_data for field in ("instrument", "total_units", "average_rate")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset holdings are derived from transactions. Patch transactions instead.",
        )

    refreshed_asset = await _recalculate_asset_from_transactions(
        db, user_id, asset.instrument
    )
    if refreshed_asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    await db.commit()
    await db.refresh(refreshed_asset)

    return refreshed_asset
