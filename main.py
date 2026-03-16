from typing import Annotated

from fastapi import FastAPI, Request, status, Depends
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from schema import CreateTrx, ResponseTrx, CreateUser, ResponseUser, PatchUser, PatchTrx

from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from database import engine, get_db, Base

# Create tables if not exists
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")


def get_user(db: Session, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


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
            detail="User not found.",
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
            detail="User not found.",
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
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
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
            detail="Username already exists",
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
            detail="email/phone already exists",
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
            detail="User not found",
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
            detail="User not found",
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
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found."
        )
    return tx


# Get all transaction of specific user
@app.get("/api/users/{user_id}/transactions", response_model=list[ResponseTrx])
def get_user_transactions_api(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = get_user(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
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
            detail="User not found",
        )

    new_trx = models.Transaction(
        type=trx.type,
        instrument=trx.instrument,
        units=trx.units,
        rate=trx.rate,
        user_id=user.id,
    )
    db.add(new_trx)
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
            detail="User not found",
        )

    trx = db.get(models.Transaction, trx_update_data.id)

    if not trx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    update_data = trx_update_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(trx, field, value)

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
            detail="User not found",
        )

    trx = db.get(models.Transaction, trx_id)
    if not trx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )

    if trx.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction does not belong to user",
        )

    db.delete(trx)
    db.commit()


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
            "message": exc.detail or "Page not found",
        },
    )
