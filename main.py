from typing import Annotated

from fastapi import FastAPI, Request, status, Depends
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from utils.enums import TrxTypeEnum
from decimal import Decimal

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
from sqlalchemy.orm import Session

import models
from database import engine, get_db, Base

from utils.error_messages import ErrorMessages

# Create tables if not exists
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")


def get_user(db: Session, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


def _recalculate_asset_from_transactions(
    db: Session, user_id: int, instrument: str
) -> models.Asset | None:
    # Get user's transactions with current instrument
    transactions = (
        db.execute(
            select(models.Transaction)
            .where(
                models.Transaction.user_id == user_id,
                models.Transaction.instrument == instrument,
            )
            .order_by(models.Transaction.id)
        )
        .scalars()
        .all()
    )

    asset = (
        db.execute(
            select(models.Asset).where(
                models.Asset.user_id == user_id,
                models.Asset.instrument == instrument,
            )
        )
        .scalars()
        .first()
    )

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
            db.delete(asset)
            db.flush()
        return None

    if asset is None:
        asset = models.Asset(
            instrument=instrument,
            total_units=total_units,
            average_rate=average_rate,
            user_id=user_id,
        )
        db.add(asset)
        db.flush()
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
def user_home_page(
    request: Request, user_id: int, db: Annotated[Session, Depends(get_db)]
):
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = db.execute(
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
def all_transactions_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Transaction))
    transactions = result.scalars().all()
    return templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# User transactions page
@app.get(
    "/users/{user_id}/transactions", include_in_schema=False, name="user_transactions"
)
def user_transactions_page(
    request: Request, user_id: int, db: Annotated[Session, Depends(get_db)]
):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )
    result = db.execute(
        select(models.Transaction).where(models.Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    return templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# --------------- API ENDPOINTS -------------------------#


# Get user by id
@app.get("/api/users/{id}", response_model=ResponseUser)
def get_user_api(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.User.NOT_FOUND
        )
    return user


# Get all users
@app.get("/api/users/", response_model=list[ResponseUser])
def get_users_api(db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(models.User)).scalars().all()


# Post: Create a user
@app.post(
    "/api/users/", status_code=status.HTTP_201_CREATED, response_model=ResponseUser
)
def create_user(user: CreateUser, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(
        select(models.User).where(models.User.username == user.username)
    )
    username = result.scalars().first()

    if username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.User.USERNAME_EXISTS,
        )

    email_exists = (
        db.execute(
            select(models.UserContact).where(models.UserContact.email == user.email)
        )
        .scalars()
        .first()
    )

    phone_exists = None
    if user.phone_no is not None:
        phone_exists = (
            db.execute(
                select(models.UserContact).where(
                    models.UserContact.phone_no == user.phone_no
                )
            )
            .scalars()
            .first()
        )

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
    db.commit()
    db.refresh(new_user)

    return new_user


# Patch: Update a user
@app.patch("/api/users/", status_code=status.HTTP_200_OK, response_model=ResponseUser)
def patch_user(user_update_data: PatchUser, db: Annotated[Session, Depends(get_db)]):
    # TODO: Extract user id from current session
    # user_id = ...

    user = db.get(models.User, user_update_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    update_data = user_update_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    # Commit post to database
    db.commit()
    db.refresh(user)

    return user


# Delete: Delete a user
@app.delete("/api/users/", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Annotated[Session, Depends(get_db)]):

    # TODO: Extract user id from current session
    # user_id = ...

    user = db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    db.delete(user)
    db.commit()


# Get transaction by id
@app.get("/api/transactions/{id}", response_model=ResponseTrx)
def get_transaction_api(id: int, db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Transaction).where(models.Transaction.id == id))
    tx = result.scalars().first()

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.Transaction.NOT_FOUND,
        )
    return tx


# Get all transaction of specific user
@app.get("/api/users/{user_id}/transactions", response_model=list[ResponseTrx])
def get_user_transactions_api(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = get_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = db.execute(
        select(models.Transaction).where(models.Transaction.user_id == user_id)
    )
    transactions = result.scalars().all()

    return transactions


# Get all transactions from table
@app.get("/api/transactions/", response_model=list[ResponseTrx])
def get_all_transactions_api(db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Transaction))
    txs = result.scalars().all()
    return txs


# Post: Create a transaction
@app.post(
    "/api/transactions/",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseTrx,
)
def create_transaction_api(trx: CreateTrx, db: Annotated[Session, Depends(get_db)]):
    user = get_user(db, trx.user_id)

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
    )
    db.add(new_trx)
    db.flush()

    asset = _recalculate_asset_from_transactions(db, user.id, trx.instrument)
    new_trx.asset_id = asset.id if asset else None

    db.commit()
    db.refresh(new_trx)

    return new_trx


