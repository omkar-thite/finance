from typing import Annotated

from fastapi import APIRouter, UploadFile, status, Depends, File, Query, BackgroundTasks

from fastapi.exceptions import HTTPException
from utils.app_services import update_user_holdings, get_user


from schema import (
    ResponseTrx,
    CreateUser,
    UserPrivate,
    UserPublic,
    PatchUser,
    CreateHoldings,
    ResponseHoldings,
    PatchHoldings,
    Token,
    PaginatedTransactions,
    PaginatedHoldings,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangedPasswordRequest,
)

from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from utils.error_messages import ErrorMessages


from datetime import UTC, datetime, timedelta
from fastapi.security import OAuth2PasswordRequestForm
from auth import (
    create_access_token,
    hash_password,
    CurrentUser,
    verify_password,
    hash_reset_token,
    generate_reset_token,
)
from config import settings
from PIL import UnidentifiedImageError
from utils.image_utils import process_profile_image, delete_profile_image
from fastapi.concurrency import run_in_threadpool
from email_utils import send_password_reset_email

router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Look up user by email (case insensitive)
    result = await db.execute(
        select(models.UserContact.user_id).where(
            func.lower(models.UserContact.email) == form_data.username.lower()
        )
    )

    user_id = result.scalars().first()
    password_hash = await db.execute(
        select(models.UserAuth.password_hash).where(models.UserAuth.user_id == user_id)
    )
    password_hash = password_hash.scalars().first()

    # Verify user exists and password is correct
    if not password_hash or not verify_password(form_data.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # create and access token with user id as subject
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user_id)},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


# Get current user
@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password_api(
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == request_data.email.lower()
        )
    )
    user = result.scalars().first()

    if user:
        # Delete existing reset tokens for the user (if any)
        await db.execute(
            sql_delete(models.PasswordResetToken).where(
                models.PasswordResetToken.user_id == user.id
            )
        )

        # Generate reset token and save hashed version in db
        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.reset_token_expire_minutes
        )

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        await db.add(reset_token)
        await db.commit()

        # Send email with reset link (including plain token)
        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            username=user.username,
            token=token,
        )

        return {
            "message": "If an account with that email exists,"
            " you will receive an password reset instructions.."
        }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password_api(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_hash = hash_reset_token(request_data.token)

    result = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash
        )
    )

    reset_token = result.scalars().first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    # Check if token has expired
    if reset_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        # Delete expired token
        await db.execute(
            sql_delete(models.PasswordResetToken).where(
                models.PasswordResetToken.id == reset_token.id
            )
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    # Check if user exists (should always exist if token is valid, but just in case)
    result = await db.execute(
        select(models.User).where(models.User.id == reset_token.user_id)
    )

    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user.password_hash = hash_password(request_data.new_password)

    # Delete all of the user reset tokens
    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == reset_token.user_id
        )
    )

    await db.commit()

    return {
        "message": "Password has been reset successfully. "
        "You can now log in with your new password."
    }


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password_api(
    password_data: ChangedPasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.auth is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User authentication record not found.",
        )

    # Verify current password is correct
    if not verify_password(
        password_data.current_password, current_user.auth.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # Verify new password is different from current password
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    # Update to new password
    current_user.auth.password_hash = hash_password(password_data.new_password)

    # Delete outstanding reset tokens for the user (if any)
    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == current_user.id
        )
    )
    await db.commit()

    return {"message": "Password changed successfully."}


# Get user by id
@router.get("/{user_id}", response_model=UserPrivate)
async def get_user_api(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's data",
        )

    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user


# Get all users
@router.get("/", response_model=list[UserPublic])
async def get_users_api(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Users).options(selectinload(models.Users.contact))
    )
    return result.scalars().all()


