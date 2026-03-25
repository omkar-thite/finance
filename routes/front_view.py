from typing import Annotated

from fastapi import APIRouter, Request, status, Depends
from fastapi.exceptions import HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from utils.error_messages import ErrorMessages

router = APIRouter()


@router.get("/", name="home", include_in_schema=False)
def home_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, name="home.html")


# User home page
@router.get("/users/{user_id}", include_in_schema=False)
async def user_home_page(
    request: Request, user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.Users).where(models.Users.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Transactions).where(models.Transactions.user_id == user_id)
    )
    transactions = result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        request,
        name="user_home_page.html",
        context={"user": user, "transactions": transactions},
    )


# All transactions
@router.get("/transactions/", include_in_schema=False)
async def all_transactions_page(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.Transactions))
    transactions = result.scalars().all()
    return request.app.state.templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# User transactions page
@router.get(
    "/users/{user_id}/transactions", include_in_schema=False, name="user_transactions"
)
async def user_transactions_page(
    request: Request, user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):

    result = await db.execute(select(models.Users).where(models.Users.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )
    result = await db.execute(
        select(models.Transactions).where(models.Transactions.user_id == user_id)
    )
    transactions = result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )
