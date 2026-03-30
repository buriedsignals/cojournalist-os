"""
Benchmark and audit the Social Scout pipeline end-to-end.

Tests profile validation, Apify scraping, post normalization, ID-based
diffing, AI summary generation, and criteria matching — all platforms
(Instagram, X, Facebook) and both monitor modes (summarize, criteria).

Usage:
    cd backend
    python scripts/benchmark_social.py              # Quick benchmark (2 profiles)
    python scripts/benchmark_social.py --audit       # Full audit (all scenarios + report)
"""
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.social_orchestrator import (
    validate_profile,
    scrape_profile,
    normalize_instagram_posts,
    normalize_x_posts,
    normalize_facebook_posts,
    identify_new_posts,
    identify_removed_posts,
    summarize_posts,
    match_criteria,
    build_profile_url,
)
from app.schemas.social import NormalizedPost, PostSnapshot

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent


# =============================================================================
# Test Scenarios
# =============================================================================

QUICK_SCENARIOS = [
    {
        "name": "Instagram: @buriedsignals",
        "platform": "instagram",
        "handle": "buriedsignals",
        "mode": "summarize",
        "language": "en",
    },
    {
        "name": "X: @buriedsignals",
        "platform": "x",
        "handle": "buriedsignals",
        "mode": "summarize",
        "language": "en",
    },
    {
        "name": "Facebook: @NASA",
        "platform": "facebook",
        "handle": "NASA",
        "mode": "summarize",
        "language": "en",
    },
]

AUDIT_SCENARIOS = [
    # Instagram profiles
    {
        "name": "ig-summarize: buriedsignals",
        "platform": "instagram",
        "handle": "buriedsignals",
        "mode": "summarize",
        "language": "en",
        "max_items": 20,
    },
    {
        "name": "ig-criteria: buriedsignals",
        "platform": "instagram",
        "handle": "buriedsignals",
        "mode": "criteria",
        "criteria": "data visualization or investigative journalism",
        "language": "en",
        "max_items": 20,
    },
    # X/Twitter profiles
    {
        "name": "x-summarize: buriedsignals",
        "platform": "x",
        "handle": "buriedsignals",
        "mode": "summarize",
        "language": "en",
        "max_items": 20,
    },
    {
        "name": "x-criteria: buriedsignals",
        "platform": "x",
        "handle": "buriedsignals",
        "mode": "criteria",
        "criteria": "data visualization or investigative journalism",
        "language": "en",
        "max_items": 20,
    },
    # Facebook profiles
    {
        "name": "fb-summarize: NASA",
        "platform": "facebook",
        "handle": "NASA",
        "mode": "summarize",
        "language": "en",
        "max_items": 20,
    },
    {
        "name": "fb-criteria: NASA",
        "platform": "facebook",
        "handle": "NASA",
        "mode": "criteria",
        "criteria": "space exploration or rocket launch",
        "language": "en",
        "max_items": 20,
    },
]


# =============================================================================
# Quality Checks
# =============================================================================


def check_normalization(posts: list[NormalizedPost], platform: str) -> dict:
    """Validate post normalization quality."""
    if not posts:
        return {"check": "normalization", "status": "FAIL", "detail": "no posts", "issues": []}

    issues = []
    for p in posts:
        if not p.id:
            issues.append(f"empty ID")
        if not p.url:
            issues.append(f"post {p.id}: empty URL")
        if not p.timestamp:
            issues.append(f"post {p.id}: empty timestamp")
        if not p.author:
            issues.append(f"post {p.id}: empty author")
        if platform == "instagram" and not p.image_urls:
            issues.append(f"post {p.id}: no image_urls (expected for IG)")

    status = "FAIL" if issues else "PASS"
    detail = f"{len(posts)} posts, {len(issues)} issues"
    return {"check": "normalization", "status": status, "detail": detail, "issues": issues[:10]}


