"""
Benchmark and audit the Smart Scout (pulse) pipeline.

Quick mode measures real wall-clock time as users experience it.
Audit mode runs all scope x source_mode permutations with flaw detection,
writes a markdown report to backend/smart-scout-results.md.

Usage:
    cd backend
    python scripts/benchmark_pulse.py              # Quick benchmark (3 scenarios)
    python scripts/benchmark_pulse.py --audit       # Full audit (12 searches + report)
"""
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

import re
try:
    from langdetect import detect as detect_language
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    print("WARNING: langdetect not installed — skipping language checks")

from app.services.pulse_orchestrator import PulseOrchestrator
from app.services.news_utils import AgentResponse, extract_content_year

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent


# =============================================================================
# Quick Benchmark Scenarios (existing)
# =============================================================================

SCENARIOS = [
    {
        "name": "Local DE: Schaffhausen",
        "news": {
            "location": "Schaffhausen, Switzerland",
            "city": "Schaffhausen",
            "country": "CH",
            "category": "news",
            "language": "de",
        },
        "gov": {
            "location": "Schaffhausen, Switzerland",
            "city": "Schaffhausen",
            "country": "CH",
            "category": "government",
            "language": "de",
        },
    },
    {
        "name": "Inv EN: Iran",
        "news": {
            "location": "Iran",
            "city": "",
            "country": "IR",
            "category": "news",
            "language": "en",
        },
        "gov": {
            "location": "Iran",
            "city": "",
            "country": "IR",
            "category": "government",
            "language": "en",
        },
    },
    {
        "name": "Topic DE: AI regulation",
        "news": {
            "criteria": "AI regulation",
            "category": "news",
            "language": "de",
        },
        "gov": {
            "criteria": "AI regulation",
            "category": "analysis",
            "language": "de",
        },
    },
]


# =============================================================================
# Audit Permutations — all scope x source_mode combinations
# =============================================================================

AUDIT_PERMUTATIONS = [
    # ── Small US towns: niche (digest, no criteria) ──
    {
        "name": "niche: Bozeman",
        "source_mode": "niche",
        "scope": "location",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Bozeman, Montana",
            "city": "Bozeman",
            "country": "US",
            "language": "en",
        },
    },
    {
        "name": "niche: Flagstaff",
        "source_mode": "niche",
        "scope": "location",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Flagstaff, Arizona",
            "city": "Flagstaff",
            "country": "US",
            "language": "en",
        },
    },
    # ── Small US towns: reliable (digest, no criteria) ──
    {
        "name": "reliable: Bozeman",
        "source_mode": "reliable",
        "scope": "location",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Bozeman, Montana",
            "city": "Bozeman",
            "country": "US",
            "language": "en",
        },
    },
    {
        "name": "reliable: Flagstaff",
        "source_mode": "reliable",
        "scope": "location",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Flagstaff, Arizona",
            "city": "Flagstaff",
            "country": "US",
            "language": "en",
        },
    },
    # ── Small US towns: reliable + criteria ──
    {
        "name": "reliable+criteria: Bozeman+housing",
        "source_mode": "reliable",
        "scope": "location+topic",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Bozeman, Montana",
            "city": "Bozeman",
            "country": "US",
            "criteria": "housing development",
            "language": "en",
        },
    },
    {
        "name": "reliable+criteria: Flagstaff+water",
        "source_mode": "reliable",
        "scope": "location+topic",
        "categories": ["news", "government"],
        "search_kwargs": {
            "location": "Flagstaff, Arizona",
            "city": "Flagstaff",
            "country": "US",
            "criteria": "water supply drought",
            "language": "en",
        },
    },
    # ── Beat mode: niche ──
    {
        "name": "beat+niche: housing policy",
        "source_mode": "niche",
        "scope": "topic",
        "categories": ["news", "analysis"],
        "search_kwargs": {"criteria": "housing policy", "language": "en"},
    },
    {
        "name": "beat+niche: renewable energy",
        "source_mode": "niche",
        "scope": "topic",
        "categories": ["news", "analysis"],
        "search_kwargs": {"criteria": "renewable energy", "language": "en"},
    },
    # ── Beat mode: reliable ──
    {
        "name": "beat+reliable: housing policy",
        "source_mode": "reliable",
        "scope": "topic",
        "categories": ["news", "analysis"],
        "search_kwargs": {"criteria": "housing policy", "language": "en"},
    },
    {
        "name": "beat+reliable: renewable energy",
        "source_mode": "reliable",
        "scope": "topic",
        "categories": ["news", "analysis"],
        "search_kwargs": {"criteria": "renewable energy", "language": "en"},
    },
    # ── Priority sources: beat ──
    {
        "name": "priority: housing+propublica",
        "source_mode": "reliable",
        "scope": "topic+priority",
        "categories": ["news"],
        "search_kwargs": {
            "criteria": "housing policy",
            "language": "en",
            "priority_sources": ["propublica.org", "reuters.com"],
        },
    },
    {
        "name": "priority: energy+nytimes",
        "source_mode": "reliable",
        "scope": "topic+priority",
        "categories": ["news"],
        "search_kwargs": {
            "criteria": "renewable energy",
            "language": "en",
            "priority_sources": ["nytimes.com", "theguardian.com"],
        },
    },
    # ── Priority sources: location ──
    {
        "name": "priority: Bozeman+localnews",
        "source_mode": "reliable",
        "scope": "location+priority",
        "categories": ["news"],
        "search_kwargs": {
            "location": "Bozeman, Montana",
            "city": "Bozeman",
            "country": "US",
            "language": "en",
            "priority_sources": ["bozemandailychronicle.com", "montanafreepress.org"],
        },
    },
]


