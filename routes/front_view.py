from typing import Annotated

from fastapi import APIRouter, Request, status, Depends
from fastapi.exceptions import HTTPException

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from utils.error_messages import ErrorMessages
from config import is_email_configured

router = APIRouter()


@router.get("/", name="home", include_in_schema=False)
def home_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, name="home.html")


@router.get("/login", name="login_page", include_in_schema=False)
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        name="login.html",
        context={"email_configured": is_email_configured()},
    )


@router.get("/register", name="register_page", include_in_schema=False)
def register_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, name="register.html")


@router.get("/account", name="account_page", include_in_schema=False)
def account_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, name="account.html")


# User home page
@router.get("/users/{user_id}", include_in_schema=False)
async def user_home_page(
    request: Request, user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Users)
        .options(selectinload(models.Users.contact))
        .where(models.Users.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.User.NOT_FOUND,
        )

    result = await db.execute(
        select(models.Transactions)
        .options(selectinload(models.Transactions.instrument_rel))
        .where(models.Transactions.user_id == user_id)
    )
    transactions = result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        request,
        name="user_home_page.html",
        context={"user": user, "transactions": transactions},
    )


# All transactions
@router.get("/transactions/", include_in_schema=False, name="all_transactions_page")
async def all_transactions_page(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Transactions).options(
            selectinload(models.Transactions.instrument_rel)
        )
    )
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
        select(models.Transactions)
        .options(selectinload(models.Transactions.instrument_rel))
        .where(models.Transactions.user_id == user_id)
    )
    transactions = result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        request, name="transactions.html", context={"transactions": transactions}
    )


# User assets page
@router.get("/users/{user_id}/assets", include_in_schema=False, name="user_assets")
async def user_assets_page(
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
        select(models.Holdings)
        .options(
            selectinload(models.Holdings.transactions),
            selectinload(models.Holdings.instrument_rel),
        )
        .where(models.Holdings.user_id == user_id)
    )
    assets = result.scalars().all()

    return request.app.state.templates.TemplateResponse(
        request,
        name="assets.html",
        context={"user": user, "assets": assets},
    )


@router.get("/forgot-password", include_in_schema=False)
async def forgot_password_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "title": "Forgot Password",
            "email_configured": is_email_configured(),
        },
    )


@router.get("/reset-password", include_in_schema=False)
async def reset_password_page(request: Request):

    response = request.app.state.templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "title": "Reset Password",
            "email_configured": is_email_configured(),
        },
    )

    response.headers["Referrer-Policy"] = "no-referrer"
    return response