def check_engagement(posts: list[NormalizedPost]) -> dict:
    """Check that engagement data is populated."""
    if not posts:
        return {"check": "engagement", "status": "SKIP", "detail": "no posts"}

    with_engagement = sum(1 for p in posts if p.engagement and any(v for v in p.engagement.values()))
    ratio = with_engagement / len(posts)

    status = "PASS" if ratio >= 0.5 else "WARN"
    detail = f"{with_engagement}/{len(posts)} posts have engagement ({ratio:.0%})"
    return {"check": "engagement", "status": status, "detail": detail}


def check_id_uniqueness(posts: list[NormalizedPost]) -> dict:
    """Check for duplicate post IDs."""
    ids = [p.id for p in posts]
    unique = len(set(ids))
    dupes = len(ids) - unique

    status = "PASS" if dupes == 0 else "WARN"
    detail = f"{unique} unique / {len(ids)} total" + (f" ({dupes} duplicates)" if dupes else "")
    return {"check": "id_uniqueness", "status": status, "detail": detail}


def check_url_validity(posts: list[NormalizedPost], platform: str) -> dict:
    """Check that post URLs match the expected platform domain."""
    if not posts:
        return {"check": "url_validity", "status": "SKIP", "detail": "no posts"}

    domain_map = {"instagram": "instagram.com", "x": "x.com", "facebook": "facebook.com"}
    expected_domain = domain_map.get(platform, "")
    bad_urls = []
    for p in posts:
        if expected_domain not in p.url:
            bad_urls.append({"id": p.id, "url": p.url[:80]})

    status = "PASS" if not bad_urls else "WARN"
    detail = f"{len(posts) - len(bad_urls)}/{len(posts)} valid URLs"
    return {"check": "url_validity", "status": status, "detail": detail, "bad_urls": bad_urls[:5]}


def check_diffing(
    posts: list[NormalizedPost],
    previous_ids: set[str],
) -> dict:
    """Verify ID-based diffing logic."""
    new = identify_new_posts(posts, previous_ids)
    expected_new = len(posts) - len(previous_ids & {p.id for p in posts})

    status = "PASS" if len(new) == expected_new else "FAIL"
    detail = f"{len(new)} new / {len(posts)} total (baseline: {len(previous_ids)} IDs)"
    return {"check": "diffing", "status": status, "detail": detail}


def check_summary(summary: str) -> dict:
    """Basic summary quality check."""
    if not summary:
        return {"check": "summary", "status": "FAIL", "detail": "empty summary"}

    lines = [l.strip() for l in summary.split("\n") if l.strip()]
    has_bullets = any(l.startswith("-") or l.startswith("*") for l in lines)
    char_count = len(summary)

    issues = []
    if char_count < 50:
        issues.append("summary too short (<50 chars)")
    if not has_bullets:
        issues.append("no bullet points found")

    status = "PASS" if not issues else "WARN"
    detail = f"{char_count} chars, {len(lines)} lines" + (f" ({'; '.join(issues)})" if issues else "")
    return {"check": "summary", "status": status, "detail": detail}


def run_quality_checks(
    posts: list[NormalizedPost],
    platform: str,
    previous_ids: set[str],
    summary: str = "",
) -> list[dict]:
    """Run all quality checks on a benchmark result."""
    checks = []
    checks.append(check_normalization(posts, platform))
    checks.append(check_engagement(posts))
    checks.append(check_id_uniqueness(posts))
    checks.append(check_url_validity(posts, platform))
    checks.append(check_diffing(posts, previous_ids))
    if summary:
        checks.append(check_summary(summary))
    return checks


# =============================================================================
# Pipeline Steps (timed individually)
# =============================================================================


async def step_validate(platform: str, handle: str) -> dict:
    """Step 1: Profile validation via HTTP HEAD."""
    start = time.time()
    try:
        valid, profile_url = await validate_profile(platform, handle)
        elapsed = time.time() - start
        return {
            "step": "validate",
            "elapsed_ms": int(elapsed * 1000),
            "valid": valid,
            "profile_url": profile_url,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "validate",
            "elapsed_ms": int((time.time() - start) * 1000),
            "valid": False,
            "profile_url": "",
            "error": str(e),
        }


