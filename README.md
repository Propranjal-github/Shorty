# Shorty — a distributed URL shortener

A distributed URL shortener with a read-through LRU cache, snowflake ID
generation, token-bucket rate limiting, and non-blocking click analytics.
Backend in Python (FastAPI), frontend in React + TypeScript.

> **Design decisions** are recorded as ADRs in [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md).

---

## What it does

- Shorten any `http(s)` URL to a compact, k-sortable code (`POST /api/urls`).
- Redirect with `302` and record a click (`GET /{code}`).
- Optional **custom codes** and **TTL expiry**.
- Per-URL **analytics**: hourly click buckets + top referrers.
- A **React + TypeScript** UI to exercise the API end to end.

## Features

- **Shorten & redirect** — base62 short codes from snowflake IDs; `302` redirects with click recording.
- **Read-through LRU cache** — hash map + doubly-linked list, TTL-aware and thread-safe, so redirects skip the DB on cache hits.
- **Token-bucket rate limiting** — per-client throttling mapped to HTTP 429 with `Retry-After`.
- **Non-blocking analytics** — clicks buffered in memory and flushed in batches to the DB by a background worker.
- **Clean architecture** — pure, I/O-free `core/` algorithms; `routers → services → core` layering with dependency injection.
- **Tested & typed** — `pytest` (46 tests, ~93% coverage), `mypy --strict`, `ruff`, GitHub Actions CI.
- **Docker** — multi-stage images and `docker-compose` for the full stack.

## Architecture

```
backend/app
├── core/            # pure algorithms: encoder, snowflake, LRU cache, rate limiter
├── models.py        # SQLAlchemy ORM (URLRecord, ClickEvent)
├── schemas.py       # Pydantic v2 request/response models
├── services/        # URLService (business logic), AnalyticsBuffer (async flusher)
├── routers/         # thin HTTP translation (urls, analytics, health)
├── deps.py         # singletons + dependency injection
├── database.py      # engine + session
└── main.py          # FastAPI app: CORS, lifespan, exception handlers
frontend/src          # Vite + React + TS: shortener form, link list, analytics charts
```

**Request flow (redirect):** `GET /{code}` → `URLService.resolve` → LRU cache → (miss) DB
lookup → return original URL + enqueue a click to the `AnalyticsBuffer` (no DB
write on the hot path). The background flusher batches clicks to the DB.

## Getting started

### Backend (local)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows; source .venv/bin/activate on *nix
pip install -e ".[dev]"
pytest                                              # 46 tests, ~93% coverage
uvicorn app.main:app --reload                       # http://localhost:8000/docs
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (proxies /api -> :8000)
```

### Everything via Docker

```bash
docker compose up --build
# UI:  http://localhost:8080
# API: http://localhost:8000/docs  (redirects resolve here too)
```

## API reference

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/urls` | Shorten `{ url, custom_code?, ttl_seconds? }` → `201` |
| `GET` | `/{code}` | Redirect to the original URL (`302`); records a click |
| `GET` | `/api/urls/{code}` | Stats (original URL, click count, expiry) |
| `DELETE` | `/api/urls/{code}` | Delete a link (`204`) |
| `GET` | `/api/urls/{code}/analytics?hours=24` | Hourly buckets + top referrers |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/_internal/stats` | Cache / rate-limiter / buffer observability |

## Benchmarks

`bench/` has two scripts (see [`bench/README.md`](bench/README.md)):

- **`microbench.py`** — measures the real `resolve` path in-process (no HTTP):
  a cache hit (~750 ns) vs a cache miss that reads SQLite (~114 µs raw / ~485 µs
  via the ORM) — a measured **~150x–650x** difference.
- **`benchmark.py`** — end-to-end HTTP load test (throughput + p50/p95/p99).
  Environment-bound on a dev box.

## Configuration

All settings are environment variables (prefix `SHORTY_`); see
[`backend/.env.example`](backend/.env.example). Notable ones:

- `SHORTY_DATABASE_URL` — SQLite by default; swap for Postgres/MySQL in production.
- `SHORTY_MACHINE_ID` — **must be unique per process/instance** (0..1023).
- `SHORTY_RATE_LIMIT_*`, `SHORTY_CACHE_*`, `SHORTY_ANALYTICS_*` — tune capacity.

## Scaling notes (intentionally documented, not built)

- Replace in-process cache/limiter with Redis for multi-instance correctness.
- Move the analytics buffer to Kafka/SQS for durable, at-least-once ingestion.
- Switch to async SQLAlchemy + Postgres for higher redirect throughput.

## License

MIT
