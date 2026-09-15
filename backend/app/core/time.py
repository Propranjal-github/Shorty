from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime.

    Naive UTC is used throughout so SQLite round-trips (which drop tzinfo) stay
    comparable. A Postgres migration would switch to timezone-aware columns.
    """
    return datetime.now(UTC).replace(tzinfo=None)
