from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.lru_cache import LRUCache
from app.core.rate_limiter import RateLimiter
from app.database import get_db
from app.deps import (
    get_analytics_buffer,
    get_cache,
    get_rate_limiter,
    get_url_service,
    rate_limit,
)
from app.schemas import AnalyticsResponse
from app.services.analytics import AnalyticsBuffer
from app.services.url_service import CachedTarget, URLService

router = APIRouter(tags=["analytics"])

DbSession = Annotated[Session, Depends(get_db)]
ServiceDep = Annotated[URLService, Depends(get_url_service)]
Throttle = Annotated[None, Depends(rate_limit)]
CacheDep = Annotated[LRUCache[str, CachedTarget], Depends(get_cache)]
BufferDep = Annotated[AnalyticsBuffer, Depends(get_analytics_buffer)]
LimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


@router.get("/api/urls/{short_code}/analytics", response_model=AnalyticsResponse)
def get_analytics(
    short_code: str,
    db: DbSession,
    service: ServiceDep,
    _: Throttle,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> AnalyticsResponse:
    return service.get_analytics(db, short_code, hours=hours)


@router.get("/api/_internal/stats", include_in_schema=False)
def internal_stats(
    cache: CacheDep,
    buffer: BufferDep,
    limiter: LimiterDep,
) -> dict[str, object]:
    cs = cache.stats()
    return {
        "cache": {
            "size": cs.size,
            "capacity": cs.capacity,
            "hits": cs.hits,
            "misses": cs.misses,
            "evictions": cs.evictions,
        },
        "analytics_pending": buffer.pending,
        "rate_limiter_tracked_keys": limiter.tracked_keys,
    }
