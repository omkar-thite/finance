from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from routes import front_view, users, transactions
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager
from fastapi.exception_handlers import (
    http_exception_handler,
)

from database import engine, Base
from utils.error_messages import ErrorMessages


@asynccontextmanager
async def lifespan(_app: FastAPI):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.state.templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(
    transactions.router, prefix="/api/transactions", tags=["transactions"]
)
app.include_router(front_view.router, tags=["front_view"])


# --------- EXCEPTION HANDLERS --------------------------#


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return await http_exception_handler(request, exc)

    return request.app.state.templates.TemplateResponse(
        request,
        name="error.html",
        status_code=status.HTTP_404_NOT_FOUND,
        context={
            "status_code": status.HTTP_404_NOT_FOUND,
            "message": exc.detail or ErrorMessages.PAGE_NOT_FOUND,
        },
    )
