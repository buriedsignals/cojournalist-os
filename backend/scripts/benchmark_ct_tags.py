"""
Diagnostic: isolate what causes Firecrawl to drop changeTracking baselines.

Tests different tag formats to find which ones persist vs get dropped:
1. Short simple tag (control — known to work)
2. Long tag (UUID length, no special chars)
3. Tag with # character
4. Tag with spaces
5. Tag matching exact production format (UUID#name with spaces)
6. Tag matching production format but # replaced with _
7. Tag matching production format but spaces replaced with -

For each tag, runs double-probe then waits 60s and re-checks.

Usage:
    cd backend
    python3 scripts/benchmark_ct_tags.py
"""
import asyncio
import os
import sys
import time
import uuid
import json
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings
from app.services.http_client import get_http_client

settings = get_settings()
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"

# Use a sub-page to avoid interference with existing baselines on the homepage
TEST_URL = "https://www.itromso.no/nyheter"

# Generate unique suffix so no stale baselines from prior runs
RUN_ID = uuid.uuid4().hex[:6]

TAG_TESTS = [
    {
        "name": "1. Short simple",
        "tag": f"test-short-{RUN_ID}",
    },
    {
        "name": "2. Long no specials",
        "tag": f"c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c-DEV-Tromso-Real-estate-{RUN_ID}",
    },
    {
        "name": "3. With # char",
        "tag": f"user123#{RUN_ID}",
    },
    {
        "name": "4. With spaces",
        "tag": f"user123 scout name {RUN_ID}",
    },
    {
        "name": "5. Exact prod format (UUID#name spaces)",
        "tag": f"c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c#DEV Tromso {RUN_ID}",
    },
    {
        "name": "6. UUID_name (# replaced)",
        "tag": f"c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c_DEV_Tromso_{RUN_ID}",
    },
    {
        "name": "7. UUID-name (sanitized)",
        "tag": f"c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c-DEV-Tromso-{RUN_ID}",
    },
]


async def firecrawl_scrape(url: str, tag: str):
    """Scrape with changeTracking, return (changeStatus, previousScrapeAt, success)."""
    client = await get_http_client()
    response = await client.post(
        FIRECRAWL_URL,
        headers={
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "url": url,
            "formats": ["markdown", {"type": "changeTracking", "tag": tag}],
            "onlyMainContent": True,
        },
        timeout=60.0,
    )
    if response.status_code != 200:
        return None, None, False
    result = response.json()
    if not result.get("success", True):
        return None, None, False
    ct = result.get("data", {}).get("changeTracking", {})
    return ct.get("changeStatus"), ct.get("previousScrapeAt"), True


async def test_tag(test: dict) -> dict:
    """Run double-probe for a tag, then verify after wait."""
    tag = test["tag"]
    name = test["name"]

    # Call 1: establish baseline
    cs1, ps1, ok1 = await firecrawl_scrape(TEST_URL, tag)
    if not ok1:
        return {**test, "call1": "FAILED", "call2": "SKIPPED", "verify": "SKIPPED"}

    # Call 2: verify baseline stored
    cs2, ps2, ok2 = await firecrawl_scrape(TEST_URL, tag)
    if not ok2:
        return {**test, "call1": f"{cs1}", "call2": "FAILED", "verify": "SKIPPED"}

    baseline_stored = ps2 is not None

    return {
        **test,
        "call1_status": cs1,
        "call1_prev": ps1,
        "call2_status": cs2,
        "call2_prev": ps2,
        "baseline_stored": baseline_stored,
        "verify_status": None,  # filled in later
        "verify_prev": None,
    }


async def run():
    print("=" * 72)
    print("CHANGETRACKING TAG FORMAT ISOLATION TEST")
    print(f"URL: {TEST_URL}")
    print(f"Run ID: {RUN_ID}")
    print("=" * 72)

    results = []

    # Phase 1: Double-probe all tags
    print("\n── Phase 1: Double-probe each tag ──\n")
    for test in TAG_TESTS:
        print(f"  {test['name']}")
        print(f"    tag: {test['tag']}")
        r = await test_tag(test)
        results.append(r)
        stored = r.get("baseline_stored", False)
        print(f"    Call 1: changeStatus={r.get('call1_status')}  previousScrapeAt={r.get('call1_prev')}")
        print(f"    Call 2: changeStatus={r.get('call2_status')}  previousScrapeAt={r.get('call2_prev')}")
        print(f"    Baseline: {'STORED' if stored else 'DROPPED'}")
        print()

    # Phase 2: Wait then re-verify all
    wait_secs = 90
    print(f"── Phase 2: Waiting {wait_secs}s then re-verifying all baselines ──\n")
    for remaining in range(wait_secs, 0, -10):
        print(f"  {remaining}s remaining...", flush=True)
        await asyncio.sleep(min(10, remaining))
    print()

    for r in results:
        if not r.get("baseline_stored"):
            r["verify_status"] = "SKIPPED"
            r["verify_prev"] = None
            continue
        cs, ps, ok = await firecrawl_scrape(TEST_URL, r["tag"])
        r["verify_status"] = cs
        r["verify_prev"] = ps
        r["baseline_persisted"] = ps is not None

    # Summary
    print("=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"  {'Test':<38} {'Tag len':>7} {'Probe':>8} {'After {0}s':>10}".format(wait_secs))
    print(f"  {'-'*38} {'-'*7} {'-'*8} {'-'*10}")
    for r in results:
        stored = "STORED" if r.get("baseline_stored") else "DROPPED"
        persisted = "N/A"
        if r.get("baseline_stored"):
            persisted = "ALIVE" if r.get("baseline_persisted") else "GONE"
        print(f"  {r['name']:<38} {len(r['tag']):>7} {stored:>8} {persisted:>10}")

    # Identify the pattern
    print(f"\n── Analysis ──\n")
    dropped_at_probe = [r for r in results if not r.get("baseline_stored")]
    dropped_after_wait = [r for r in results if r.get("baseline_stored") and not r.get("baseline_persisted")]
    survived = [r for r in results if r.get("baseline_persisted")]

    if dropped_at_probe:
        print("  Tags where baseline DROPPED immediately (double-probe failed):")
        for r in dropped_at_probe:
            print(f"    - {r['name']}: tag={r['tag']}")

    if dropped_after_wait:
        print(f"  Tags where baseline DROPPED after {wait_secs}s:")
        for r in dropped_after_wait:
            print(f"    - {r['name']}: tag={r['tag']}")

    if survived:
        print(f"  Tags where baseline SURVIVED after {wait_secs}s:")
        for r in survived:
            print(f"    - {r['name']}: tag={r['tag']}")

    if not dropped_at_probe and not dropped_after_wait:
        print("  All baselines survived! Issue may be time-dependent (>90s).")


if __name__ == "__main__":
    asyncio.run(run())
