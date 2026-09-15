from __future__ import annotations

from fastapi.testclient import TestClient

from app.deps import get_analytics_buffer
from app.services.url_service import URLService


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_metadata(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "shorty"


def test_create_then_redirect(client: TestClient) -> None:
    response = client.post("/api/urls", json={"url": "https://example.com"})
    assert response.status_code == 201
    body = response.json()
    code = body["short_code"]
    assert body["short_url"].endswith(f"/{code}")

    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com"


def test_create_with_custom_code(client: TestClient) -> None:
    response = client.post("/api/urls", json={"url": "https://x.com", "custom_code": "promo"})
    assert response.status_code == 201
    assert response.json()["short_code"] == "promo"


def test_custom_code_conflict_returns_409(client: TestClient) -> None:
    client.post("/api/urls", json={"url": "https://a.com", "custom_code": "dup"})
    response = client.post("/api/urls", json={"url": "https://b.com", "custom_code": "dup"})
    assert response.status_code == 409


def test_redirect_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/nope", follow_redirects=False)
    assert response.status_code == 404


def test_invalid_url_returns_422(client: TestClient) -> None:
    response = client.post("/api/urls", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_get_stats(client: TestClient, service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://s.com")
    response = client.get(f"/api/urls/{record.short_code}")
    assert response.status_code == 200
    body = response.json()
    assert body["original_url"] == "https://s.com"
    assert body["click_count"] == 0


def test_delete_then_404(client: TestClient, service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://d.com")
    response = client.delete(f"/api/urls/{record.short_code}")
    assert response.status_code == 204
    follow_up = client.get(f"/api/urls/{record.short_code}")
    assert follow_up.status_code == 404


def test_analytics_endpoint(client: TestClient, service: URLService, db) -> None:  # type: ignore[no-untyped-def]
    record = service.shorten(db, original_url="https://a.com")
    for _ in range(3):
        client.get(f"/{record.short_code}", follow_redirects=False)
    get_analytics_buffer().flush()

    response = client.get(f"/api/urls/{record.short_code}/analytics")
    assert response.status_code == 200
    assert response.json()["total_clicks"] == 3


def test_internal_stats_exposes_cache_metrics(client: TestClient) -> None:
    response = client.get("/api/_internal/stats")
    assert response.status_code == 200
    body = response.json()
    assert "cache" in body
    assert body["cache"]["capacity"] > 0
    assert "analytics_pending" in body