# Post: Create a user
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserPrivate)
async def create_user(user: CreateUser, db: Annotated[AsyncSession, Depends(get_db)]):

    # Check if username exists
    result = await db.execute(
        select(models.Users).where(
            func.lower(models.Users.username) == user.username.lower()
        )
    )
    username = result.scalars().first()

    if username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.USERNAME_EXISTS,
        )

    email_exists = await db.execute(
        select(models.UserContact).where(
            func.lower(models.UserContact.email) == user.email.lower()
        )
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
    userauth = models.UserAuth(password_hash=hash_password(user.password))

    new_user = models.Users(
        username=user.username.lower(),
        contact=new_contact,
        auth=userauth,
        image_file_name=user.image_file_name,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user, attribute_names=["contact", "auth"])

    return UserPrivate.model_validate(new_user)


# Patch: Update a user
@router.patch("/", status_code=status.HTTP_200_OK, response_model=UserPrivate)
async def patch_user(
    user_update_data: PatchUser,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.get(models.Users, current_user.id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    normalized_username = user_update_data.username.strip().lower()
    username_result = await db.execute(
        select(models.Users.id).where(
            func.lower(models.Users.username) == normalized_username,
            models.Users.id != current_user.id,
        )
    )
    username_exists = username_result.scalars().first()
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.USERNAME_EXISTS,
        )

    normalized_email = user_update_data.email.strip().lower()
    email_result = await db.execute(
        select(models.UserContact.user_id).where(
            func.lower(models.UserContact.email) == normalized_email,
            models.UserContact.user_id != current_user.id,
        )
    )
    email_exists = email_result.scalars().first()

    phone_exists = None
    if user_update_data.phone_no:
        phone_result = await db.execute(
            select(models.UserContact.user_id).where(
                models.UserContact.phone_no == user_update_data.phone_no,
                models.UserContact.user_id != current_user.id,
            )
        )
        phone_exists = phone_result.scalars().first()

    if email_exists or phone_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.EMAIL_OR_PHONE_EXISTS,
        )

    user.username = normalized_username

    contact_result = await db.execute(
        select(models.UserContact).where(models.UserContact.user_id == current_user.id)
    )
    contact = contact_result.scalars().first()

    if contact is None:
        contact = models.UserContact(
            user_id=current_user.id,
            email=user_update_data.email,
            phone_no=user_update_data.phone_no,
        )
        db.add(contact)
    else:
        contact.email = normalized_email
        contact.phone_no = user_update_data.phone_no

    # Commit post to database
    await db.commit()
    await db.refresh(user, attribute_names=["contact"])

    return UserPrivate.model_validate(user)


# Delete: Delete a user
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # ownership check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    old_filename = user.image_file_name

    await db.delete(user)
    await db.commit()

    if old_filename:
        delete_profile_image(old_filename)


# Get all transaction of specific user
@router.get("/{user_id}/transactions", response_model=PaginatedTransactions)
async def get_user_transactions_api(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=10)] = 10,
):
    # ownership check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's transactions",
        )

    user = await get_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    count = await db.execute(
        select(func.count(models.Transactions.id)).where(
            models.Transactions.user_id == user_id
        )
    )
    total = count.scalar() or 0

    result = await db.execute(
        select(models.Transactions)
        .options(
            selectinload(models.Transactions.instrument_rel),
        )
        .where(models.Transactions.user_id == user_id)
        .order_by(models.Transactions.date_created.desc())
        .offset(skip)
        .limit(limit)
    )
    transactions = result.scalars().all()
    has_more = skip + len(transactions) < total

    return PaginatedTransactions(
        transactions=[ResponseTrx.model_validate(tx) for tx in transactions],
        total=total,
        skip=skip,
        has_more=has_more,
        limit=limit,
    )


# Get user's holdings
@router.get("/{user_id}/holdings", response_model=PaginatedHoldings)
async def get_user_assets_api(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=10)] = 10,
):

    # ownership check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's holdings",
        )

    user = await db.get(models.Users, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    count = await db.execute(
        select(func.count(models.Holdings.instrument_id)).where(
            models.Holdings.user_id == user_id
        )
    )
    total = count.scalar() or 0

    result = await db.execute(
        select(models.Holdings)
        .options(
            selectinload(models.Holdings.transactions),
            selectinload(models.Holdings.instrument_rel),
        )
        .where(models.Holdings.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    holdings = result.scalars().all()
    has_more = skip + len(holdings) < total

    return PaginatedHoldings(
        holdings=[ResponseHoldings.model_validate(h) for h in holdings],
        total=total,
        skip=skip,
        has_more=has_more,
        limit=limit,
    )


# Create holding for user
@router.post("/{user_id}/holdings", response_model=ResponseHoldings)
async def create_user_holdings_api(
    user_id: int,
    create_holding: CreateHoldings,
    db: Annotated[AsyncSession, Depends(get_db)],
):

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
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):

    # ownership check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's holdings",
        )

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


@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def update_profile_picture_api(
    user_id: int,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Only original user is allowed to update the profile picture
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user.",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is"
            f"{settings.max_upload_size_bytes // (1024 * 1024)} MB.",
        )

    try:
        new_filename = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image.",
        ) from err

    old_filename = current_user.image_file_name
    current_user.image_file_name = new_filename

    await db.commit()
    await db.refresh(current_user, attribute_names=["contact"])

    if old_filename:
        await run_in_threadpool(delete_profile_image, old_filename)

    return current_user


@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture_api(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Only original user is allowed to delete the profile picture
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user.",
        )

    old_filename = current_user.image_file_name

    if not old_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete.",
        )

    current_user.image_file_name = None

    await db.commit()
    await db.refresh(current_user, attribute_names=["contact"])

    await run_in_threadpool(delete_profile_image, old_filename)

    return current_user
