from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.encoder import encode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.id_generator import SnowflakeGenerator
from app.core.lru_cache import LRUCache
from app.core.time import utcnow
from app.models import ClickEvent as ClickEventModel
from app.models import URLRecord
from app.schemas import AnalyticsResponse, ClickBucket, ReferrerCount, URLStats
from app.services.analytics import AnalyticsBuffer
from app.services.analytics import ClickEvent as ClickEventData


@dataclass(slots=True)
class CachedTarget:
    """Cached resolution target, carrying the URL's own expiry for validation."""

    original_url: str
    expires_at: datetime | None


class URLService:
    """Business logic for shortening, resolving, and analysing URLs.

    Pure of HTTP concerns: it raises domain exceptions which the router layer
    maps to HTTP responses. Coordinates the id generator, LRU cache, analytics
    buffer, and persistence.
    """

    def __init__(
        self,
        *,
        id_generator: SnowflakeGenerator,
        cache: LRUCache[str, CachedTarget],
        analytics: AnalyticsBuffer,
        base_url: str,
    ) -> None:
        self._gen = id_generator
        self._cache = cache
        self._analytics = analytics
        self._base_url = base_url.rstrip("/")

    def short_url_for(self, code: str) -> str:
        return f"{self._base_url}/{code}"

    def shorten(
        self,
        db: Session,
        *,
        original_url: str,
        custom_code: str | None = None,
        ttl_seconds: int | None = None,
        client_ip: str | None = None,
    ) -> URLRecord:
        new_id = self._gen.next_id()
        if custom_code is not None:
            code = custom_code
            if self._exists(db, code):
                raise ConflictError(f"custom code {code!r} is already taken")
        else:
            code = encode(new_id)
            if self._exists(db, code):  # collision guard; effectively impossible
                code = encode(self._gen.next_id())
        expires_at = utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        record = URLRecord(
            id=new_id,
            short_code=code,
            original_url=original_url,
            expires_at=expires_at,
            created_by=client_ip,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        self._cache.put(code, CachedTarget(original_url, expires_at))
        return record

    def resolve(self, db: Session, short_code: str) -> str | None:
        cached = self._cache.get(short_code)
        if cached is not None:
            if cached.expires_at is not None and cached.expires_at <= utcnow():
                self._cache.invalidate(short_code)
                return None
            return cached.original_url
        record = self._get(db, short_code)
        if record is None:
            return None
        if record.expires_at is not None and record.expires_at <= utcnow():
            return None
        self._cache.put(short_code, CachedTarget(record.original_url, record.expires_at))
        return record.original_url

    def record_click(
        self,
        *,
        short_code: str,
        referrer: str | None,
        client_ip: str | None,
        user_agent: str | None,
    ) -> None:
        self._analytics.record(
            ClickEventData(
                short_code=short_code,
                referrer=referrer,
                client_ip=client_ip,
                user_agent=user_agent,
                clicked_at=utcnow(),
            )
        )

    def get_stats(self, db: Session, short_code: str) -> URLStats:
        record = self._get(db, short_code)
        if record is None:
            raise NotFoundError(f"no URL for code {short_code!r}")
        return URLStats(
            short_code=record.short_code,
            original_url=record.original_url,
            click_count=record.click_count,
            created_at=record.created_at,
            expires_at=record.expires_at,
        )

    def get_analytics(self, db: Session, short_code: str, *, hours: int = 24) -> AnalyticsResponse:
        record = self._get(db, short_code)
        if record is None:
            raise NotFoundError(f"no URL for code {short_code!r}")
        since = utcnow() - timedelta(hours=hours)
        events = (
            db.query(ClickEventModel)
            .filter(
                ClickEventModel.short_code == short_code,
                ClickEventModel.clicked_at >= since,
            )
            .all()
        )
        total_clicks = (
            db.query(func.count(ClickEventModel.id))
            .filter(ClickEventModel.short_code == short_code)
            .scalar()
            or 0
        )
        buckets: Counter[datetime] = Counter()
        referrers: Counter[str | None] = Counter()
        for event in events:
            hour = event.clicked_at.replace(minute=0, second=0, microsecond=0)
            buckets[hour] += 1
            referrers[event.referrer] += 1
        recent = [ClickBucket(bucket=h, clicks=c) for h, c in sorted(buckets.items())]
        top = [ReferrerCount(referrer=r, count=c) for r, c in referrers.most_common(5)]
        return AnalyticsResponse(
            short_code=short_code,
            total_clicks=total_clicks,
            recent=recent,
            top_referrers=top,
        )

    def delete(self, db: Session, short_code: str) -> None:
        record = self._get(db, short_code)
        if record is None:
            raise NotFoundError(f"no URL for code {short_code!r}")
        db.delete(record)
        db.commit()
        self._cache.invalidate(short_code)

    def _exists(self, db: Session, code: str) -> bool:
        return db.query(URLRecord.short_code).filter_by(short_code=code).first() is not None

    def _get(self, db: Session, code: str) -> URLRecord | None:
        return db.query(URLRecord).filter_by(short_code=code).first()
