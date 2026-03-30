"""
Benchmark Apify scraper actors — tests that each actor returns valid data.

Tests each scraper with a known public URL/profile, validates the raw
Apify output and the normalized output. Designed as a quick smoke test
to catch actor breakages before they hit the UI.

Usage:
    cd backend
    python scripts/benchmark_scrapers.py
"""
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.apify_client import (
    ApifyClient,
    ApifyError,
    start_twitter_scraper_async,
    check_twitter_scraper_status,
    start_instagram_scraper_async,
    check_instagram_scraper_status,
    start_facebook_scraper_async,
    check_facebook_scraper_status,
    start_instagram_comments_async,
    check_instagram_comments_status,
)
from app.workflows.data_extractor import (
    normalize_apify_results,
    normalize_instagram_results,
    normalize_facebook_results,
    normalize_instagram_comments,
)
from app.services.social_orchestrator import (
    normalize_instagram_posts as social_normalize_ig,
    normalize_x_posts as social_normalize_x,
    normalize_facebook_posts as social_normalize_fb,
)
from app.config import get_settings


# =============================================================================
# Test cases — known public profiles/posts
# =============================================================================

TESTS = [
    {
        "name": "X/Twitter: @NASA",
        "scraper": "twitter",
        "url": "https://x.com/NASA",
        "min_items": 1,
        "required_fields": ["id", "text", "url"],
    },
    {
        "name": "Instagram Posts: @nasa",
        "scraper": "instagram",
        "url": "https://www.instagram.com/nasa/",
        "min_items": 1,
        "required_fields": ["id", "code", "caption"],
    },
    {
        "name": "Facebook Profile: NASA",
        "scraper": "facebook",
        "url": "https://www.facebook.com/NASA/",
        "min_items": 1,
        # First item may be a profile_id metadata row; required_fields checked
        # on the first item with post_id present
        "required_fields": ["post_id", "message"],
        "find_sample_with": "post_id",
    },
    {
        "name": "Instagram Comments: NASA post",
        "scraper": "instagram_comments",
        # Use a recent NASA post with high engagement (likely to have comments)
        "url": "https://www.instagram.com/p/DN8-GjPkgjS",
        "min_items": 1,
        "required_fields": ["id", "text", "ownerUsername"],
    },
]

# How long to wait for each scraper (seconds)
POLL_TIMEOUT = 120
POLL_INTERVAL = 3


# =============================================================================
# Scraper runners
# =============================================================================


