from __future__ import annotations

import threading
import time

from app.core.exceptions import ClockMovedBackwardsError

# Custom epoch (2023-11-14T22:13:20Z). Keeping timestamps small maximises the
# ~69-year lifetime of the 41-bit field.
EPOCH_MS = 1_700_000_000_000

MACHINE_ID_BITS = 10
SEQUENCE_BITS = 12
MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1
SEQUENCE_MASK = (1 << SEQUENCE_BITS) - 1
TIMESTAMP_LEFT_SHIFT = MACHINE_ID_BITS + SEQUENCE_BITS


class SnowflakeGenerator:
    """Twitter-snowflake-style unique 64-bit ID generator.

    Bit layout (MSB -> LSB): 41-bit millisecond timestamp | 10-bit machine id |
    12-bit sequence. IDs are k-sortable (roughly time-ordered) and collision-free
    across up to MAX_MACHINE_ID machines. Thread-safe via a single mutex; the
    critical section is O(1) so contention is bounded even under heavy load.
    """

    __slots__ = ("_machine_id", "_epoch", "_lock", "_last_ts", "_seq")

    def __init__(self, machine_id: int, *, epoch: int = EPOCH_MS) -> None:
        if not 0 <= machine_id <= MAX_MACHINE_ID:
            raise ValueError(f"machine_id must be in [0, {MAX_MACHINE_ID}]")
        self._machine_id = machine_id
        self._epoch = epoch
        self._lock = threading.Lock()
        self._last_ts: int = -1
        self._seq: int = 0

    def set_machine_id(self, machine_id: int) -> None:
        """Reassign the machine id (e.g. from a DB lease at startup).

        Must be called before any IDs are issued and is intended for one-time
        startup configuration on multi-instance deployments.
        """
        if not 0 <= machine_id <= MAX_MACHINE_ID:
            raise ValueError(f"machine_id must be in [0, {MAX_MACHINE_ID}]")
        with self._lock:
            self._machine_id = machine_id

    @staticmethod
    def _current_ms() -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_ts: int) -> int:
        ts = self._current_ms()
        while ts <= last_ts:
            ts = self._current_ms()
        return ts

    def next_id(self) -> int:
        with self._lock:
            ts = self._current_ms()
            if ts < self._last_ts:
                raise ClockMovedBackwardsError(
                    f"clock moved backwards: last={self._last_ts} now={ts}"
                )
            if ts == self._last_ts:
                self._seq = (self._seq + 1) & SEQUENCE_MASK
                if self._seq == 0:
                    ts = self._wait_next_ms(self._last_ts)
            else:
                self._seq = 0
            self._last_ts = ts
            timestamp_delta = ts - self._epoch
            return (
                (timestamp_delta << TIMESTAMP_LEFT_SHIFT)
                | (self._machine_id << SEQUENCE_BITS)
                | self._seq
            )
