from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.database import get_db
from app.deps import get_url_service, rate_limit
from app.schemas import URLRequest, URLResponse, URLStats
from app.services.url_service import URLService

router = APIRouter(tags=["urls"])

DbSession = Annotated[Session, Depends(get_db)]
ServiceDep = Annotated[URLService, Depends(get_url_service)]
Throttle = Annotated[None, Depends(rate_limit)]


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/api/urls",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_short_url(
    payload: URLRequest,
    request: Request,
    db: DbSession,
    service: ServiceDep,
    _: Throttle,
) -> URLResponse:
    record = service.shorten(
        db,
        original_url=payload.url,
        custom_code=payload.custom_code,
        ttl_seconds=payload.ttl_seconds,
        client_ip=_client_ip(request),
    )
    return URLResponse(
        short_code=record.short_code,
        short_url=service.short_url_for(record.short_code),
        original_url=record.original_url,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


@router.get("/api/urls/{short_code}", response_model=URLStats)
def get_stats(
    short_code: str,
    db: DbSession,
    service: ServiceDep,
    _: Throttle,
) -> URLStats:
    return service.get_stats(db, short_code)


@router.delete("/api/urls/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_url(
    short_code: str,
    db: DbSession,
    service: ServiceDep,
    _: Throttle,
) -> None:
    service.delete(db, short_code)


@router.get("/{short_code}", status_code=status.HTTP_302_FOUND)
def redirect(
    short_code: str,
    request: Request,
    db: DbSession,
    service: ServiceDep,
) -> RedirectResponse:
    original = service.resolve(db, short_code)
    if original is None:
        raise NotFoundError(f"no URL for code {short_code!r}")
    service.record_click(
        short_code=short_code,
        referrer=request.headers.get("referer"),
        client_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return RedirectResponse(url=original, status_code=status.HTTP_302_FOUND)
