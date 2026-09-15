from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

K = TypeVar("K")  # bound by Hashable at the cache level
V = TypeVar("V")


@dataclass
class _Node(Generic[K, V]):
    key: K
    value: V
    expires_at: float  # 0.0 means "never expires"
    prev: _Node[K, V] | None = None
    next: _Node[K, V] | None = None


@dataclass
class CacheStats:
    size: int
    capacity: int
    hits: int
    misses: int
    evictions: int


class LRUCache(Generic[K, V]):
    """Thread-safe TTL-aware LRU cache.

    Backed by a hash map + doubly-linked list for O(1) get/put. On access an
    entry is moved to the head (most-recently-used); evictions come from the
    tail (least-recently-used). TTL is checked lazily on read and write.
    """

    __slots__ = (
        "_capacity",
        "_ttl",
        "_lock",
        "_data",
        "_head",
        "_tail",
        "_hits",
        "_misses",
        "_evictions",
    )

    def __init__(self, capacity: int, ttl_seconds: float = 0.0) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._data: dict[K, _Node[K, V]] = {}
        self._head: _Node[K, V] = cast("_Node[K, V]", _Node("__head__", None, 0.0))
        self._tail: _Node[K, V] = cast("_Node[K, V]", _Node("__tail__", None, 0.0))
        self._head.next = self._tail
        self._tail.prev = self._head
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _unlink(self, node: _Node[K, V]) -> None:
        prev = node.prev
        nxt = node.next
        assert prev is not None and nxt is not None
        prev.next = nxt
        nxt.prev = prev

    def _push_front(self, node: _Node[K, V]) -> None:
        node.prev = self._head
        node.next = self._head.next
        assert self._head.next is not None
        self._head.next.prev = node
        self._head.next = node

    def _is_expired(self, node: _Node[K, V]) -> bool:
        return self._ttl > 0 and node.expires_at <= time.monotonic()

    def get(self, key: K) -> V | None:
        with self._lock:
            node = self._data.get(key)
            if node is None:
                self._misses += 1
                return None
            if self._is_expired(node):
                self._unlink(node)
                del self._data[key]
                self._misses += 1
                return None
            self._unlink(node)
            self._push_front(node)
            self._hits += 1
            return node.value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            now = time.monotonic()
            expires_at = now + self._ttl if self._ttl > 0 else 0.0
            node = self._data.get(key)
            if node is not None:
                node.value = value
                node.expires_at = expires_at
                self._unlink(node)
                self._push_front(node)
                return
            node = _Node(key, value, expires_at)
            self._data[key] = node
            self._push_front(node)
            if len(self._data) > self._capacity:
                lru = self._tail.prev
                assert lru is not None and lru is not self._head
                self._unlink(lru)
                del self._data[lru.key]
                self._evictions += 1

    def invalidate(self, key: K) -> None:
        with self._lock:
            node = self._data.pop(key, None)
            if node is not None:
                self._unlink(node)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._head.next = self._tail
            self._tail.prev = self._head
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                size=len(self._data),
                capacity=self._capacity,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )
