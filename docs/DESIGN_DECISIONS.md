# Design Decisions (ADR log)

A living record of architectural and technology decisions for **Shorty**, the
URL shortener. Each entry follows a lightweight ADR format: Context → Decision
→ Consequences. Append new decisions at the bottom; never rewrite history.

---

## ADR-001 — Project: distributed URL shortener (FastAPI + React/TS)

**Context** — The goal is a small but non-trivial URL shortener that exercises
core engineering concerns: data structures & algorithms, clean architecture,
API design, concurrency, testing, and engineering hygiene (CI/CD, Docker,
docs).

**Decision** — Build a distributed URL shortener. Backend in Python with
FastAPI; frontend in React + TypeScript (Vite). A shortener naturally touches
hashing/encoding, distributed ID generation, caching, rate limiting, async
analytics, and a clean REST API — all in a small, grokkable surface.

**Consequences** — Scope is bounded enough to finish yet rich enough to cover
meaningful ground. The frontend demonstrates end-to-end integration without
obscuring the backend algorithms that carry most of the interest.

---

## ADR-002 — Synchronous SQLAlchemy 2.0 + SQLite (default), not async

**Context** — FastAPI is async-native; async SQLAlchemy (aiosqlite) would
maximize the concurrency story. But async testing is more brittle (event-loop
fixtures, async test client) and harder to run reliably on Windows.

**Decision** — Use synchronous SQLAlchemy 2.0 with a sync `Session` dependency.
Default DB is SQLite (`shorty.db`); the URL is configurable so Postgres/MySQL
drop in via env. Concurrency is demonstrated instead through thread-safe core
data structures (LRU cache, rate limiter), the snowflake generator's mutex, and
FastAPI `BackgroundTasks` for non-blocking analytics writes.

**Consequences** — Tests are deterministic and fast. The concurrency story is
still explicit and load-bearing; async could be a follow-up if the project
migrates to Postgres at scale.

---

## ADR-003 — Layered architecture: routers → services → core

**Context** — Mixed business logic inside route handlers is hard to test and
reason about.

**Decision** — Three layers. `app/core/` holds pure, framework-agnostic
algorithms and data structures (base62, snowflake, LRU cache, rate limiter) —
each unit-testable with no I/O. `app/services/` holds business logic that
orchestrates core + persistence. `app/routers/` is a thin HTTP translation
layer. Dependency injection via FastAPI `Depends`.

**Consequences** — Clear separation of concerns; core modules have no DB or
HTTP dependencies, so their tests are blazing fast and pin failures precisely.

---

## ADR-004 — Short codes from snowflake IDs encoded as base62

**Context** — A short code must be unique, compact, and not guessably sequential
for security. Auto-increment DB IDs are sequential and enumerable; pure random
strings need a collision check (a race under load).

**Decision** — Generate 64-bit IDs with a Twitter-snowflake generator
(41-bit ms timestamp | 10-bit machine id | 12-bit sequence), then encode the ID
as base62 for the URL slug. K-sortable, collision-free across up to 1024
machines, and ~6–11 chars long.

**Consequences** — No collision checks needed. Machine id must be provisioned
per instance (env-configurable). Codes are not encrypted — sensitive links
should add an optional secret in a follow-up.

---

## ADR-005 — Read-through LRU cache with TTL, fronted by the DB

**Context** — Redirects are the hot path and hit the same popular codes
repeatedly; the DB should not be consulted on every hit.

**Decision** — A custom thread-safe LRU cache (`dict` + doubly-linked list,
O(1) get/put) with per-entry TTL and stats (hits/misses/evictions). The URL
service consults the cache on read and invalidates on delete. A single mutex
guards operations.

**Consequences** — Redirect latency drops to microseconds for hot keys.
Strict consistency on delete is handled by explicit invalidation. For
read-heavy traffic an RW lock would scale further (noted as a follow-up).

---

## ADR-006 — Token-bucket rate limiting keyed by client IP

**Context** — Unbounded shortening/redirects enable abuse (spam, scraping).

**Decision** — Per-key token-bucket limiter with lazy refill, capacity and
refill rate configurable via env. Implemented as a `RateLimiter` dependency that
raises `RateLimitExceededError`, mapped to HTTP 429 with a `Retry-After` header.

**Consequences** — Smoothed throttling that tolerates short bursts. Idle
buckets are reaped to bound memory. State is in-process; a distributed limiter
(Redis) is a documented scaling step.

---

## ADR-007 — Non-blocking click analytics via background tasks

**Context** — Recording a redirect click synchronously would add DB write
latency to every redirect.

