from typing import Annotated

from fastapi import FastAPI, Request, status, Depends
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from utils.enums import TrxTypeEnum
from decimal import Decimal

from contextlib import asynccontextmanager
from fastapi.exception_handlers import (
    http_exception_handler,
)
from schema import (
    CreateTrx,
    ResponseTrx,
    PatchTrx,
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
from database import engine, get_db, Base
from utils.error_messages import ErrorMessages


@asynccontextmanager
async def lifespan(_app: FastAPI):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")
templates = Jinja2Templates(directory="templates")


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


# ----------------- HTML ENDPOINTS --------------- #


@app.get("/", name="home", include_in_schema=False)
def home_page(request: Request):
    return templates.TemplateResponse(request, name="home.html")


# User home page
@app.get("/users/{user_id}", include_in_schema=False)
async def user_home_page(
    request: Request, user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Transaction).where(models.Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    return templates.TemplateResponse(
        request,
        name="user_home_page.html",
        context={"user": user, "transactions": transactions},
    )


# All transactions
@app.get("/transactions/", include_in_schema=False)
async def all_transactions_page(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.Transaction))
    transactions = result.scalars().all()
    return templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# User transactions page
@app.get(
    "/users/{user_id}/transactions", include_in_schema=False, name="user_transactions"
)
async def user_transactions_page(
    request: Request, user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )
    result = await db.execute(
        select(models.Transaction).where(models.Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    return templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# --------------- API ENDPOINTS -------------------------#


# Get user by id
@app.get("/api/users/{user_id}", response_model=ResponseUser)
async def get_user_api(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.User.NOT_FOUND
        )
    return user


# Get all users
@app.get("/api/users/", response_model=list[ResponseUser])
async def get_users_api(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.User).options(selectinload(models.User.contact))
    )
    return result.scalars().all()


# Post: Create a user
@app.post(
    "/api/users/", status_code=status.HTTP_201_CREATED, response_model=ResponseUser
)
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
@app.patch("/api/users/", status_code=status.HTTP_200_OK, response_model=ResponseUser)
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
@app.delete("/api/users/", status_code=status.HTTP_204_NO_CONTENT)
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


# Get transaction by id
@app.get("/api/transactions/{id}", response_model=ResponseTrx)
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


# Get all transaction of specific user
@app.get("/api/users/{user_id}/transactions", response_model=list[ResponseTrx])
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


# Get all transactions from table
@app.get("/api/transactions/", response_model=list[ResponseTrx])
async def get_all_transactions_api(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Transaction))
    txs = result.scalars().all()
    return txs


# Post: Create a transaction
@app.post(
    "/api/transactions/",
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
@app.patch(
    "/api/transactions/", status_code=status.HTTP_200_OK, response_model=ResponseTrx
)
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
@app.delete("/api/transactions/", status_code=status.HTTP_204_NO_CONTENT)
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


# Get user's assets
@app.get("/api/users/{user_id}/assets", response_model=list[ResponseAsset])
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
@app.post("/api/users/{user_id}/assets", response_model=ResponseAsset)
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
@app.patch("/api/users/{user_id}/assets/{asset_id}", response_model=ResponseAsset)
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


# --------- EXCEPTION HANDLERS --------------------------#


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return await http_exception_handler(request, exc)

    return templates.TemplateResponse(
        request,
        name="error.html",
        status_code=status.HTTP_404_NOT_FOUND,
        context={
            "status_code": status.HTTP_404_NOT_FOUND,
            "message": exc.detail or ErrorMessages.PAGE_NOT_FOUND,
        },
    )