async def step_scrape(
    platform: str,
    handle: str,
    max_items: int = 20,
) -> dict:
    """Step 2: Scrape posts via Apify."""
    start = time.time()
    try:
        posts = await scrape_profile(platform=platform, handle=handle, max_items=max_items)
        elapsed = time.time() - start
        return {
            "step": "scrape",
            "elapsed_ms": int(elapsed * 1000),
            "post_count": len(posts),
            "posts": posts,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "scrape",
            "elapsed_ms": int((time.time() - start) * 1000),
            "post_count": 0,
            "posts": [],
            "error": str(e),
        }


async def step_summarize(
    posts: list[NormalizedPost],
    handle: str,
    language: str = "en",
) -> dict:
    """Step 3a: Generate AI summary (summarize mode)."""
    start = time.time()
    try:
        summary = await summarize_posts(posts, handle, language)
        elapsed = time.time() - start
        return {
            "step": "summarize",
            "elapsed_ms": int(elapsed * 1000),
            "summary": summary,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "summarize",
            "elapsed_ms": int((time.time() - start) * 1000),
            "summary": "",
            "error": str(e),
        }


async def step_criteria(
    posts: list[NormalizedPost],
    criteria: str,
    platform: str,
) -> dict:
    """Step 3b: Criteria matching (criteria mode)."""
    start = time.time()
    try:
        matched = await match_criteria(posts, criteria, platform)
        elapsed = time.time() - start
        return {
            "step": "criteria",
            "elapsed_ms": int(elapsed * 1000),
            "matched_count": len(matched),
            "matched_ids": [p.id for p in matched],
            "error": None,
        }
    except Exception as e:
        return {
            "step": "criteria",
            "elapsed_ms": int((time.time() - start) * 1000),
            "matched_count": 0,
            "matched_ids": [],
            "error": str(e),
        }


# =============================================================================
# Quick Benchmark
# =============================================================================


async def run_benchmark():
    """Run quick benchmark on a few profiles."""
    print("=" * 65)
    print("  SOCIAL SCOUT PIPELINE BENCHMARK")
    print("=" * 65)

    for scenario in QUICK_SCENARIOS:
        name = scenario["name"]
        platform = scenario["platform"]
        handle = scenario["handle"]
        language = scenario.get("language", "en")

        print(f"\n--- {name} ---")

        # Validate
        v = await step_validate(platform, handle)
        print(f"  {'validate':>12}: {v['elapsed_ms']:5d}ms  valid={v['valid']}")
        if not v["valid"]:
            print(f"  SKIPPED — profile invalid")
            continue

        # Scrape
        s = await step_scrape(platform, handle, max_items=20)
        print(f"  {'scrape':>12}: {s['elapsed_ms']:5d}ms  posts={s['post_count']}")
        if s["error"]:
            print(f"  ERROR: {s['error']}")
            continue

        # Diff (empty baseline = all new)
        new_posts = identify_new_posts(s["posts"], set())
        print(f"  {'diff':>12}:     0ms  new={len(new_posts)} (empty baseline)")

        # Summarize
        sm = await step_summarize(new_posts[:10], handle, language)
        print(f"  {'summarize':>12}: {sm['elapsed_ms']:5d}ms  chars={len(sm['summary'])}")

        total_ms = v["elapsed_ms"] + s["elapsed_ms"] + sm["elapsed_ms"]
        print(f"  {'TOTAL':>12}: {total_ms:5d}ms")

    print(f"\n{'=' * 65}")


# =============================================================================
# Audit Mode
# =============================================================================


