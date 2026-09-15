from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from app.config import settings
from app.core.exceptions import RateLimitExceededError
from app.core.id_generator import SnowflakeGenerator
from app.core.lru_cache import LRUCache
from app.core.rate_limiter import RateLimiter
from app.services.analytics import AnalyticsBuffer
from app.services.url_service import CachedTarget, URLService


@lru_cache
def get_id_generator() -> SnowflakeGenerator:
    return SnowflakeGenerator(machine_id=settings.machine_id)


@lru_cache
def get_cache() -> LRUCache[str, CachedTarget]:
    return LRUCache(capacity=settings.cache_capacity, ttl_seconds=settings.cache_ttl_seconds)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(
        capacity=settings.rate_limit_capacity,
        refill_per_second=settings.rate_limit_refill_per_second,
    )


@lru_cache
def get_analytics_buffer() -> AnalyticsBuffer:
    return AnalyticsBuffer(
        batch_size=settings.analytics_batch_size,
        flush_interval=settings.analytics_flush_interval_seconds,
    )


@lru_cache
def get_url_service() -> URLService:
    return URLService(
        id_generator=get_id_generator(),
        cache=get_cache(),
        analytics=get_analytics_buffer(),
        base_url=settings.base_url,
    )


def rate_limit(request: Request) -> None:
    """FastAPI dependency: throttle per client IP via the token-bucket limiter."""
    limiter = get_rate_limiter()
    forwarded = request.headers.get("x-forwarded-for")
    key = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "anonymous")
    )
    if not limiter.allow(key):
        raise RateLimitExceededError("rate limit exceeded; please retry shortly")
