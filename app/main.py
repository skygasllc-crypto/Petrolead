"""PetroLead FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.companies import router as companies_router
from app.api.emails import router as emails_router
from app.api.payments import router as payments_router
from app.api.saved_searches import router as saved_searches_router
from app.config import get_settings
from app.core.deps import get_current_admin_user, get_current_user
from app.core.logging import setup_logging
from app.database.migrations import run_migrations
from app.services.billing_service import BillingError
from app.services.payment_service import PaymentError

setup_logging()
logger = logging.getLogger("petrolead.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bring the database schema up to date. Deployments running several app
    # processes should set RUN_MIGRATIONS_ON_STARTUP=false and run
    # `alembic upgrade head` once per release instead.
    if settings.run_migrations_on_startup:
        run_migrations()
    logger.info(
        "PetroLead starting | env=%s | database=%s | search_provider=%s",
        settings.app_env,
        settings.database_url.split("://")[0] + "://***",
        settings.search_provider,
    )
    if settings.using_default_secret_key and settings.app_env != "development":
        logger.warning(
            "SECRET_KEY is still the insecure development default outside a "
            "development environment — set a real random value in .env."
        )
    yield
    logger.info("PetroLead shutting down")


app = FastAPI(
    title="PetroLead API",
    description="Petroleum & energy B2B lead discovery platform — Phase 1: Company Discovery.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


@app.exception_handler(BillingError)
async def billing_exception_handler(request: Request, exc: BillingError) -> JSONResponse:
    # A plan or credit limit — the message tells the user what to do next.
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(PaymentError)
async def payment_exception_handler(request: Request, exc: PaymentError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces to clients; full detail goes to the logs only.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


app.include_router(auth_router, prefix=settings.api_v1_prefix)

# Every other endpoint requires a logged-in user, and only ever sees that
# account's own saved data.
_auth_required = [Depends(get_current_user)]
app.include_router(companies_router, prefix=settings.api_v1_prefix, dependencies=_auth_required)
app.include_router(emails_router, prefix=settings.api_v1_prefix, dependencies=_auth_required)
app.include_router(billing_router, prefix=settings.api_v1_prefix, dependencies=_auth_required)
app.include_router(payments_router, prefix=settings.api_v1_prefix, dependencies=_auth_required)
app.include_router(
    saved_searches_router, prefix=settings.api_v1_prefix, dependencies=_auth_required
)
app.include_router(
    admin_router,
    prefix=settings.api_v1_prefix,
    dependencies=[Depends(get_current_admin_user)],
)


@app.get(f"{settings.api_v1_prefix}/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
