#!/usr/bin/env python3
"""
api_latency_monitor.py
Interactive API / Website latency checker (clean, production mode)

Usage:
    python api_latency_monitor.py
It will prompt for URLs (comma-separated), samples, timeout, concurrency, and whether to spoof User-Agent.
Outputs:
    api_latency_detailed.csv
    api_latency_summary.csv
"""
import sys
import time
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean, stdev
from datetime import datetime

try:
    import requests
except Exception:
    print("Missing dependency 'requests'. Install: python -m pip install requests")
    sys.exit(1)

DEFAULT_TIMEOUT = 6
DEFAULT_SAMPLES = 3
DEFAULT_CONCURRENCY = 6
OUTPUT_DETAILED = "api_latency_detailed.csv"
OUTPUT_SUMMARY = "api_latency_summary.csv"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ParadoxBot/1.0"

def measure_once(session, url, timeout):
    try:
        t0 = time.perf_counter()
        r = session.get(url, timeout=timeout)
        t1 = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000, 2)
        size = len(r.content) if r.content is not None else 0
        return r.status_code, latency_ms, size, None
    except Exception as e:
        return None, None, None, str(e)

def measure_multiple(session, url, samples, timeout, executor):
    futures = [executor.submit(measure_once, session, url, timeout) for _ in range(samples)]
    results = []
    for fut in as_completed(futures):
        results.append(fut.result())
    return results

def aggregate_results(results):
    latencies = [r[1] for r in results if r[1] is not None]
    statuses = [r[0] for r in results if r[0] is not None]
    errors = [r[3] for r in results if r[3] is not None]
    return {
        "count": len(results),
        "success_count": len([s for s in statuses if str(s).isdigit() and 200 <= int(s) < 400]),
        "failure_count": len(errors),
        "min_ms": round(min(latencies),2) if latencies else None,
        "avg_ms": round(mean(latencies),2) if latencies else None,
        "max_ms": round(max(latencies),2) if latencies else None,
        "stdev_ms": round(stdev(latencies),2) if len(latencies) > 1 else 0.0
    }

def write_csv(filename, fieldnames, rows):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    print("API Latency Monitor — interactive")
    urls_input = input("Enter URLs (comma separated, include http/https) or paste a single URL: ").strip()
    if not urls_input:
        print("No URLs provided. Exiting.")
        return
    urls = [u.strip() for u in urls_input.split(",") if u.strip()]

    try:
        samples = int(input(f"Samples per URL (default {DEFAULT_SAMPLES}): ") or DEFAULT_SAMPLES)
    except Exception:
        samples = DEFAULT_SAMPLES

    try:
        timeout = float(input(f"Request timeout secs (default {DEFAULT_TIMEOUT}): ") or DEFAULT_TIMEOUT)
    except Exception:
        timeout = DEFAULT_TIMEOUT

    try:
        concurrency = int(input(f"Concurrency threads (default {DEFAULT_CONCURRENCY}): ") or DEFAULT_CONCURRENCY)
    except Exception:
        concurrency = DEFAULT_CONCURRENCY

    ua_choice = input("Spoof User-Agent header? (y/N): ").strip().lower()
    headers = {"User-Agent": USER_AGENT} if ua_choice == "y" else {}

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    detailed_rows = []
    summary_rows = []

    with requests.Session() as session:
        if headers:
            session.headers.update(headers)
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for url in urls:
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = "https://" + url
                print(f"Checking {url} ...")
                results = measure_multiple(session, url, samples, timeout, executor)
                for idx, (status, latency, size, error) in enumerate(results, start=1):
                    detailed_rows.append({
                        "checked_at": timestamp,
                        "url": url,
                        "sample_index": idx,
                        "status": status or "",
                        "latency_ms": latency or "",
                        "response_bytes": size or "",
                        "error": error or ""
                    })
                agg = aggregate_results(results)
                summary_rows.append({
                    "checked_at": timestamp,
                    "url": url,
                    "samples": agg["count"],
                    "success_count": agg["success_count"],
                    "failure_count": agg["failure_count"],
                    "min_ms": agg["min_ms"],
                    "avg_ms": agg["avg_ms"],
                    "max_ms": agg["max_ms"],
                    "stdev_ms": agg["stdev_ms"]
                })
                if agg["avg_ms"] is not None:
                    print(f"Result: avg {agg['avg_ms']} ms, successes {agg['success_count']}/{agg['count']}")
                else:
                    print("Result: no successful requests")

    write_csv(OUTPUT_DETAILED, ["checked_at","url","sample_index","status","latency_ms","response_bytes","error"], detailed_rows)
    write_csv(OUTPUT_SUMMARY, ["checked_at","url","samples","success_count","failure_count","min_ms","avg_ms","max_ms","stdev_ms"], summary_rows)
    print(f"\nSaved: {OUTPUT_DETAILED} and {OUTPUT_SUMMARY}")

if __name__ == "__main__":
    main()