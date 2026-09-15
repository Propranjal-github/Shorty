from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.time import utcnow
from app.deps import get_analytics_buffer, get_cache
from app.services.url_service import URLService


def test_shorten_and_resolve(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://example.com")
    assert record.original_url == "https://example.com"
    assert service.resolve(db, record.short_code) == "https://example.com"


def test_resolve_serves_from_cache_after_db_delete(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://ex.com")
    service.resolve(db, record.short_code)  # warm the cache
    db.delete(record)
    db.commit()
    # cache hit bypasses the DB; the entry has no expiry so it still resolves
    assert service.resolve(db, record.short_code) == "https://ex.com"


def test_custom_code_conflict(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    service.shorten(db, original_url="https://a.com", custom_code="promo")
    with pytest.raises(ConflictError):
        service.shorten(db, original_url="https://b.com", custom_code="promo")


def test_resolve_unknown_returns_none(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    assert service.resolve(db, "nope") is None


def test_get_stats_unknown_raises(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError):
        service.get_stats(db, "nope")


def test_delete_removes_record_and_invalidates_cache(
    service: URLService,
    db,  # type: ignore[no-untyped-def]
) -> None:
    record = service.shorten(db, original_url="https://a.com")
    service.delete(db, record.short_code)
    assert service.resolve(db, record.short_code) is None
    assert get_cache().get(record.short_code) is None


def test_delete_unknown_raises(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError):
        service.delete(db, "nope")


def test_ttl_expiry_blocks_resolution(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://a.com", ttl_seconds=3600)
    get_cache().invalidate(record.short_code)  # force the DB path
    record.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert service.resolve(db, record.short_code) is None


def test_ttl_within_window_resolves(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://a.com", ttl_seconds=3600)
    assert service.resolve(db, record.short_code) == "https://a.com"


def test_analytics_aggregates_clicks(service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://a.com")
    for _ in range(5):
        service.record_click(
            short_code=record.short_code,
            referrer="https://google.com",
            client_ip="1.2.3.4",
            user_agent="ua",
        )
    service.record_click(
        short_code=record.short_code,
        referrer="https://x.com",
        client_ip="1.2.3.4",
        user_agent="ua",
    )
    get_analytics_buffer().flush()

    response = service.get_analytics(db, record.short_code, hours=24)
    assert response.total_clicks == 6
    assert response.top_referrers[0].referrer == "https://google.com"
    assert response.top_referrers[0].count == 5