# =============================================================================
# Quality Validation Helpers
# =============================================================================


def validate_language(summary: str, expected_lang: str) -> dict:
    """Check that summary bullets are in the expected language."""
    result = {"check": "language", "status": "skip", "detail": "", "mismatches": []}

    if not HAS_LANGDETECT or not summary:
        result["detail"] = "langdetect unavailable" if not HAS_LANGDETECT else "no summary"
        return result

    # Split summary into bullet-like lines (>20 chars to skip headers/noise)
    bullets = [line.strip() for line in summary.split("\n") if len(line.strip()) > 20]
    if not bullets:
        result["detail"] = "no bullet lines found"
        return result

    mismatches = []
    for bullet in bullets:
        try:
            detected = detect_language(bullet)
            if detected != expected_lang:
                mismatches.append({"text": bullet[:80], "detected": detected, "expected": expected_lang})
        except Exception:
            pass  # langdetect can fail on short/ambiguous text

    result["mismatches"] = mismatches
    if mismatches:
        result["status"] = "FAIL"
        result["detail"] = f"{len(mismatches)}/{len(bullets)} bullets wrong language"
    else:
        result["status"] = "PASS"
        result["detail"] = f"{len(bullets)} bullets OK ({expected_lang})"

    return result


def validate_date_relevance(articles: list[dict]) -> dict:
    """Flag articles with stale year references in URL/title and detect PDFs."""
    current_year = datetime.now().year
    stale_articles = []
    pdfs = []

    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "")

        # Check for PDFs
        if ".pdf" in url.lower():
            pdfs.append({"title": title, "url": url})

        # Check for stale year references
        year = extract_content_year(url=url, title=title)
        if year is not None and year < current_year - 1:
            stale_articles.append({"title": title, "url": url, "year": year})

    status = "WARN" if stale_articles else "PASS"
    detail = f"{len(stale_articles)} stale, {len(pdfs)} PDFs"
    return {
        "check": "date_relevance",
        "status": status,
        "detail": detail,
        "stale_articles": stale_articles,
        "pdf_count": len(pdfs),
        "pdfs": pdfs,
    }


def validate_source_diversity(articles: list[dict], source_mode: str) -> dict:
    """Check that no single domain exceeds the per-mode cap."""
    from collections import Counter

    cap = 2 if source_mode == "niche" else 3
    domains = []
    for a in articles:
        url = a.get("url", "")
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if domain:
                domains.append(domain)
        except Exception:
            pass

    domain_counts = Counter(domains)
    violations = {d: c for d, c in domain_counts.items() if c > cap}
    unique = len(domain_counts)

    status = "WARN" if violations else "PASS"
    detail = f"{unique} domains" + (f", {len(violations)} over cap ({cap})" if violations else "")

    return {
        "check": "source_diversity",
        "status": status,
        "detail": detail,
        "unique_domains": unique,
        "violations": violations,
    }


