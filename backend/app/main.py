from __future__ import annotations

import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import (
    ConflictError,
    InvalidUrlError,
    NotFoundError,
    RateLimitExceededError,
    ShortyError,
)
from app.database import SessionLocal, init_db
from app.deps import get_analytics_buffer, get_id_generator
from app.routers import analytics, health, urls
from app.services.id_lease import (
    LEASE_TTL_SECONDS,
    lease_machine_id,
    release_machine_id,
    renew_machine_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

_leased_machine_id: int | None = None
_renew_stop: threading.Event = threading.Event()


def _lease_renew_loop(machine_id: int, interval: float) -> None:
    """Background thread: renews the DB lease every *interval* seconds.

    One lightweight UPDATE per tick — no extra memory, ~0 cost.
    """
    while not _renew_stop.wait(timeout=interval):
        try:
            with SessionLocal() as db:
                renew_machine_id(db, machine_id)
            logger.debug("renewed lease for machine_id %d", machine_id)
        except Exception:
            logger.warning("lease renewal failed; will retry next tick", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _leased_machine_id
    if settings.auto_create_tables:
        # dev/tests: create tables directly. Prod sets this False and relies on Alembic.
        init_db()
    if settings.database_url.startswith("postgres"):
        with SessionLocal() as db:
            _leased_machine_id = lease_machine_id(db)
        get_id_generator().set_machine_id(_leased_machine_id)
        logger.info("leased machine_id %d", _leased_machine_id)
        # Renew every TTL/2 so the lease never expires while we're alive.
        _renew_stop.clear()
        renew_thread = threading.Thread(
            target=_lease_renew_loop,
            args=(_leased_machine_id, LEASE_TTL_SECONDS / 2),
            daemon=True,
            name="lease-renew",
        )
        renew_thread.start()
    buffer = get_analytics_buffer()
    buffer.start()
    logger.info("startup complete; analytics flusher running")
    yield
    buffer.stop()
    _renew_stop.set()  # stop the renewal thread (if running)
    if _leased_machine_id is not None:
        with SessionLocal() as db:
            release_machine_id(db, _leased_machine_id)
        logger.info("released machine_id %d", _leased_machine_id)
        _leased_machine_id = None
    logger.info("shutdown complete")


app = FastAPI(
    title="Shorty",
    version="0.1.0",
    description="A distributed URL shortener.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidUrlError)
async def _invalid_url(_: Request, exc: InvalidUrlError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RateLimitExceededError)
async def _rate_limited(_: Request, exc: RateLimitExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={"Retry-After": "1"},
    )


@app.exception_handler(ShortyError)
async def _domain_error(_: Request, exc: ShortyError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(urls.router)
app.include_router(analytics.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "shorty", "version": "0.1.0", "docs": "/docs"}
