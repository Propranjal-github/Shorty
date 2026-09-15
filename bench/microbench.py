r"""In-process microbenchmark: cache HIT vs cache MISS (DB read) on resolve().

Measures the real production `URLService.resolve` path with no HTTP, no
threadpool, and no transport overhead, so the latency reflects the algorithm
itself. The HIT/MISS ratio quantifies exactly what the in-process LRU cache
buys over hitting SQLite.

Run with the backend venv:
    backend\.venv\Scripts\python.exe bench\microbench.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

_DB = os.path.join(tempfile.mkdtemp(prefix="shorty-mb-"), "mb.db").replace(os.sep, "/")
os.environ["SHORTY_DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["SHORTY_CACHE_TTL_SECONDS"] = "0"  # disable TTL so entries stay warm
os.environ.setdefault("SHORTY_CACHE_CAPACITY", "10000")

from app.database import SessionLocal, init_db  # noqa: E402
from app.deps import get_cache, get_url_service  # noqa: E402
from sqlalchemy import text  # noqa: E402

M = 50_000


def bench(label: str, fn, m: int = M) -> float:
    for _ in range(1000):  # warm up
        fn()
    t0 = time.perf_counter_ns()
    for _ in range(m):
        fn()
    dt = time.perf_counter_ns() - t0
    ns_per_op = dt / m
    print(f"  {label:<24} {ns_per_op:8.1f} ns/op  ({m / dt * 1e9:,.0f} ops/s)")
    return ns_per_op


def main() -> int:
    init_db()
    db = SessionLocal()
    svc = get_url_service()
    cache = get_cache()
    record = svc.shorten(db, original_url="https://example.com/hot")
    code = record.short_code
    svc.resolve(db, code)  # warm the cache

    print(f"\nResolving /{code}  ({M:,} ops/phase)\n" + "-" * 56)
    hit_ns = bench("resolve (cache HIT)", lambda: svc.resolve(db, code))

    def miss() -> None:
        cache.invalidate(code)  # force the cold/DB path
        db.expire_all()  # bypass the ORM identity map so each call hits SQLite
        svc.resolve(db, code)

    miss_ns = bench("resolve (cache MISS, ORM)", miss)

    def raw_select() -> None:
        # raw SQL on the same connection: the true DB round-trip floor, with no
        # ORM hydration and no identity-map involvement.
        db.execute(
            text("SELECT original_url, expires_at FROM urls WHERE short_code = :c"),
            {"c": code},
        ).first()

    raw_ns = bench("resolve (raw SQL SELECT)", raw_select)
    speedup = miss_ns / hit_ns if hit_ns else 0
    raw_speedup = raw_ns / hit_ns if hit_ns else 0

    print("-" * 56)
    print(
        f"\nCache speedup vs ORM DB-read: {hit_ns:.0f} ns (hit) vs {miss_ns:.0f} ns "
        f"(miss) -> {speedup:.0f}x faster when warm."
    )
    print(
        f"Cache speedup vs raw SQL:    {hit_ns:.0f} ns (hit) vs {raw_ns:.0f} ns "
        f"(raw) -> {raw_speedup:.0f}x faster when warm."
    )
    print(
        f"\nResult: cache hit {hit_ns:.0f} ns vs miss {miss_ns/1000:.1f} us -> "
        f"{speedup:.0f}x faster when warm (raw-SQL lower bound: {raw_speedup:.0f}x)."
    )
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