# Patch: Update a transaction
@app.patch(
    "/api/transactions/", status_code=status.HTTP_200_OK, response_model=ResponseTrx
)
def patch_trx(trx_update_data: PatchTrx, db: Annotated[Session, Depends(get_db)]):
    # TODO: Get user id from session
    # user_id =

    # TODO: Authnticate user id with session user id
    # ...

    user = db.get(models.User, trx_update_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = db.get(models.Transaction, trx_update_data.id)

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

    for field, value in update_data.items():
        setattr(trx, field, value)

    db.flush()

    if old_instrument != trx.instrument:
        _recalculate_asset_from_transactions(db, trx.user_id, old_instrument)

    current_asset = _recalculate_asset_from_transactions(
        db, trx.user_id, trx.instrument
    )
    trx.asset_id = current_asset.id if current_asset else None

    # Commit post to database
    db.commit()
    db.refresh(trx)

    return trx


# Delete: Delete a transaction
@app.delete("/api/transactions/", status_code=status.HTTP_204_NO_CONTENT)
def delete_trx(user_id: int, trx_id: int, db: Annotated[Session, Depends(get_db)]):

    # TODO: Extract user id from current session
    # user_id = ...

    user = db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    trx = db.get(models.Transaction, trx_id)
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

    db.delete(trx)
    db.flush()

    _recalculate_asset_from_transactions(db, user_id, instrument)

    db.commit()


@app.get("/api/users/{user_id}/assets", response_model=list[ResponseAsset])
def get_user_assets_api(user_id: int, db: Annotated[Session, Depends(get_db)]):

    # TODO: Get user_id from current session after implementing
    # authenticte with passed user_id

    user = db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = db.execute(select(models.Asset).where(models.Asset.user_id == user_id))
    assets = result.scalars().all()

    return assets


@app.post("/api/users/{user_id}/assets", response_model=ResponseAsset)
def create_user_assets_api(
    user_id: int, create_asset: CreateAsset, db: Annotated[Session, Depends(get_db)]
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = db.get(models.User, user_id)

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
    db.commit()
    db.refresh(new_asset)

    return new_asset


@app.patch("/api/users/{user_id}/assets/{asset_id}", response_model=ResponseAsset)
def patch_user_assets_api(
    user_id: int,
    asset_id: int,
    asset_update_data: PatchAsset,
    db: Annotated[Session, Depends(get_db)],
):

    # TODO: Get user_id from current session after implementing authenticte with passed user_id

    user = db.get(models.User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    asset = db.get(models.Asset, asset_id)

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

    refreshed_asset = _recalculate_asset_from_transactions(
        db, user_id, asset.instrument
    )
    if refreshed_asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    db.commit()
    db.refresh(refreshed_asset)

    return refreshed_asset


# --------- EXCEPTION HANDLERS --------------------------#


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.detail or "Not found"},
        )
    return templates.TemplateResponse(
        request,
        name="error.html",
        status_code=status.HTTP_404_NOT_FOUND,
        context={
            "status_code": status.HTTP_404_NOT_FOUND,
            "message": exc.detail or ErrorMessages.PAGE_NOT_FOUND,
        },
    )
