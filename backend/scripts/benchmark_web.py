"""
Benchmark and regression test for Page Scout (type "web") URL behaviors.

Tests three distinct URL behaviors that the Page Scout handles:
1. Blocked URL (nytimes.com) — scraper_status=False
2. Normal URL (neunkirch.ch) — full changeTracking works (firecrawl)
3. Normal URL (politico.com) — full changeTracking works (firecrawl)

Usage:
    cd backend
    python scripts/benchmark_web.py          # Run all 3 URL tests
"""
import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.scout_service import ScoutService

BENCHMARK_USER_ID = "benchmark-web-test"
# Unique per run so the double-probe tag has no stale baseline from prior runs.
# This simulates a user testing a brand-new scout (fresh tag, no prior baseline).
BENCHMARK_SCRAPER_NAME = f"bench-{uuid.uuid4().hex[:8]}"

TEST_CASES = [
    {
        "name": "Blocked URL (nytimes.com)",
        "url": "https://www.nytimes.com/2025/01/15/us/politics/trump-executive-orders.html",
        "expect_scraper_status": False,
        "expect_provider": None,  # Not checked when scraper fails
    },
    {
        "name": "Normal URL (neunkirch.ch)",
        "url": "https://www.neunkirch.ch/freizeit/veranstaltungen.html/23",
        "expect_scraper_status": True,
        "expect_provider": "firecrawl",
    },
    {
        "name": "Normal URL (politico.com)",
        "url": "https://www.politico.com",
        "expect_scraper_status": True,
        "expect_provider": "firecrawl",
    },
]


async def run_test_case(scout_service: ScoutService, case: dict) -> dict:
    """Run a single test case matching the /scouts/test endpoint behavior.

    Runs preview scrape (Task A) and double_probe (Task B) concurrently.
    """
    start = time.time()

    preview_task = asyncio.create_task(
        scout_service.execute(
            url=case["url"],
            user_id=BENCHMARK_USER_ID,
            scraper_name=BENCHMARK_SCRAPER_NAME,
            skip_duplicate_check=True,
            skip_notification=True,
            skip_credit_charge=True,
            preview_mode=True,
        )
    )

    probe_task = asyncio.create_task(
        scout_service.double_probe(
            url=case["url"],
            user_id=BENCHMARK_USER_ID,
            scraper_name=BENCHMARK_SCRAPER_NAME,
        )
    )

    result = await preview_task
    elapsed = time.time() - start

    if result.get("scraper_status"):
        provider = await probe_task
    else:
        probe_task.cancel()
        provider = None

    # Check assertions
    scraper_ok = result.get("scraper_status") == case["expect_scraper_status"]

    if case["expect_provider"] is not None:
        provider_ok = provider == case["expect_provider"]
    else:
        provider_ok = True  # Not checked for failed scrapes

    passed = scraper_ok and provider_ok

    return {
        "name": case["name"],
        "url": case["url"],
        "elapsed_s": round(elapsed, 1),
        "scraper_status": result.get("scraper_status"),
        "provider": provider,
        "expect_scraper_status": case["expect_scraper_status"],
        "expect_provider": case["expect_provider"],
        "scraper_ok": scraper_ok,
        "provider_ok": provider_ok,
        "passed": passed,
        "summary": (result.get("summary") or "")[:80],
    }


async def run_benchmark():
    scout_service = ScoutService()
    results = []

    print("=" * 70)
    print("PAGE SCOUT (WEB) REGRESSION BENCHMARK")
    print("(preview scrape + double_probe in parallel per URL)")
    print("=" * 70)

    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {case['name']}")
        print(f"  URL: {case['url']}")

        r = await run_test_case(scout_service, case)
        results.append(r)

        status_icon = "PASS" if r["passed"] else "FAIL"
        print(f"  Time: {r['elapsed_s']}s")
        print(f"  scraper_status: {r['scraper_status']} (expected {r['expect_scraper_status']}) {'OK' if r['scraper_ok'] else 'MISMATCH'}")
        if r["expect_provider"] is not None:
            print(f"  provider: {r['provider']} (expected {r['expect_provider']}) {'OK' if r['provider_ok'] else 'MISMATCH'}")
        if r["summary"]:
            print(f"  summary: {r['summary']}")
        print(f"  Result: [{status_icon}]")

    # Summary table
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  {'Test':<45} {'Status':<10} {'Time':>6}")
    print(f"  {'-'*45} {'-'*10} {'-'*6}")
    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['name']:<45} {icon:<10} {r['elapsed_s']:>5.1f}s")
    print(f"\n  Passed: {passed}/{len(results)}")
    if failed:
        print(f"  Failed: {failed}/{len(results)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_benchmark())
    sys.exit(exit_code)
