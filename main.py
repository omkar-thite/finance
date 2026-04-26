from fastapi import FastAPI, Request, status, Response
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from routes import front_view, users, transactions
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager
from fastapi.exception_handlers import (
    http_exception_handler,
)

from database import engine
from utils.error_messages import ErrorMessages
from config import settings

import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
        docs_route = request.url.path.startswith(DOCS_PATHS)

        script_src = "script-src 'self'"
        style_src = "style-src 'self'"
        font_src = "font-src 'self'"
        img_src = (
            f"img-src 'self' blob: "
            f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com"
        )

        if docs_route and not settings.is_production:
            # Swagger/ReDoc assets are served by jsDelivr CDN.
            # FastAPI docs include inline script blocks for UI bootstrapping.
            script_src += " https://cdn.jsdelivr.net 'unsafe-inline'"
            style_src += " https://cdn.jsdelivr.net"
            font_src += " https://cdn.jsdelivr.net"

            # FastAPI docs UI loads an external favicon and data URI images.
            img_src += " https://fastapi.tiangolo.com data:"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            f"{script_src}; "
            f"{style_src}; "
            f"{img_src}; "
            f"{font_src}; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests; "
            "report-uri /csp-report;"
        )
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):

    async with engine.begin():
        yield
    await engine.dispose()


app = (
    FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    if settings.is_production
    else FastAPI(lifespan=lifespan)
)

app.add_middleware(CSPMiddleware)
app.state.templates = Jinja2Templates(directory="templates")
app.state.templates.env.globals["s3_endpoint_url"] = settings.s3_endpoint_url
app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(
    transactions.router, prefix="/api/transactions", tags=["transactions"]
)
app.include_router(front_view.router, tags=["front_view"])


@app.post("/csp-report")
async def csp_report(request: Request):
    report = await request.json()
    logger.warning("CSP violation: %s", report)
    return Response(status_code=204)


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
