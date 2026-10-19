from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["meta"])

# Cache the readiness result so Cloud Run probes (every ~10s) don't each fire a
# SELECT against Neon.  A 30-second window is more than fresh enough for the
# "can I serve traffic?" semantic.
_ready_cache_ts: float = 0.0
_READY_TTL: float = 30.0


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no DB touch, always cheap."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Readiness probe — confirms the DB connection is usable (cached)."""
    global _ready_cache_ts
    now = time.monotonic()
    if now - _ready_cache_ts < _READY_TTL:
        return {"status": "ready"}
    db.execute(text("SELECT 1"))
    _ready_cache_ts = now
    return {"status": "ready"}