def validate_undated_ratio(articles: list[dict], category: str) -> dict:
    """Flag high ratio of undated articles."""
    if not articles:
        return {
            "check": "undated_ratio",
            "status": "PASS",
            "detail": "no articles",
            "ratio": 0.0,
        }

    undated = sum(1 for a in articles if not a.get("date"))
    ratio = undated / len(articles)

    threshold = 0.7 if category == "government" else 0.5
    status = "WARN" if ratio > threshold else "PASS"
    detail = f"{undated}/{len(articles)} undated ({ratio:.0%})"

    return {
        "check": "undated_ratio",
        "status": status,
        "detail": detail,
        "ratio": round(ratio, 3),
    }


def validate_priority_sources(articles: list[dict], priority_sources: list[str]) -> dict:
    """Check whether articles from priority source domains appear in results."""
    from urllib.parse import urlparse

    if not priority_sources:
        return {"check": "priority_sources", "status": "skip", "detail": "no priority sources set"}

    priority_set = {d.lower() for d in priority_sources}
    hits = {}
    for a in articles:
        url = a.get("url", "")
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            continue
        for ps in priority_set:
            if domain.endswith(ps):
                hits.setdefault(ps, []).append(a.get("title", "?")[:60])

    found = list(hits.keys())
    missing = [d for d in priority_set if d not in hits]

    if not found:
        status = "FAIL"
        detail = f"0/{len(priority_set)} priority domains found in results"
    elif missing:
        status = "WARN"
        detail = f"{len(found)}/{len(priority_set)} priority domains found (missing: {', '.join(missing)})"
    else:
        status = "PASS"
        detail = f"{len(found)}/{len(priority_set)} priority domains found"

    return {
        "check": "priority_sources",
        "status": status,
        "detail": detail,
        "found_domains": found,
        "missing_domains": missing,
        "hits": {d: titles for d, titles in hits.items()},
    }


def run_quality_checks(
    record: dict, expected_lang: str, source_mode: str,
    priority_sources: list[str] | None = None,
) -> list[dict]:
    """Run all quality validation checks on a single audit record."""
    checks = []
    checks.append(validate_language(record.get("summary", ""), expected_lang))
    checks.append(validate_date_relevance(record.get("articles", [])))
    checks.append(validate_source_diversity(record.get("articles", []), source_mode))
    checks.append(validate_undated_ratio(record.get("articles", []), record.get("category", "")))
    if priority_sources:
        checks.append(validate_priority_sources(record.get("articles", []), priority_sources))
    return checks


# =============================================================================
# Quick Benchmark
# =============================================================================


async def run_single(orchestrator, label, kwargs):
    """Run a single category and return timing + stats."""
    start = time.time()
    try:
        r = await orchestrator.search_news(**kwargs)
        elapsed = time.time() - start
        return {
            "label": label,
            "elapsed_s": round(elapsed, 1),
            "articles": len(r.articles),
            "total": r.total_results,
            "searches": len(r.search_queries_used),
            "status": r.status,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "label": label,
            "elapsed_s": round(elapsed, 1),
            "error": str(e),
        }


async def run_benchmark():
    orchestrator = PulseOrchestrator()
    parallel_times = []

    print("=" * 60)
    print("PULSE PIPELINE BENCHMARK")
    print("(2 categories in parallel, matching frontend behavior)")
    print("=" * 60)

    for scenario in SCENARIOS:
        print(f"\n--- {scenario['name']} ---")

        start = time.time()
        news_result, gov_result = await asyncio.gather(
            run_single(orchestrator, "news", scenario["news"]),
            run_single(orchestrator, "gov/analysis", scenario["gov"]),
        )
        parallel_elapsed = round(time.time() - start, 1)
        parallel_times.append(parallel_elapsed)

        for r in [news_result, gov_result]:
            err = f" ERROR: {r['error']}" if "error" in r else ""
            articles = r.get("articles", 0)
            total = r.get("total", 0)
            searches = r.get("searches", 0)
            print(f"  {r['label']:>15}: {r['elapsed_s']:5.1f}s  |  {articles} selected / {total} found  |  {searches} queries{err}")

        print(f"  {'PARALLEL TOTAL':>15}: {parallel_elapsed:5.1f}s  (user-perceived)")

    print(f"\n{'=' * 60}")
    print("SUMMARY (user-perceived parallel times)")
    print(f"{'=' * 60}")
    mean = sum(parallel_times) / len(parallel_times)
    print(f"  Runs:  {len(parallel_times)}")
    print(f"  Mean:  {mean:.1f}s")
    print(f"  Min:   {min(parallel_times):.1f}s")
    print(f"  Max:   {max(parallel_times):.1f}s")
    print(f"\n  Recommended PULSE_EXPECTED_DURATION_MS = {int(max(parallel_times) * 1000)}")


