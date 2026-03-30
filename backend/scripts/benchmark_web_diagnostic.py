"""
Diagnostic benchmark for Page Scout changeTracking baseline behavior.

Traces each step of the double-probe with intermediate verification
to identify exactly where/when baselines are lost.

Usage:
    cd backend
    python scripts/benchmark_web_diagnostic.py
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

TEST_URL = "https://www.itromso.no/"
TAG = f"diag-{uuid.uuid4().hex[:8]}"


async def firecrawl_scrape(url: str, tag: str = None):
    """Raw Firecrawl v2 scrape, returns full data dict."""
    formats = ["markdown"]
    if tag:
        formats.append({"type": "changeTracking", "tag": tag})

    client = await get_http_client()
    response = await client.post(
        FIRECRAWL_URL,
        headers={
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        },
        json={"url": url, "formats": formats, "onlyMainContent": True},
        timeout=60.0,
    )
    if response.status_code != 200:
        return None, response.status_code, response.text[:200]
    result = response.json()
    if not result.get("success", True):
        return None, response.status_code, result.get("error")
    return result.get("data", {}), response.status_code, None


def print_ct(label: str, data: dict):
    """Print changeTracking details from a scrape result."""
    ct = data.get("changeTracking", {}) if data else {}
    md = data.get("markdown", "") if data else ""
    md_hash = hashlib.sha256(md.encode()).hexdigest()[:16] if md else "NONE"

    print(f"  {label}:")
    print(f"    success:          {data is not None}")
    print(f"    changeStatus:     {ct.get('changeStatus', 'MISSING')}")
    print(f"    previousScrapeAt: {ct.get('previousScrapeAt', 'MISSING')}")
    print(f"    visibility:       {ct.get('visibility', 'MISSING')}")
    print(f"    ct keys:          {list(ct.keys()) if ct else 'EMPTY'}")
    print(f"    markdown length:  {len(md)}")
    print(f"    markdown hash:    {md_hash}")
    return ct


async def run_diagnostic():
    print("=" * 70)
    print("PAGE SCOUT CHANGETRACKING DIAGNOSTIC")
    print(f"URL: {TEST_URL}")
    print(f"Tag: {TAG}")
    print("=" * 70)

    # ── Step 1: Plain scrape (no changeTracking) ──
    print(f"\n── Step 1: Plain scrape (no tag) ──")
    t0 = time.time()
    data1, status1, err1 = await firecrawl_scrape(TEST_URL)
    print(f"  Time: {time.time()-t0:.1f}s  Status: {status1}")
    if err1:
        print(f"  ERROR: {err1}")
        return
    md1 = data1.get("markdown", "")
    hash1 = hashlib.sha256(md1.encode()).hexdigest()
    print(f"  Markdown length: {len(md1)}")
    print(f"  Content hash:    {hash1[:32]}...")

    # ── Step 2: First changeTracking call (establish baseline) ──
    print(f"\n── Step 2: Call 1 with tag (establish baseline) ──")
    t0 = time.time()
    data2, status2, err2 = await firecrawl_scrape(TEST_URL, tag=TAG)
    elapsed2 = time.time() - t0
    print(f"  Time: {elapsed2:.1f}s  Status: {status2}")
    if err2:
        print(f"  ERROR: {err2}")
        return
    ct2 = print_ct("Call 1 result", data2)

    # ── Step 3: Immediate verification (is baseline stored?) ──
    print(f"\n── Step 3: Call 2 with same tag (verify baseline) ──")
    t0 = time.time()
    data3, status3, err3 = await firecrawl_scrape(TEST_URL, tag=TAG)
    elapsed3 = time.time() - t0
    print(f"  Time: {elapsed3:.1f}s  Status: {status3}")
    if err3:
        print(f"  ERROR: {err3}")
        return
    ct3 = print_ct("Call 2 result", data3)

    previous_scrape = ct3.get("previousScrapeAt")
    if previous_scrape:
        print(f"\n  >> BASELINE CONFIRMED: previousScrapeAt={previous_scrape}")
        probe_result = "firecrawl"
    else:
        print(f"\n  >> BASELINE DROPPED: previousScrapeAt is null/missing")
        probe_result = "firecrawl_plain"

    # ── Step 4: Wait 5 seconds, check again ──
    print(f"\n── Step 4: Wait 5s, then verify baseline persistence ──")
    await asyncio.sleep(5)
    t0 = time.time()
    data4, status4, err4 = await firecrawl_scrape(TEST_URL, tag=TAG)
    elapsed4 = time.time() - t0
    print(f"  Time: {elapsed4:.1f}s  Status: {status4}")
    if err4:
        print(f"  ERROR: {err4}")
    else:
        ct4 = print_ct("After 5s", data4)
        if ct4.get("previousScrapeAt"):
            print(f"  >> Still persisted after 5s")
        else:
            print(f"  >> LOST after 5s!")

    # ── Step 5: Compare markdown content across calls ──
    print(f"\n── Step 5: Content comparison ──")
    md2 = data2.get("markdown", "") if data2 else ""
    md3 = data3.get("markdown", "") if data3 else ""
    md4 = data4.get("markdown", "") if data4 else ""

    h2 = hashlib.sha256(md2.encode()).hexdigest()[:16]
    h3 = hashlib.sha256(md3.encode()).hexdigest()[:16]
    h4 = hashlib.sha256(md4.encode()).hexdigest()[:16]

    print(f"  Plain scrape hash:  {hashlib.sha256(md1.encode()).hexdigest()[:16]}")
    print(f"  Call 1 hash:        {h2}")
    print(f"  Call 2 hash:        {h3}")
    print(f"  After 5s hash:      {h4}")
    print(f"  All same content:   {h2 == h3 == h4}")

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'=' * 70}")
    print(f"  URL:                {TEST_URL}")
    print(f"  Tag:                {TAG}")
    print(f"  Provider decision:  {probe_result}")
    print(f"  Baseline after probe: {'STORED' if previous_scrape else 'DROPPED'}")
    print(f"  Baseline after 5s:    {'STORED' if data4 and data4.get('changeTracking', {}).get('previousScrapeAt') else 'DROPPED'}")

    if probe_result == "firecrawl":
        print(f"\n  Conclusion: changeTracking works for this URL.")
        print(f"  If baselines disappear later, Firecrawl has a retention window.")
    else:
        print(f"\n  Conclusion: changeTracking baseline is silently dropped.")
        print(f"  This URL should use firecrawl_plain (hash-based detection).")


if __name__ == "__main__":
    asyncio.run(run_diagnostic())
