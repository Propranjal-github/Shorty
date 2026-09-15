r"""End-to-end HTTP load + latency benchmark for Shorty.

Measures shorten, redirect (cache HIT), and redirect (cache MISS) over real HTTP.
NOTE: these numbers are environment-bound — on a single dev machine the latency
floor is dominated by the OS network stack + the sync-endpoint threadpool +
httpx, NOT the cache algorithm. For the *algorithmic* win (cache vs DB), run
bench/microbench.py instead — that isolates the cache-vs-DB win.

Run the server with the rate limiter off and cache forced to capacity 1 (so
distinct codes miss), then in another terminal:

    backend\.venv\Scripts\python.exe bench\benchmark.py
"""

from __future__ import annotations

import asyncio
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] if lo == hi else sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def summarize(label: str, lats: list[float], duration: float) -> None:
    s = sorted(lats)
    rps = len(s) / duration if duration else 0.0
    print(
        f"  {label:<24} {len(s):>6d} reqs in {duration:6.2f}s = {rps:>7,.0f} req/s | "
        f"p50 {percentile(s,50):6.2f}ms  p95 {percentile(s,95):6.2f}ms  p99 {percentile(s,99):6.2f}ms"
    )


async def drive(
    client: httpx.AsyncClient,
    request,  # callable(client) -> Awaitable
    n: int,
    concurrency: int,
) -> tuple[list[float], float]:
    sem = asyncio.Semaphore(concurrency)
    lats: list[float] = []

    async def one() -> None:
        async with sem:
            t0 = time.perf_counter()
            await request(client)
            lats.append((time.perf_counter() - t0) * 1000.0)

    t0 = time.perf_counter()
    await asyncio.wait_for(asyncio.gather(*(one() for _ in range(n))), timeout=120)
    return lats, time.perf_counter() - t0


async def shorten(client: httpx.AsyncClient, sink: list[str]) -> None:
    r = await client.post(f"{BASE}/api/urls", json={"url": "https://example.com/bench"})
    if r.status_code >= 400:
        raise RuntimeError(f"shorten {r.status_code}: {r.text[:160]}")
    sink.append(r.json()["short_code"])


async def redirect(client: httpx.AsyncClient, code: str) -> None:
    r = await client.get(f"{BASE}/{code}", follow_redirects=False)
    if r.status_code != 302:
        raise RuntimeError(f"redirect {r.status_code}: {r.text[:160]}")


async def main() -> int:
    limits = httpx.Limits(max_connections=64, max_keepalive_connections=64)
    async with httpx.AsyncClient(limits=limits, timeout=15) as client:
        try:
            h = await client.get(f"{BASE}/health", timeout=5)
            h.raise_for_status()
        except Exception as e:
            print(f"Server not reachable at {BASE}: {e}\nStart it first (see module docstring).")
            return 1

        codes: list[str] = []
        # Phase A: shorten (writes serialize in SQLite -> low concurrency is honest)
        lats, dur = await drive(client, lambda c: shorten(c, codes), n=200, concurrency=8)
        summarize("Shorten (POST)", lats, dur)

        # Phase B: cache HIT (one hot code)
        hot = codes[0]
        await redirect(client, hot)  # warm
        lats, dur = await drive(client, lambda c: redirect(c, hot), n=5000, concurrency=32)
        summarize("Redirect (cache HIT)", lats, dur)

        # Phase C: cache MISS (distinct codes; requires SHORTY_CACHE_CAPACITY=1)
        idx = 0
        miss_codes = codes

        async def miss(c: httpx.AsyncClient) -> None:
            nonlocal idx
            await redirect(c, miss_codes[idx % len(miss_codes)])
            idx += 1

        lats, dur = await drive(client, miss, n=2000, concurrency=16)
        summarize("Redirect (cache MISS)", lats, dur)

    print(
        "\nEnd-to-end numbers above are transport/threadpool-bound. For the "
        "algorithmic cache-vs-DB speedup, run: bench/microbench.py"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