# =============================================================================
# Audit Mode
# =============================================================================


async def run_audit_search(
    permutation_name: str,
    source_mode: str,
    scope: str,
    category: str,
    search_kwargs: dict,
) -> dict:
    """Run one pulse search and return structured audit data."""
    orch = PulseOrchestrator()
    record = {
        "permutation": permutation_name,
        "category": category,
        "source_mode": source_mode,
        "scope": scope,
        "queries_generated": 0,
        "queries_list": [],
        "raw_results": 0,
        "final_articles": 0,
        "articles": [],
        "summary": "",
        "processing_time_ms": 0,
        "error": None,
    }

    start = time.time()
    try:
        result: AgentResponse = await orch.search_news(
            category=category,
            source_mode=source_mode,
            **search_kwargs,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        record["queries_generated"] = len(result.search_queries_used)
        record["queries_list"] = result.search_queries_used
        record["raw_results"] = result.total_results
        record["final_articles"] = len(result.articles)
        record["articles"] = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "date": a.date,
            }
            for a in result.articles
        ]
        record["summary"] = result.summary[:300] if result.summary else ""
        record["processing_time_ms"] = result.processing_time_ms or elapsed_ms

    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
        record["processing_time_ms"] = int((time.time() - start) * 1000)
        traceback.print_exc()

    return record


def detect_flaws(records: list[dict]) -> list[str]:
    """Auto-detect issues from audit results.

    Heuristics:
    - Any error -> flaw
    - Zero articles returned -> flaw
    - Only 1 article -> warning
    - Category imbalance: one category returns results, another returns 0
    - 100% drop rate: raw > 0 but final == 0
    """
    flaws = []

    by_perm: dict[str, list[dict]] = {}
    for r in records:
        by_perm.setdefault(r["permutation"], []).append(r)

    for perm_name, cats in by_perm.items():
        for r in cats:
            if r["error"]:
                flaws.append(
                    f"**{perm_name} / {r['category']}**: Error -- {r['error']}"
                )
            elif r["final_articles"] == 0:
                flaws.append(
                    f"**{perm_name} / {r['category']}**: Zero articles "
                    f"(raw={r['raw_results']}, queries={r['queries_generated']})"
                )
            elif r["final_articles"] <= 1:
                flaws.append(
                    f"**{perm_name} / {r['category']}**: Only {r['final_articles']} article "
                    f"(raw={r['raw_results']}, queries={r['queries_generated']})"
                )

        # Category imbalance check
        if len(cats) > 1:
            article_counts = {r["category"]: r["final_articles"] for r in cats}
            with_results = [c for c, n in article_counts.items() if n > 0]
            without = [
                c for c, n in article_counts.items()
                if n == 0 and not any(r["error"] for r in cats if r["category"] == c)
            ]
            if with_results and without:
                flaws.append(
                    f"**{perm_name}**: Imbalanced -- "
                    f"{', '.join(with_results)} returned results but "
                    f"{', '.join(without)} returned nothing"
                )

    # 100% drop rate
    for r in records:
        if r["raw_results"] > 0 and r["final_articles"] == 0 and not r["error"]:
            flaws.append(
                f"**{r['permutation']} / {r['category']}**: 100% drop -- "
                f"{r['raw_results']} raw results all filtered out"
            )

    # Quality check failures
    for r in records:
        for check in r.get("quality_checks", []):
            if check["status"] == "FAIL":
                flaws.append(
                    f"**{r['permutation']} / {r['category']}**: Quality FAIL — "
                    f"{check['check']}: {check.get('detail', '')}"
                )

    # Cross-category URL overlap (same article in both categories)
    for perm_name, cats in by_perm.items():
        if len(cats) < 2:
            continue
        url_sets = {}
        for r in cats:
            urls = {a.get("url", "") for a in r.get("articles", []) if a.get("url")}
            url_sets[r["category"]] = urls
        cat_names = list(url_sets.keys())
        for i in range(len(cat_names)):
            for j in range(i + 1, len(cat_names)):
                overlap = url_sets[cat_names[i]] & url_sets[cat_names[j]]
                if overlap:
                    flaws.append(
                        f"**{perm_name}**: URL overlap between {cat_names[i]} and {cat_names[j]} — "
                        f"{len(overlap)} shared URLs"
                    )

    return flaws


