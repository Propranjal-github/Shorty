from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

# Configure an isolated, file-based SQLite DB and generous limits BEFORE any
# app module is imported. A file DB (not :memory:) is used so the analytics
# flusher's own connections see the same tables. The background flusher is
# effectively silenced (huge interval/batch) so tests flush explicitly.
_TMP_DIR = tempfile.mkdtemp(prefix="shorty-test-")
_DB_PATH = os.path.join(_TMP_DIR, "shorty-test.db").replace(os.sep, "/")
os.environ["SHORTY_DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SHORTY_BASE_URL"] = "http://testserver"
os.environ["SHORTY_RATE_LIMIT_CAPACITY"] = "10000"
os.environ["SHORTY_RATE_LIMIT_REFILL_PER_SECOND"] = "10000"
os.environ["SHORTY_ANALYTICS_FLUSH_INTERVAL_SECONDS"] = "3600"
os.environ["SHORTY_ANALYTICS_BATCH_SIZE"] = "100000"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, init_db
from app.deps import get_analytics_buffer, get_cache, get_url_service
from app.main import app
from app.services.url_service import URLService


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> Generator[None, None, None]:
    init_db()
    yield


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def service() -> URLService:
    return get_url_service()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolate(db: Session) -> Generator[None, None, None]:
    """Truncate tables, drain analytics, and clear the cache between tests."""
    get_analytics_buffer().flush()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    get_cache().clear()
    yield
