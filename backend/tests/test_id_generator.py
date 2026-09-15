from __future__ import annotations

import threading

import pytest

from app.core.id_generator import (
    MAX_MACHINE_ID,
    SEQUENCE_BITS,
    SnowflakeGenerator,
)


def test_single_thread_uniqueness() -> None:
    gen = SnowflakeGenerator(1)
    ids = {gen.next_id() for _ in range(5000)}
    assert len(ids) == 5000


def test_multithreaded_uniqueness() -> None:
    gen = SnowflakeGenerator(2)
    ids: set[int] = set()
    lock = threading.Lock()

    def worker() -> None:
        local = [gen.next_id() for _ in range(2000)]
        with lock:
            ids.update(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ids) == 8 * 2000


def test_machine_id_is_embedded() -> None:
    a = SnowflakeGenerator(1)
    b = SnowflakeGenerator(2)
    mask = (1 << 10) - 1
    assert (a.next_id() >> SEQUENCE_BITS) & mask == 1
    assert (b.next_id() >> SEQUENCE_BITS) & mask == 2


def test_ids_are_monotonic_non_decreasing() -> None:
    gen = SnowflakeGenerator(1)
    previous = 0
    for _ in range(1000):
        current = gen.next_id()
        assert current > previous
        previous = current


def test_invalid_machine_id_raises() -> None:
    with pytest.raises(ValueError):
        SnowflakeGenerator(MAX_MACHINE_ID + 1)
    with pytest.raises(ValueError):
        SnowflakeGenerator(-1)
