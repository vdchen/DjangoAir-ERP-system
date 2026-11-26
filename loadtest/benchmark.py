#!/usr/bin/env python3
"""Zero-dependency concurrent HTTP benchmark measuring RPS and p50/p95/p99 latencies."""
import argparse
import concurrent.futures
import math
import time
import urllib.request
from datetime import datetime, timedelta, timezone


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, math.ceil(len(sorted_vals) * pct / 100.0) - 1))
    return sorted_vals[idx]


def run_benchmark(base_url: str, path: str, total_requests: int, concurrency: int) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    latencies_ms: list[float] = []
    errors = 0

    def _hit(_idx: int) -> tuple[bool, float]:
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                resp.read()
                ok = 200 <= resp.status < 300
        except Exception:
            ok = False
        return ok, (time.perf_counter() - t0) * 1000.0

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for ok, ms in pool.map(_hit, range(total_requests)):
            if ok:
                latencies_ms.append(ms)
            else:
                errors += 1
    elapsed = time.perf_counter() - started
    latencies_ms.sort()

    return {
        "path": path,
        "requests": total_requests,
        "concurrency": concurrency,
        "errors": errors,
        "rps": round(total_requests / elapsed, 1),
        "p50_ms": round(percentile(latencies_ms, 50), 1),
        "p95_ms": round(percentile(latencies_ms, 95), 1),
        "p99_ms": round(percentile(latencies_ms, 99), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="DjangoAir HTTP Latency & RPS Benchmark")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=16)
    args = parser.parse_args()

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    targets = [
        "/api/v1/health/live/",
        "/api/v1/fleet/airports/",
        f"/api/v1/flights/search/?destination=LHR&date={tomorrow}&passengers=1",
    ]
    print(f"Benchmarking {args.base_url} ({args.requests} reqs @ concurrency={args.concurrency})\n")
    print(f"{'Endpoint':<58} {'RPS':>8} {'p50(ms)':>9} {'p95(ms)':>9} {'p99(ms)':>9} {'Err':>5}")
    print("-" * 104)
    for path in targets:
        res = run_benchmark(args.base_url, path, args.requests, args.concurrency)
        print(
            f"{res['path']:<58} {res['rps']:>8.1f} {res['p50_ms']:>9.1f} "
            f"{res['p95_ms']:>9.1f} {res['p99_ms']:>9.1f} {res['errors']:>5d}"
        )


if __name__ == "__main__":
    main()
