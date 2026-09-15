from __future__ import annotations

import threading
import time


class TokenBucket:
    """Single token bucket with lazy (on-demand) refill. Thread-safe."""

    __slots__ = ("_capacity", "_refill", "_tokens", "_last", "_lock")

    def __init__(self, capacity: float, refill_per_second: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second must be positive")
        self._capacity = capacity
        self._refill = refill_per_second
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            if elapsed > 0:
                self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
                self._last = now
            if self._tokens >= cost:
                self._tokens -= cost
                return True
            return False

    @property
    def tokens(self) -> float:
        with self._lock:
            return self._tokens

    def is_idle(self, threshold: float) -> bool:
        with self._lock:
            return time.monotonic() - self._last >= threshold


class RateLimiter:
    """Per-key token-bucket rate limiter.

    Buckets are created lazily on first use and reaped once idle past
    `idle_ttl` to bound memory. Thread-safe; uses double-checked locking to
    avoid taking the registry lock on the hot read path.
    """

    __slots__ = ("_capacity", "_refill", "_idle_ttl", "_buckets", "_last_cleanup", "_lock")

    def __init__(
        self,
        capacity: float,
        refill_per_second: float,
        *,
        idle_ttl: float = 600.0,
    ) -> None:
        if capacity <= 0 or refill_per_second <= 0:
            raise ValueError("capacity and refill_per_second must be positive")
        self._capacity = capacity
        self._refill = refill_per_second
        self._idle_ttl = idle_ttl
        self._buckets: dict[str, TokenBucket] = {}
        self._last_cleanup = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        bucket = self._buckets.get(key)
        if bucket is None:
            with self._lock:
                bucket = self._buckets.get(key)
                if bucket is None:
                    bucket = TokenBucket(self._capacity, self._refill)
                    self._buckets[key] = bucket
        allowed = bucket.allow(cost)
        self._maybe_cleanup()
        return allowed

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < self._idle_ttl:
            return
        with self._lock:
            if now - self._last_cleanup < self._idle_ttl:
                return
            stale = [k for k, b in self._buckets.items() if b.is_idle(self._idle_ttl)]
            for k in stale:
                del self._buckets[k]
            self._last_cleanup = now

    @property
    def tracked_keys(self) -> int:
        return len(self._buckets)