async def run_audit_scenario(scenario: dict) -> dict:
    """Run one full audit scenario and return structured results."""
    name = scenario["name"]
    platform = scenario["platform"]
    handle = scenario["handle"]
    mode = scenario["mode"]
    criteria_text = scenario.get("criteria", "")
    language = scenario.get("language", "en")
    max_items = scenario.get("max_items", 20)

    record = {
        "scenario": name,
        "platform": platform,
        "handle": handle,
        "mode": mode,
        "criteria": criteria_text,
        "language": language,
        "steps": [],
        "post_count": 0,
        "new_count": 0,
        "summary": "",
        "matched_count": 0,
        "total_time_ms": 0,
        "error": None,
        "quality_checks": [],
        "posts_preview": [],
    }

    total_start = time.time()

    # Step 1: Validate
    v = await step_validate(platform, handle)
    record["steps"].append(v)
    if not v["valid"]:
        record["error"] = v.get("error") or "Profile invalid"
        record["total_time_ms"] = int((time.time() - total_start) * 1000)
        return record

    # Step 2: Scrape
    s = await step_scrape(platform, handle, max_items=max_items)
    record["steps"].append(s)
    posts = s["posts"]
    record["post_count"] = len(posts)
    if s["error"]:
        record["error"] = s["error"]
        record["total_time_ms"] = int((time.time() - total_start) * 1000)
        return record

    # Post preview (for report)
    for p in posts[:5]:
        record["posts_preview"].append({
            "id": p.id,
            "author": p.author,
            "text": (p.text or "")[:120],
            "timestamp": p.timestamp,
            "image_urls": len(p.image_urls),
            "engagement": p.engagement,
        })

    # Step 3: Diff (empty baseline = first run)
    new_posts = identify_new_posts(posts, set())
    record["new_count"] = len(new_posts)

    # Step 4: Mode-specific processing
    if mode == "summarize":
        sm = await step_summarize(new_posts[:10], handle, language)
        record["steps"].append(sm)
        record["summary"] = sm["summary"]
        if sm["error"]:
            record["error"] = sm["error"]
    elif mode == "criteria":
        cr = await step_criteria(new_posts, criteria_text, platform)
        record["steps"].append(cr)
        record["matched_count"] = cr["matched_count"]
        if cr["error"]:
            record["error"] = cr["error"]

    record["total_time_ms"] = int((time.time() - total_start) * 1000)

    # Quality checks
    record["quality_checks"] = run_quality_checks(
        posts=posts,
        platform=platform,
        previous_ids=set(),  # empty baseline
        summary=record["summary"],
    )

    return record


def detect_flaws(records: list[dict]) -> list[str]:
    """Auto-detect issues from audit results."""
    flaws = []

    for r in records:
        name = r["scenario"]
        if r["error"]:
            flaws.append(f"**{name}**: Error -- {r['error']}")
        elif r["post_count"] == 0:
            flaws.append(f"**{name}**: Zero posts scraped")

        # Summarize mode: check summary exists
        if r["mode"] == "summarize" and not r["error"]:
            if not r["summary"] or len(r["summary"]) < 20:
                flaws.append(f"**{name}**: Summary too short or empty ({len(r.get('summary', ''))} chars)")

        # Criteria mode: check reasonable match rate
        if r["mode"] == "criteria" and not r["error"]:
            if r["post_count"] > 0 and r["matched_count"] == 0:
                flaws.append(f"**{name}**: Zero criteria matches from {r['post_count']} posts")
            elif r["matched_count"] == r["post_count"] and r["post_count"] > 3:
                flaws.append(f"**{name}**: ALL posts matched criteria ({r['matched_count']}/{r['post_count']}) -- threshold may be too low")

        # Quality check failures
        for check in r.get("quality_checks", []):
            if check["status"] == "FAIL":
                flaws.append(f"**{name}**: Quality FAIL -- {check['check']}: {check.get('detail', '')}")

        # Step-level errors
        for step in r.get("steps", []):
            if step.get("error"):
                flaws.append(f"**{name}**: Step '{step['step']}' error -- {step['error']}")

    # Cross-platform consistency: same handle on different modes should get same post count
    by_handle: dict[str, list[dict]] = {}
    for r in records:
        key = f"{r['platform']}/@{r['handle']}"
        by_handle.setdefault(key, []).append(r)

    for key, runs in by_handle.items():
        counts = [r["post_count"] for r in runs if not r["error"]]
        if len(counts) > 1 and len(set(counts)) > 1:
            flaws.append(
                f"**{key}**: Inconsistent post counts across modes: {counts}"
            )

    return flaws