async def run_scraper(test: dict) -> dict:
    """Start a scraper, poll until done, return raw + normalized results."""
    scraper = test["scraper"]
    url = test["url"]
    start = time.time()

    try:
        # Start
        if scraper == "twitter":
            run_id = await start_twitter_scraper_async(url, max_tweets=5)
        elif scraper == "instagram":
            run_id = await start_instagram_scraper_async(url, max_items=5)
        elif scraper == "facebook":
            run_id = await start_facebook_scraper_async(url, max_items=5)
        elif scraper == "instagram_comments":
            run_id = await start_instagram_comments_async(url, max_items=10)
        else:
            return {"error": f"Unknown scraper: {scraper}", "elapsed_ms": 0}

        # Poll
        for _ in range(POLL_TIMEOUT // POLL_INTERVAL):
            await asyncio.sleep(POLL_INTERVAL)

            if scraper == "twitter":
                result = await check_twitter_scraper_status(run_id)
            elif scraper == "instagram":
                result = await check_instagram_scraper_status(run_id)
            elif scraper == "facebook":
                result = await check_facebook_scraper_status(run_id)
            elif scraper == "instagram_comments":
                result = await check_instagram_comments_status(run_id)

            if result["normalized_status"] == "completed":
                raw_items = result.get("data") or []
                elapsed = int((time.time() - start) * 1000)

                # Filter error/metadata items
                valid_items = [
                    item for item in raw_items
                    if isinstance(item, dict)
                    and not item.get("error")
                    and not item.get("requestErrorMessages")
                ]

                # Normalize with both data_extractor and social_orchestrator normalizers
                normalized_data = []
                normalized_social = []
                if scraper == "twitter":
                    normalized_data = normalize_apify_results(valid_items)
                    normalized_social = [p.__dict__ for p in social_normalize_x(valid_items)]
                elif scraper == "instagram":
                    normalized_data = normalize_instagram_results(valid_items)
                    normalized_social = [p.__dict__ for p in social_normalize_ig(valid_items)]
                elif scraper == "facebook":
                    normalized_data = normalize_facebook_results(valid_items)
                    normalized_social = [p.__dict__ for p in social_normalize_fb(valid_items)]
                elif scraper == "instagram_comments":
                    normalized_data = normalize_instagram_comments(valid_items)

                # Pick the best sample item (some scrapers return metadata rows first)
                find_key = test.get("find_sample_with")
                sample_item = None
                if find_key:
                    sample_item = next((i for i in valid_items if i.get(find_key)), None)
                if not sample_item and valid_items:
                    sample_item = valid_items[0]

                return {
                    "raw_count": len(raw_items),
                    "valid_count": len(valid_items),
                    "error_count": len(raw_items) - len(valid_items),
                    "normalized_data_count": len(normalized_data),
                    "normalized_social_count": len(normalized_social),
                    "raw_sample": sample_item,
                    "normalized_data_sample": normalized_data[0] if normalized_data else None,
                    "normalized_social_sample": normalized_social[0] if normalized_social else None,
                    "raw_keys": sorted(sample_item.keys()) if sample_item else [],
                    "elapsed_ms": elapsed,
                    "error": None,
                }

            if result["normalized_status"] == "failed":
                elapsed = int((time.time() - start) * 1000)
                return {
                    "error": result.get("error") or "Apify run failed",
                    "elapsed_ms": elapsed,
                }

        elapsed = int((time.time() - start) * 1000)
        return {"error": f"Timed out after {POLL_TIMEOUT}s", "elapsed_ms": elapsed}

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {"error": str(e), "elapsed_ms": elapsed}


def validate_result(test: dict, result: dict) -> list[str]:
    """Validate scraper results against expected fields and counts."""
    issues = []

    if result.get("error"):
        issues.append(f"Error: {result['error']}")
        return issues

    if result["valid_count"] < test["min_items"]:
        issues.append(f"Too few items: {result['valid_count']} (expected >= {test['min_items']})")

    if result["error_count"] > 0:
        issues.append(f"{result['error_count']} error items in raw output")

    # Check required fields present in raw output
    sample = result.get("raw_sample") or {}
    for field in test["required_fields"]:
        if field not in sample:
            issues.append(f"Missing required field '{field}' in raw output")

    # Check normalized output is non-empty
    if test["scraper"] != "instagram_comments":
        if result.get("normalized_social_count", 0) == 0 and result["valid_count"] > 0:
            issues.append("Social normalizer produced 0 results from valid items")

    if result.get("normalized_data_count", 0) == 0 and result["valid_count"] > 0:
        issues.append("Data normalizer produced 0 results from valid items")

    return issues


# =============================================================================
# Main
# =============================================================================


async def main():
    settings = get_settings()
    if not settings.apify_api_token:
        print("ERROR: APIFY_API_TOKEN not configured in .env")
        sys.exit(1)

    print("=" * 70)
    print("  APIFY SCRAPER BENCHMARK")
    print("=" * 70)
    print(f"  Testing {len(TESTS)} scrapers with known public URLs\n")

    all_pass = True

    for test in TESTS:
        name = test["name"]
        print(f"  {name}")
        print(f"    URL: {test['url']}")

        result = await run_scraper(test)
        issues = validate_result(test, result)

        if result.get("error"):
            print(f"    FAIL  {result['elapsed_ms']}ms  -- {result['error']}")
            all_pass = False
        elif issues:
            print(f"    WARN  {result['elapsed_ms']}ms  items={result['valid_count']}")
            for issue in issues:
                print(f"      ! {issue}")
        else:
            print(f"    PASS  {result['elapsed_ms']}ms  items={result['valid_count']}")
            if result.get("normalized_data_count"):
                print(f"      normalized (data): {result['normalized_data_count']}")
            if result.get("normalized_social_count"):
                print(f"      normalized (social): {result['normalized_social_count']}")

        # Show raw keys for debugging
        if result.get("raw_keys"):
            print(f"      raw keys: {result['raw_keys']}")

        print()

    print("=" * 70)
    if all_pass:
        print("  ALL SCRAPERS PASSED")
    else:
        print("  SOME SCRAPERS FAILED — check output above")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
