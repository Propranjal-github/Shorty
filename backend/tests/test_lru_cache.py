from __future__ import annotations

from time import sleep

import pytest

from app.core.lru_cache import LRUCache


def test_get_miss_returns_none_and_counts() -> None:
    cache = LRUCache(2)
    assert cache.get("missing") is None
    stats = cache.stats()
    assert stats.misses == 1
    assert stats.hits == 0


def test_put_then_get() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert cache.stats().hits == 1


def test_lru_eviction_removes_least_recently_used() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # a becomes MRU, b is LRU
    cache.put("c", 3)  # evicts b
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.stats().evictions == 1


def test_put_updates_value_in_place() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("a", 2)
    assert cache.get("a") == 2
    assert cache.stats().size == 1


def test_ttl_expiry_returns_none_after_ttl() -> None:
    cache = LRUCache(2, ttl_seconds=0.05)
    cache.put("a", 1)
    assert cache.get("a") == 1
    sleep(0.1)
    assert cache.get("a") is None


def test_invalidate_removes_entry() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.invalidate("a")
    assert cache.get("a") is None


def test_clear_resets_state() -> None:
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.get("a")
    cache.clear()
    stats = cache.stats()
    assert stats.size == 0
    assert stats.hits == 0


def test_invalid_capacity_raises() -> None:
    with pytest.raises(ValueError):
        LRUCache(0)


def test_capacity_boundary_evicts_exactly_one() -> None:
    cache = LRUCache(3)
    for key in ("a", "b", "c"):
        cache.put(key, key)
    cache.put("d", "d")  # evicts a
    assert cache.get("a") is None
    assert cache.stats().size == 3