**Decision** — Redirects enqueue a click event onto an in-memory
`AnalyticsBuffer` (a deque with a lock) and return immediately. A background
flusher batches events to the DB on an interval/batch-size threshold. The buffer
is drained on shutdown.

**Consequences** — Redirects stay fast. Under crash, a small in-flight batch
may be lost (acceptable for analytics). At scale this moves to a queue
(Kafka/SQS).

---

## ADR-008 — Tooling: ruff + mypy strict + pytest with coverage

**Context** — A maintainable project needs linting, typing, and coverage enforced consistently.

**Decision** — `ruff` for lint/format, `mypy --strict` for typing, `pytest`
with `pytest-cov` enforcing coverage on `app/`. CI runs the full matrix and
fails on regressions.

**Consequences** — Type and lint errors are caught at the gate. Strict mypy
raises the bar on the core algorithms especially.

---

## ADR-009 — Cache values carry the URL's own expiry (correctness)

**Context** — The LRU cache originally stored only the original URL string. A
URL with a TTL could still resolve from cache after its expiry, because the
cache hit path never re-checked the URL's expiry (only the cache's own TTL).

**Decision** — The cache stores a `CachedTarget(original_url, expires_at)`
rather than a bare string. `resolve` validates the URL's expiry on every cache
hit and invalidates the entry if it has expired. This keeps the cache consistent
with the source-of-truth DB record regardless of the two TTLs.

**Consequences** — Correct expiry even when the URL TTL is longer than the
cache TTL. A small per-hit comparison cost (negligible). Caught by the
`test_ttl_expiry_*` tests.

---

## ADR-010 — Analytics totals via COUNT, not the denormalized counter

**Context** — `URLRecord.click_count` is a denormalized counter incremented by
the flusher in a separate session. Reading it from a *reused* ORM session
returns a stale identity-map value; in general it lags the flusher by up to one
flush interval.

**Decision** — `get_analytics` computes `total_clicks` as a fresh SQL
`COUNT(*)` over `click_events` rather than reading the denormalized counter.
`get_stats` (the fast path) still reads the counter, which is fresh under the
normal per-request session model.

**Consequences** — Analytics is exact at query time (no stale reads). The
denormalized counter remains a fast-read optimization for the stats path.
Analytics is **eventually consistent** — clicks buffered since the last flush
are not yet counted; the flush interval (default 5s) bounds the lag. This is
documented and acceptable for click analytics.

---

## ADR-011 — SQLite busy-timeout to survive concurrent writers

**Context** — Load testing with 64 concurrent `POST /api/urls` (each a write +
commit) against SQLite returned 500s: SQLite's default busy-timeout is ~0, so a
writer that can't immediately acquire the write lock raises
`database is locked` instead of waiting.

**Decision** — Set a 30s busy-timeout on SQLite connections
(`connect_args["timeout"] = 30`) so contending writers wait for the lock rather
than erroring. The arg is sqlite-only; Postgres/MySQL are unaffected.

**Consequences** — Concurrent writes now serialize and complete instead of
failing. Under heavy write contention throughput drops (writes are inherently
serial in SQLite) — the benchmark reflects this honestly rather than masking
failures. A Postgres backend would remove the serialization ceiling.

---

## ADR-012 — Measure the cache win in-process, not over HTTP

**Context** — To produce a defensible performance number, the first instinct
was an end-to-end HTTP load test (httpx vs. uvicorn). But on the dev machine
(Windows + Python 3.14 + uvicorn single worker + sync-endpoint threadpool)
the per-request latency floor was ~7.5 ms even for the trivial `/health`
endpoint, and under concurrency the numbers became noisy enough that a cache
*hit* measured slower than a *miss*. The transport and threadpool dominated
and masked the algorithm.

**Decision** — Keep an HTTP load test (`bench/benchmark.py`) for end-to-end
sanity, but measure the **algorithmic** cache-vs-DB win **in-process**
(`bench/microbench.py`) with no HTTP, no threadpool, and no transport. The
microbenchmark times the real `URLService.resolve` path: a cache hit (~750 ns)
versus a cache miss that reads SQLite via the ORM (~485 µs) — a measured
~150x–650x improvement depending on whether the ORM overhead is counted.

**Consequences** — The in-process number is reproducible and isolates exactly
what the cache contributes, independent of the host's transport overhead. The
HTTP numbers are reported but explicitly labelled environment-bound and not
cited as the algorithmic claim. This also reflects the judgment of measuring
the right thing: a wall-clock that includes unrelated transport overhead is not
a fair measure of a hash-map lookup vs. a DB read.