def write_report(records: list[dict], flaws: list[str], output_path: Path):
    """Write structured markdown audit report."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []

    lines.append("# Smart Scout (Pulse) Audit Results")
    lines.append(f"Generated: {now}\n")
    total_perms = len(AUDIT_PERMUTATIONS)
    lines.append(f"**Searches:** {len(records)} ({total_perms} permutations x 2 categories)\n")

    # Summary Matrix
    lines.append("## Summary Matrix\n")
    lines.append("| Permutation | Category | Source Mode | Scope | Queries | Raw | Final | Time (ms) | Status |")
    lines.append("|-------------|----------|-------------|-------|---------|-----|-------|-----------|--------|")

    for r in records:
        if r["error"]:
            status = "ERROR"
        elif r["final_articles"] == 0:
            status = "FAIL"
        elif r["final_articles"] <= 1:
            status = f"WARN ({r['final_articles']})"
        else:
            status = "OK"

        lines.append(
            f"| {r['permutation']} | {r['category']} | {r['source_mode']} | {r['scope']} | "
            f"{r['queries_generated']} | {r['raw_results']} | {r['final_articles']} | "
            f"{r['processing_time_ms']} | {status} |"
        )

    # Detailed Results
    lines.append("\n## Detailed Results\n")

    for r in records:
        lines.append(f"### {r['permutation']} / {r['category']}\n")
        lines.append(f"- **Source mode:** {r['source_mode']}")
        lines.append(f"- **Scope:** {r['scope']}")
        lines.append(f"- **Queries:** {r['queries_generated']}")
        lines.append(f"- **Raw results:** {r['raw_results']}")
        lines.append(f"- **Final articles:** {r['final_articles']}")
        lines.append(f"- **Time:** {r['processing_time_ms']}ms")

        if r["error"]:
            lines.append(f"- **Error:** `{r['error']}`")

        if r["queries_list"]:
            lines.append(f"\n**Queries ({len(r['queries_list'])}):**")
            for q in r["queries_list"]:
                lines.append(f"- `{q}`")

        if r["articles"]:
            lines.append(f"\n**Articles ({len(r['articles'])}):**")
            for i, a in enumerate(r["articles"], 1):
                lines.append(f"{i}. **{a['title']}**")
                lines.append(f"   - Source: {a['source']} | Published: {a['date'] or 'undated'}")
                lines.append(f"   - URL: {a['url']}")

        if r["summary"]:
            lines.append(f"\n**Summary:** {r['summary']}")

        lines.append("")

    # Quality Validation
    lines.append("\n## Quality Validation\n")
    lines.append("| Permutation | Category | Language | Date Relevance | Source Diversity | Undated Ratio | Priority Sources |")
    lines.append("|-------------|----------|----------|----------------|-----------------|---------------|-----------------|")
    for r in records:
        checks = {c["check"]: c for c in r.get("quality_checks", [])}
        lang = checks.get("language", {})
        date = checks.get("date_relevance", {})
        src = checks.get("source_diversity", {})
        und = checks.get("undated_ratio", {})
        pri = checks.get("priority_sources", {})
        lines.append(
            f"| {r['permutation']} | {r['category']} | "
            f"{lang.get('status', 'skip')} | "
            f"{date.get('status', 'skip')} ({date.get('pdf_count', 0)} PDFs) | "
            f"{src.get('detail', 'skip')} | "
            f"{und.get('detail', 'skip')} | "
            f"{pri.get('status', 'skip')} {pri.get('detail', '')} |"
        )

    # Cross-Category Overlap
    lines.append("\n## Cross-Category Overlap\n")
    lines.append("Checks whether the same URLs appear in both categories for a permutation.")
    lines.append("Note: In production, `cross_category_dedup()` runs at the router level after both categories complete.\n")

    by_perm_report: dict[str, list[dict]] = {}
    for r in records:
        by_perm_report.setdefault(r["permutation"], []).append(r)

    has_overlap = False
    for perm_name, cats in by_perm_report.items():
        if len(cats) < 2:
            continue
        url_sets = {}
        for r in cats:
            urls = {a.get("url", "") for a in r.get("articles", []) if a.get("url")}
            url_sets[r["category"]] = urls
        cat_names = list(url_sets.keys())
        for i in range(len(cat_names)):
            for j in range(i + 1, len(cat_names)):
                overlap = url_sets[cat_names[i]] & url_sets[cat_names[j]]
                if overlap:
                    has_overlap = True
                    lines.append(f"**{perm_name}** — {cat_names[i]} ∩ {cat_names[j]}: {len(overlap)} shared URLs")
                    for url in sorted(overlap):
                        lines.append(f"- {url}")
                    lines.append("")

    if not has_overlap:
        lines.append("No URL overlap detected between categories.\n")

    # Flaws
    lines.append("---")
    lines.append("## Identified Flaws\n")
    if flaws:
        for f in flaws:
            lines.append(f"- {f}")
    else:
        lines.append("No flaws detected.")

    # Test Inputs (dynamic from permutations)
    lines.append("\n## Test Inputs\n")
    lines.append("| Name | Scope | Source Mode | Location | Topic | Criteria | Priority Sources | User Lang |")
    lines.append("|------|-------|-------------|----------|-------|----------|-----------------|-----------|")
    for p in AUDIT_PERMUTATIONS:
        sk = p["search_kwargs"]
        ps = ", ".join(sk.get("priority_sources", [])) or "--"
        lines.append(
            f"| {p['name']} | {p['scope']} | {p['source_mode']} | "
            f"{sk.get('location', '--')} | {sk.get('topic', '--')} | "
            f"{sk.get('criteria', '--')} | {ps} | {sk.get('language', 'en')} |"
        )

    # Raw JSON
    lines.append("\n## Raw Data (JSON)\n")
    lines.append("```json")
    lines.append(json.dumps(records, indent=2, default=str))
    lines.append("```\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {output_path}")


async def run_audit():
    """Run all permutations sequentially with flaw detection."""
    total = sum(len(p["categories"]) for p in AUDIT_PERMUTATIONS)
    idx = 0
    all_records = []

    print("=" * 70)
    print(f"  PULSE PIPELINE AUDIT -- {total} searches")
    print("=" * 70)

    for perm in AUDIT_PERMUTATIONS:
        for cat in perm["categories"]:
            idx += 1
            label = f"{perm['name']} / {cat}"
            print(f"\n[{idx}/{total}] {label} ...")

            record = await run_audit_search(
                permutation_name=perm["name"],
                source_mode=perm["source_mode"],
                scope=perm["scope"],
                category=cat,
                search_kwargs=perm["search_kwargs"],
            )
            all_records.append(record)

            if record["error"]:
                print(f"       ERROR: {record['error']}")
            else:
                print(
                    f"       queries={record['queries_generated']}  "
                    f"raw={record['raw_results']}  "
                    f"final={record['final_articles']}  "
                    f"time={record['processing_time_ms']}ms"
                )

            expected_lang = perm["search_kwargs"].get("language", "en")
            ps = perm["search_kwargs"].get("priority_sources")
            checks = run_quality_checks(record, expected_lang, perm["source_mode"], priority_sources=ps)
            record["quality_checks"] = checks
            failed = [c for c in checks if c["status"] == "FAIL"]
            warned = [c for c in checks if c["status"] == "WARN"]
            if failed:
                print(f"       QUALITY FAIL: {', '.join(c['check'] for c in failed)}")
            if warned:
                print(f"       QUALITY WARN: {', '.join(c['check'] for c in warned)}")

    flaws = detect_flaws(all_records)
    output_path = BACKEND_DIR / "smart-scout-results.md"
    write_report(all_records, flaws, output_path)

    # Quick summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for r in all_records:
        status = "ERROR" if r["error"] else ("FAIL" if r["final_articles"] == 0 else "OK")
        print(f"  {r['permutation']:30s} / {r['category']:12s} -> {r['final_articles']:2d} articles  [{status}]")

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
