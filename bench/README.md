# Benchmarks

Two benchmarks. The **microbenchmark** measures the cache-vs-DB win in-process
(no HTTP); the HTTP load test is for end-to-end sanity and is environment-bound
(see [ADR-012](../docs/DESIGN_DECISIONS.md)).

## microbench.py — cache hit vs cache miss (DB read)

Measures the real `URLService.resolve` path **in-process** — no HTTP, no
threadpool, no transport — so the latency reflects the cache algorithm itself.

```bash
backend/.venv/Scripts/python.exe bench/microbench.py   # run from backend/ cwd
```

Example output (your numbers will vary by hardware):

```
  resolve (cache HIT)         747.0 ns/op  (1,338,645 ops/s)
  resolve (cache MISS, ORM) 484868.2 ns/op  (2,062 ops/s)
  resolve (raw SQL SELECT) 113741.4 ns/op  (8,792 ops/s)

Cache speedup vs ORM DB-read: 747 ns (hit) vs 484868 ns (miss) -> 649x faster
Cache speedup vs raw SQL:    747 ns (hit) vs 113741 ns (raw) -> 152x faster
```

**How to read it** — a cache hit is a hash-map + doubly-linked-list lookup
(~750 ns). A miss is a SQLite read: ~114 µs at the raw-SQL floor, ~485 µs
through the ORM path the code actually uses. So the cache is **~150x–650x
faster** than a DB read. The raw-SQL figure (150x) is the conservative lower
bound.

## benchmark.py — end-to-end HTTP load test

Drives shorten, redirect (hit), and redirect (miss) over real HTTP. Start the
server with the rate limiter off and cache forced to capacity 1:

```bash
# Windows (one line per var)
set SHORTY_CACHE_CAPACITY=1
set SHORTY_RATE_LIMIT_CAPACITY=100000000
set SHORTY_RATE_LIMIT_REFILL_PER_SECOND=100000000
set SHORTY_ANALYTICS_FLUSH_INTERVAL_SECONDS=3600
set SHORTY_DATABASE_URL=sqlite:///./bench.db
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# then:
backend/.venv/Scripts/python.exe bench/benchmark.py
```

These numbers are dominated by the OS network stack + the sync-endpoint
threadpool + httpx, **not** the cache. On a single dev machine a cache *hit*
can even appear slower than a *miss* under concurrency — that is transport
noise, not the algorithm. Treat these as an end-to-end sanity check, not a
measure of the cache.
