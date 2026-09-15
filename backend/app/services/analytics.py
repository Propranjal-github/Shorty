from __future__ import annotations

import logging
import threading
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update

from app.core.time import utcnow
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClickEvent:
    short_code: str
    referrer: str | None
    client_ip: str | None
    user_agent: str | None
    clicked_at: datetime


class AnalyticsBuffer:
    """Bounded in-memory buffer for click events with a background flusher.

    `record()` is O(1) and non-blocking: it appends to a deque under a lock.
    A daemon thread flushes batches to the DB on an interval and a batch-size
    threshold, keeping the redirect path off the critical write latency.
    """

    def __init__(self, batch_size: int, flush_interval: float) -> None:
        if batch_size <= 0 or flush_interval <= 0:
            raise ValueError("batch_size and flush_interval must be positive")
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buf: deque[ClickEvent] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._not_full = True

    def record(self, event: ClickEvent) -> None:
        with self._lock:
            self._buf.append(event)
            if len(self._buf) >= self._batch_size:
                self._not_full = False

    def _drain(self) -> list[ClickEvent]:
        with self._lock:
            if not self._buf:
                return []
            batch = list(self._buf)
            self._buf.clear()
            self._not_full = True
            return batch

    def flush(self) -> int:
        batch = self._drain()
        if not batch:
            return 0
        from app.models import ClickEvent as ClickEventModel
        from app.models import URLRecord

        db = SessionLocal()
        try:
            db.bulk_save_objects(
                [
                    ClickEventModel(
                        short_code=e.short_code,
                        referrer=e.referrer,
                        client_ip=e.client_ip,
                        user_agent=e.user_agent,
                        clicked_at=e.clicked_at,
                    )
                    for e in batch
                ]
            )
            for code, count in Counter(e.short_code for e in batch).items():
                db.execute(
                    update(URLRecord)
                    .where(URLRecord.short_code == code)
                    .values(click_count=URLRecord.click_count + count)
                )
            db.commit()
            return len(batch)
        except Exception:
            db.rollback()
            logger.exception("analytics flush failed for %d events", len(batch))
            raise
        finally:
            db.close()

    def start(self, *, now: Callable[[], datetime] = utcnow) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="analytics-flusher", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._flush_interval):
            try:
                self.flush()
            except Exception:  # noqa: BLE001 - keep the flusher alive
                logger.exception("flusher iteration failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        try:
            self.flush()
        except Exception:  # noqa: BLE001
            logger.exception("final flush failed")

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._buf)