def write_report(records: list[dict], flaws: list[str], output_path: Path):
    """Write structured markdown audit report."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []

    lines.append("# Social Scout Pipeline Audit Results")
    lines.append(f"Generated: {now}\n")
    lines.append(f"**Scenarios:** {len(records)}\n")

    # Summary Matrix
    lines.append("## Summary Matrix\n")
    lines.append("| Scenario | Platform | Mode | Posts | New | Matched | Summary | Time (ms) | Status |")
    lines.append("|----------|----------|------|-------|-----|---------|---------|-----------|--------|")

    for r in records:
        if r["error"]:
            status = "ERROR"
        elif r["post_count"] == 0:
            status = "FAIL"
        else:
            status = "OK"

        summary_len = len(r.get("summary", ""))
        matched = r.get("matched_count", "--")
        if r["mode"] != "criteria":
            matched = "--"

        lines.append(
            f"| {r['scenario']} | {r['platform']} | {r['mode']} | "
            f"{r['post_count']} | {r['new_count']} | {matched} | "
            f"{summary_len} chars | {r['total_time_ms']} | {status} |"
        )

    # Step Timing Breakdown
    lines.append("\n## Step Timing Breakdown\n")
    lines.append("| Scenario | Validate | Scrape | Summarize/Criteria | Total |")
    lines.append("|----------|----------|--------|--------------------|-------|")

    for r in records:
        step_times = {s["step"]: s["elapsed_ms"] for s in r["steps"]}
        validate_ms = step_times.get("validate", "--")
        scrape_ms = step_times.get("scrape", "--")
        mode_ms = step_times.get("summarize") or step_times.get("criteria") or "--"
        lines.append(
            f"| {r['scenario']} | {validate_ms}ms | {scrape_ms}ms | {mode_ms}ms | {r['total_time_ms']}ms |"
        )

    # Quality Checks
    lines.append("\n## Quality Checks\n")
    lines.append("| Scenario | Normalization | Engagement | ID Unique | URL Valid | Diffing | Summary |")
    lines.append("|----------|---------------|------------|-----------|-----------|---------|---------|")

    for r in records:
        checks = {c["check"]: c for c in r.get("quality_checks", [])}
        row = [r["scenario"]]
        for check_name in ["normalization", "engagement", "id_uniqueness", "url_validity", "diffing", "summary"]:
            c = checks.get(check_name)
            if c:
                row.append(f"{c['status']}")
            else:
                row.append("--")
        lines.append("| " + " | ".join(row) + " |")

    # Detailed Results
    lines.append("\n## Detailed Results\n")

    for r in records:
        lines.append(f"### {r['scenario']}\n")
        lines.append(f"- **Platform:** {r['platform']}")
        lines.append(f"- **Handle:** @{r['handle']}")
        lines.append(f"- **Mode:** {r['mode']}")
        if r.get("criteria"):
            lines.append(f"- **Criteria:** {r['criteria']}")
        lines.append(f"- **Posts scraped:** {r['post_count']}")
        lines.append(f"- **New posts (vs empty baseline):** {r['new_count']}")
        if r["mode"] == "criteria":
            lines.append(f"- **Criteria matches:** {r['matched_count']}")
        lines.append(f"- **Total time:** {r['total_time_ms']}ms")

        if r["error"]:
            lines.append(f"- **Error:** `{r['error']}`")

        # Step timing
        lines.append("\n**Steps:**")
        for step in r["steps"]:
            err = f" (ERROR: {step['error']})" if step.get("error") else ""
            lines.append(f"- `{step['step']}`: {step['elapsed_ms']}ms{err}")

        # Post preview
        if r["posts_preview"]:
            lines.append(f"\n**Post preview ({len(r['posts_preview'])}):**")
            for i, p in enumerate(r["posts_preview"], 1):
                lines.append(f"{i}. **@{p['author']}** ({p['timestamp']})")
                lines.append(f"   {p['text']}")
                lines.append(f"   Images: {p['image_urls']} | Engagement: {p['engagement']}")

        # Summary
        if r["summary"]:
            lines.append(f"\n**AI Summary:**\n")
            lines.append(f"```\n{r['summary'][:500]}\n```")

        # Quality checks detail
        failed_checks = [c for c in r.get("quality_checks", []) if c["status"] in ("FAIL", "WARN")]
        if failed_checks:
            lines.append("\n**Quality issues:**")
            for c in failed_checks:
                lines.append(f"- {c['check']} ({c['status']}): {c['detail']}")
                if c.get("issues"):
                    for issue in c["issues"][:5]:
                        lines.append(f"  - {issue}")

        lines.append("")

    # Flaws
    lines.append("---")
    lines.append("## Identified Flaws\n")
    if flaws:
        for f in flaws:
            lines.append(f"- {f}")
    else:
        lines.append("No flaws detected.")

    # Test Inputs
    lines.append("\n## Test Inputs\n")
    lines.append("| Scenario | Platform | Handle | Mode | Criteria | Language |")
    lines.append("|----------|----------|--------|------|----------|----------|")
    for s in AUDIT_SCENARIOS:
        lines.append(
            f"| {s['name']} | {s['platform']} | @{s['handle']} | "
            f"{s['mode']} | {s.get('criteria', '--')} | {s.get('language', 'en')} |"
        )

    # Raw JSON
    lines.append("\n## Raw Data (JSON)\n")
    lines.append("```json")
    # Strip posts objects from JSON (too large)
    sanitized = []
    for r in records:
        r_copy = {k: v for k, v in r.items()}
        r_copy.pop("posts_preview", None)  # keep preview, remove raw
        sanitized.append(r_copy)
    lines.append(json.dumps(sanitized, indent=2, default=str))
    lines.append("```\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {output_path}")


async def run_audit():
    """Run all scenarios with quality checks and flaw detection."""
    total = len(AUDIT_SCENARIOS)
    all_records = []

    print("=" * 70)
    print(f"  SOCIAL SCOUT PIPELINE AUDIT -- {total} scenarios")
    print("=" * 70)

    for idx, scenario in enumerate(AUDIT_SCENARIOS, 1):
        name = scenario["name"]
        print(f"\n[{idx}/{total}] {name} ...")

        record = await run_audit_scenario(scenario)
        all_records.append(record)

        if record["error"]:
            print(f"       ERROR: {record['error']}")
        else:
            step_summary = "  ".join(
                f"{s['step']}={s['elapsed_ms']}ms" for s in record["steps"]
            )
            print(f"       posts={record['post_count']}  new={record['new_count']}  {step_summary}")
            if record["mode"] == "criteria":
                print(f"       matched={record['matched_count']}/{record['post_count']}")

        # Quality check summary
        failed = [c for c in record.get("quality_checks", []) if c["status"] == "FAIL"]
        warned = [c for c in record.get("quality_checks", []) if c["status"] == "WARN"]
        if failed:
            print(f"       QUALITY FAIL: {', '.join(c['check'] for c in failed)}")
        if warned:
            print(f"       QUALITY WARN: {', '.join(c['check'] for c in warned)}")

    flaws = detect_flaws(all_records)
    output_path = BACKEND_DIR / "social-scout-results.md"
    write_report(all_records, flaws, output_path)

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for r in all_records:
        status = "ERROR" if r["error"] else ("FAIL" if r["post_count"] == 0 else "OK")
        extra = ""
        if r["mode"] == "criteria" and not r["error"]:
            extra = f"  matched={r['matched_count']}"
        elif r["mode"] == "summarize" and not r["error"]:
            extra = f"  summary={len(r.get('summary', ''))}ch"
        print(f"  {r['scenario']:35s} -> {r['post_count']:2d} posts  {r['total_time_ms']:5d}ms  [{status}]{extra}")

    if flaws:
        print(f"\n  FLAWS ({len(flaws)}):")
        for f in flaws:
            print(f"    {f}")
    else:
        print("\n  No flaws detected.")

    print(f"\n  Full report: {output_path}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    if "--audit" in sys.argv:
        asyncio.run(run_audit())
    else:
        asyncio.run(run_benchmark())
