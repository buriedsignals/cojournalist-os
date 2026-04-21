"""
Benchmark and audit the Civic Scout pipeline end-to-end.

URL mode measures real wall-clock time for a single council URL, breaking
down discovery, PDF download, parse, and promise extraction steps.
Audit mode runs all test permutations with flaw detection and writes a
markdown report to backend/civic-scout-results.md.

Usage:
    cd backend
    python scripts/benchmark_civic.py                        # URL mode (default URL)
    python scripts/benchmark_civic.py --url https://...      # URL mode (custom URL)
    python scripts/benchmark_civic.py --audit                # Full audit (all scenarios + report)
"""
import argparse
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

from app.services.civic_orchestrator import CivicOrchestrator
from app.schemas.civic import CandidateUrl, Promise

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

DEFAULT_URLS = [
    ("Basel (DE)", "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1"),
    ("Bozeman (EN)", "https://www.bozeman.net/departments/city-commission"),
    ("Madison WI (EN)", "https://www.cityofmadison.com/council"),
    ("Zermatt (DE)", "https://gemeinde.zermatt.ch"),
]


# =============================================================================
# Audit Scenarios
# =============================================================================

AUDIT_SCENARIOS = [
    {
        "name": "Basel: Grosser Rat (DE)",
        "url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
        "language": "de",
        "criteria": None,
    },
    {
        "name": "Basel: Grosser Rat + criteria (DE)",
        "url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
        "language": "de",
        "criteria": "Wohnungspolitik",
    },
    {
        "name": "Zurich: Gemeinderat (DE)",
        "url": "https://www.gemeinderat-zuerich.ch/protokolle",
        "language": "de",
        "criteria": None,
    },
    {
        "name": "Lausanne: Conseil communal (FR)",
        "url": "https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html",
        "language": "fr",
        "criteria": None,
    },
    {
        "name": "Bern: Stadtrat (DE)",
        "url": "https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen",
        "language": "de",
        "criteria": "Klimaschutz",
    },
    {
        "name": "Bozeman: City Commission (EN)",
        "url": "https://www.bozeman.net/departments/city-commission",
        "language": "en",
        "criteria": None,
    },
    {
        "name": "Bozeman: City Commission + criteria (EN)",
        "url": "https://www.bozeman.net/departments/city-commission",
        "language": "en",
        "criteria": "housing policy",
    },
    {
        "name": "Madison WI: Common Council (EN)",
        "url": "https://www.cityofmadison.com/council",
        "language": "en",
        "criteria": None,
    },
    {
        "name": "Zermatt: Gemeinde (DE)",
        "url": "https://gemeinde.zermatt.ch",
        "language": "de",
        "criteria": None,
    },
    {
        "name": "Zermatt: Gemeinde + criteria (DE)",
        "url": "https://gemeinde.zermatt.ch",
        "language": "de",
        "criteria": "Infrastruktur",
    },
]


# =============================================================================
# Quality Checks
# =============================================================================


def check_discovery(candidates: list[CandidateUrl]) -> dict:
    """Validate discovery output quality."""
    if not candidates:
        return {
            "check": "discovery",
            "status": "FAIL",
            "detail": "no candidates returned",
            "issues": [],
        }

    issues = []
    for c in candidates:
        if not c.url:
            issues.append("candidate missing URL")
        if not c.description:
            issues.append(f"candidate {c.url[:60]}: empty description")
        if c.confidence <= 0.0:
            issues.append(f"candidate {c.url[:60]}: zero confidence")

    high_conf = [c for c in candidates if c.confidence >= 0.7]
    if not high_conf:
        issues.append(f"no high-confidence (>=0.7) candidates among {len(candidates)}")

    status = "FAIL" if len(issues) >= len(candidates) else ("WARN" if issues else "PASS")
    detail = f"{len(candidates)} candidates, {len(high_conf)} high-confidence"
    return {
        "check": "discovery",
        "status": status,
        "detail": detail,
        "issues": issues[:10],
    }


def check_promises(promises: list[Promise]) -> dict:
    """Validate promise extraction quality."""
    if not promises:
        return {
            "check": "promises",
            "status": "WARN",
            "detail": "no promises extracted (may be expected for some documents)",
            "issues": [],
        }

    issues = []
    for p in promises:
        if not p.promise_text:
            issues.append("promise with empty promise_text")
        if not p.source_url:
            issues.append(f"promise missing source_url: {p.promise_text[:60]}")
        if p.date_confidence not in ("high", "medium", "low"):
            issues.append(f"invalid date_confidence: {p.date_confidence}")

    dated = [p for p in promises if p.due_date]
    status = "FAIL" if issues else "PASS"
    detail = f"{len(promises)} promises, {len(dated)} with due_date"
    return {
        "check": "promises",
        "status": status,
        "detail": detail,
        "issues": issues[:10],
    }


def check_url_coverage(candidates: list[CandidateUrl], root_url: str) -> dict:
    """Check that discovered URLs relate to the root domain."""
    if not candidates:
        return {"check": "url_coverage", "status": "SKIP", "detail": "no candidates"}

    from urllib.parse import urlparse

    root_domain = urlparse(root_url).netloc.lower()
    off_domain = [
        c for c in candidates
        if root_domain not in urlparse(c.url).netloc.lower()
    ]

    status = "WARN" if off_domain else "PASS"
    detail = (
        f"{len(candidates) - len(off_domain)}/{len(candidates)} on-domain"
        + (f", {len(off_domain)} off-domain" if off_domain else "")
    )
    return {
        "check": "url_coverage",
        "status": status,
        "detail": detail,
        "off_domain": [c.url for c in off_domain[:5]],
    }


def run_quality_checks(
    candidates: list[CandidateUrl],
    promises: list[Promise],
    root_url: str,
) -> list[dict]:
    """Run all quality checks on a single benchmark result."""
    checks = []
    checks.append(check_discovery(candidates))
    checks.append(check_url_coverage(candidates, root_url))
    checks.append(check_promises(promises))
    return checks


# =============================================================================
# Pipeline Steps (timed individually)
# =============================================================================


async def step_discover(orchestrator: CivicOrchestrator, url: str) -> dict:
    """Step 1: Crawl site and AI-classify candidate URLs."""
    start = time.time()
    try:
        candidates = await orchestrator.discover(url)
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "step": "discover",
            "elapsed_ms": elapsed_ms,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "firecrawl_credits": 1,  # 1 crawl job per discovery
            "error": None,
        }
    except Exception as e:
        return {
            "step": "discover",
            "elapsed_ms": int((time.time() - start) * 1000),
            "candidates": [],
            "candidate_count": 0,
            "firecrawl_credits": 0,
            "error": str(e),
        }


async def step_download_pdf(orchestrator: CivicOrchestrator, pdf_url: str) -> dict:
    """Step 2: Download a single PDF to a temp file."""
    start = time.time()
    try:
        local_path = await orchestrator._download_pdf(pdf_url)
        elapsed_ms = int((time.time() - start) * 1000)
        import os
        file_size_kb = round(os.path.getsize(local_path) / 1024, 1) if os.path.exists(local_path) else 0
        return {
            "step": "download_pdf",
            "elapsed_ms": elapsed_ms,
            "local_path": local_path,
            "file_size_kb": file_size_kb,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "download_pdf",
            "elapsed_ms": int((time.time() - start) * 1000),
            "local_path": None,
            "file_size_kb": 0,
            "error": str(e),
        }


async def step_parse_pdf(
    orchestrator: CivicOrchestrator, local_path: str, language: str = "de"
) -> dict:
    """Step 3: Parse PDF with LlamaParse and return extracted text."""
    start = time.time()
    try:
        text = await orchestrator._parse_pdf(local_path, language=language)
        elapsed_ms = int((time.time() - start) * 1000)
        # Estimate pages from text length (rough: ~2000 chars per page)
        estimated_pages = max(1, len(text) // 2000)
        return {
            "step": "parse_pdf",
            "elapsed_ms": elapsed_ms,
            "text": text,
            "text_length": len(text),
            "text_preview": text[:300] if text else "",
            "llamaparse_pages": estimated_pages,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "parse_pdf",
            "elapsed_ms": int((time.time() - start) * 1000),
            "text": "",
            "text_length": 0,
            "text_preview": "",
            "llamaparse_pages": 0,
            "error": str(e),
        }


async def step_download_and_parse(
    orchestrator: CivicOrchestrator, doc_url: str, language: str = "de"
) -> dict:
    """Step 3 (format-aware): Download+parse PDF or scrape+parse HTML.

    Detects document type via _detect_document_type and routes accordingly:
    - PDF: download to temp file, then LlamaParse
    - HTML: Firecrawl scrape → markdown (no LlamaParse)
    """
    start = time.time()
    doc_type = CivicOrchestrator._detect_document_type(doc_url)
    logging.info("step_download_and_parse: detected format=%s for %s", doc_type, doc_url)
    try:
        # Civic pipeline routes both PDF and HTML through Firecrawl's /v2/scrape
        # with parsers:[{type:'pdf',mode:'fast'}]. The legacy _download_pdf +
        # _parse_pdf (LlamaParse) path was removed when we consolidated.
        text = await orchestrator._parse_html(doc_url)
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "step": "download_and_parse",
            "doc_type": doc_type,
            "elapsed_ms": elapsed_ms,
            "text": text,
            "text_length": len(text),
            "text_preview": text[:300] if text else "",
            "file_size_kb": 0,
            "llamaparse_pages": 0,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "download_and_parse",
            "doc_type": doc_type,
            "elapsed_ms": int((time.time() - start) * 1000),
            "text": "",
            "text_length": 0,
            "text_preview": "",
            "file_size_kb": 0,
            "llamaparse_pages": 0,
            "error": str(e),
        }


async def step_extract_promises(
    orchestrator: CivicOrchestrator,
    text: str,
    source_url: str,
    source_date: str,
    criteria,
) -> dict:
    """Step 4: Extract political promises from parsed text via LLM."""
    start = time.time()
    try:
        promises = await orchestrator._extract_promises(
            text, source_url, source_date, criteria
        )
        elapsed_ms = int((time.time() - start) * 1000)
        # Estimate Gemini tokens: prompt ~500 + text (truncated to 15000 chars) / 4
        prompt_tokens = 500 + min(len(text), 15000) // 4
        output_tokens = sum(len(p.promise_text) + len(p.context) for p in promises) // 4
        return {
            "step": "extract_promises",
            "elapsed_ms": elapsed_ms,
            "promises": promises,
            "promise_count": len(promises),
            "gemini_tokens_in": prompt_tokens,
            "gemini_tokens_out": output_tokens,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "extract_promises",
            "elapsed_ms": int((time.time() - start) * 1000),
            "promises": [],
            "promise_count": 0,
            "gemini_tokens_in": 0,
            "gemini_tokens_out": 0,
            "error": str(e),
        }


# =============================================================================
# URL Mode (Single URL Benchmark) — Full Pipeline
# =============================================================================


async def step_fetch_and_detect(orchestrator: CivicOrchestrator, tracked_url: str) -> dict:
    """Step 2: Fetch tracked page, hash HTML, extract links, classify meeting URLs.

    Calls _fetch_and_extract_links (fast, no LLM) then _classify_meeting_urls
    (keywords first, LLM fallback). Logs three-number progression:
    raw_links -> pre_filtered -> classified.
    """
    start = time.time()
    try:
        content_hash, raw_links = await orchestrator._fetch_and_extract_links([tracked_url])
        raw_count = len(raw_links)

        meeting_urls = await orchestrator._classify_meeting_urls(raw_links)
        classified_count = len(meeting_urls)

        elapsed_ms = int((time.time() - start) * 1000)

        logging.info(
            "step_fetch_and_detect: raw_links=%d -> classified=%d",
            raw_count, classified_count,
        )

        return {
            "step": "fetch_and_detect",
            "elapsed_ms": elapsed_ms,
            "content_hash": content_hash,
            "pdf_urls": meeting_urls,
            "pdf_count": classified_count,
            "raw_link_count": raw_count,
            "error": None,
        }
    except Exception as e:
        return {
            "step": "fetch_and_detect",
            "elapsed_ms": int((time.time() - start) * 1000),
            "content_hash": "",
            "pdf_urls": [],
            "pdf_count": 0,
            "raw_link_count": 0,
            "error": str(e),
        }


async def run_url_benchmark(url: str):
    """Run a detailed single-URL benchmark testing the full pipeline.

    Steps:
      1. Discovery — Firecrawl crawl + AI classify (find which pages to track)
      2. Fetch & Detect — fetch the tracked page HTML, hash as baseline, extract meeting doc links
      3. Download & Parse — format-aware: PDF→LlamaParse, HTML→Firecrawl markdown
      4. Extract — Gemini promise/claim extraction
    """
    orchestrator = CivicOrchestrator()

    print("=" * 70)
    print("  CIVIC SCOUT PIPELINE BENCHMARK (full pipeline)")
    print(f"  URL: {url}")
    print("=" * 70)

    total_start = time.time()
    firecrawl_credits = 0
    llamaparse_pages = 0
    gemini_tokens_in = 0
    gemini_tokens_out = 0

    # ── Step 1: Discovery ────────────────────────────────────────────────
    print("\n[1/4] Discovery (Firecrawl crawl + AI classify)...")
    d = await step_discover(orchestrator, url)
    firecrawl_credits += d.get("firecrawl_credits", 0)
    print(
        f"  {'discover':>16}: {d['elapsed_ms']:6d}ms  "
        f"candidates={d['candidate_count']}"
        + (f"  ERROR: {d['error']}" if d["error"] else "")
    )

    if d["error"] or not d["candidates"]:
        print("\nNo candidates found — pipeline cannot proceed.")
        print(f"\nTotal time: {int((time.time() - total_start) * 1000)}ms")
        return

    print(f"\n  Top candidates:")
    for c in d["candidates"][:5]:
        print(f"    [{c.confidence:.2f}] {c.url}")
        print(f"           {c.description[:80]}")

    # Use the top candidate as the tracked URL (simulates journalist selection)
    tracked_url = d["candidates"][0].url
    print(f"\n  Simulating journalist selection: tracking {tracked_url}")

    # ── Step 2: Fetch page + detect meeting docs ──────────────────────────
    print(f"\n[2/4] Fetching tracked page + detecting meeting URLs...")
    fetch = await step_fetch_and_detect(orchestrator, tracked_url)
    raw_count = fetch.get("raw_link_count", 0)
    print(
        f"  {'fetch_detect':>16}: {fetch['elapsed_ms']:6d}ms  "
        f"hash={fetch['content_hash'][:16]}...  "
        f"raw_links={raw_count} -> classified={fetch['pdf_count']}"
        + (f"  ERROR: {fetch['error']}" if fetch["error"] else "")
    )

    if fetch["error"] or not fetch["pdf_urls"]:
        print("\n  No meeting URLs detected on tracked page.")
        total_ms = int((time.time() - total_start) * 1000)
        print(f"\n  Total time: {total_ms}ms ({total_ms / 1000:.1f}s)")
        return

    # Show top classified links (latest first — _classify_meeting_urls sorts by date desc)
    print(f"\n  Latest meeting URLs (top 5 of {fetch['pdf_count']}):")
    for doc_url in fetch["pdf_urls"][:5]:
        date = orchestrator._extract_date_from_url(doc_url)
        doc_type = CivicOrchestrator._detect_document_type(doc_url)
        name = doc_url.split("/")[-1] or doc_url.split("/")[-2]
        print(f"    [{date or '??'}] [{doc_type.upper()}] {name}")

    # Take the latest doc (first in list — sorted by date desc)
    target_doc = fetch["pdf_urls"][0]
    target_type = CivicOrchestrator._detect_document_type(target_doc)
    print(f"\n  Selected latest document ({target_type.upper()}): {target_doc}")

    # ── Step 3: Download + Parse (format-aware) ───────────────────────────
    if target_type == "pdf":
        print(f"\n[3/4] Downloading + parsing PDF (LlamaParse — may take several minutes)...")
    else:
        print(f"\n[3/4] Scraping HTML page via Firecrawl (markdown)...")
    parse = await step_download_and_parse(orchestrator, target_doc, language="de")
    llamaparse_pages += parse.get("llamaparse_pages", 0)
    size_info = f"size={parse['file_size_kb']}KB  " if parse["file_size_kb"] else ""
    print(
        f"  {'download_parse':>16}: {parse['elapsed_ms']:6d}ms  "
        f"format={parse['doc_type'].upper()}  "
        f"{size_info}"
        f"chars={parse['text_length']}"
        + (f"  ~pages={parse['llamaparse_pages']}" if parse["llamaparse_pages"] else "")
        + (f"  ERROR: {parse['error']}" if parse["error"] else "")
    )

    if parse["text_preview"]:
        print(f"\n  Text preview:")
        print(f"    {parse['text_preview'][:200]}")

    if parse["error"] or not parse["text_length"]:
        print("\n  Parse failed — cannot proceed.")
        total_ms = int((time.time() - total_start) * 1000)
        print(f"\n  Total time: {total_ms}ms ({total_ms / 1000:.1f}s)")
        return

    # ── Step 4: Extract Promises ─────────────────────────────────────────
    print(f"\n[4/4] Extracting promises (Gemini)...")
    source_date = orchestrator._extract_date_from_url(target_doc)
    ex = await step_extract_promises(
        orchestrator, parse["text"], target_doc, source_date, criteria=None
    )
    gemini_tokens_in += ex.get("gemini_tokens_in", 0)
    gemini_tokens_out += ex.get("gemini_tokens_out", 0)
    print(
        f"  {'extract':>16}: {ex['elapsed_ms']:6d}ms  "
        f"promises={ex['promise_count']}  "
        f"tokens_in={ex['gemini_tokens_in']}  "
        f"tokens_out={ex['gemini_tokens_out']}"
        + (f"  ERROR: {ex['error']}" if ex["error"] else "")
    )

    if ex["promises"]:
        print(f"\n  Promises found:")
        for i, p in enumerate(ex["promises"][:5], 1):
            print(f"    {i}. {p.promise_text[:120]}")
            if p.due_date:
                print(f"       Due: {p.due_date} (confidence: {p.date_confidence})")
            else:
                print(f"       No date (confidence: {p.date_confidence})")

    # ── Summary ──────────────────────────────────────────────────────────
    total_ms = int((time.time() - total_start) * 1000)
    step_ms = {
        "discover": d["elapsed_ms"],
        "fetch_detect": fetch["elapsed_ms"],
        "download_parse": parse["elapsed_ms"],
        "extract": ex["elapsed_ms"],
    }

    print(f"\n{'=' * 70}")
    print("  TIMING BREAKDOWN")
    print(f"{'=' * 70}")
    for step_name, ms in step_ms.items():
        pct = ms / total_ms * 100 if total_ms > 0 else 0
        print(f"  {step_name:>16}: {ms:6d}ms  ({pct:4.1f}%)")
    print(f"  {'TOTAL':>16}: {total_ms:6d}ms")

    print(f"\n{'=' * 70}")
    print("  COST ESTIMATE")
    print(f"{'=' * 70}")
    print(f"  Firecrawl credits:   {firecrawl_credits} (crawl job)")
    print(f"  LlamaParse pages:    ~{llamaparse_pages}")
    print(f"  Gemini tokens in:    {gemini_tokens_in:,}")
    print(f"  Gemini tokens out:   {gemini_tokens_out:,}")

    # Quality checks
    quality = run_quality_checks(d["candidates"], ex["promises"], url)
    print(f"\n{'=' * 70}")
    print("  QUALITY CHECKS")
    print(f"{'=' * 70}")
    for check in quality:
        status_icon = {"PASS": "OK ", "WARN": "WARN", "FAIL": "FAIL", "SKIP": "SKIP"}.get(
            check["status"], check["status"]
        )
        print(f"  [{status_icon}] {check['check']:20s} {check['detail']}")
        for issue in check.get("issues", [])[:3]:
            print(f"         - {issue}")

    last_name = target_doc.split("/")[-1] or target_doc.split("/")[-2]
    print(f"\n{'=' * 70}")
    print(f"  Baseline hash: {fetch['content_hash']}")
    print(f"  Meeting docs on page: {fetch['pdf_count']}")
    print(f"  Latest doc processed: {last_name} [{target_type.upper()}]")
    print(f"{'=' * 70}")


# =============================================================================
# Audit Mode
# =============================================================================


async def run_audit_scenario(scenario: dict) -> dict:
    """Run one full audit scenario and return structured results."""
    name = scenario["name"]
    url = scenario["url"]
    language = scenario.get("language", "de")
    criteria = scenario.get("criteria")

    record = {
        "scenario": name,
        "url": url,
        "language": language,
        "criteria": criteria,
        "steps": [],
        "candidate_count": 0,
        "candidates": [],
        "pdf_url": None,
        "pdf_size_kb": 0,
        "text_length": 0,
        "llamaparse_pages": 0,
        "promise_count": 0,
        "promises": [],
        "total_time_ms": 0,
        "firecrawl_credits": 0,
        "gemini_tokens_in": 0,
        "gemini_tokens_out": 0,
        "error": None,
        "quality_checks": [],
    }

    orchestrator = CivicOrchestrator()
    total_start = time.time()

    try:
        # Step 1: Discovery
        d = await step_discover(orchestrator, url)
        record["steps"].append({k: v for k, v in d.items() if k != "candidates"})
        record["candidate_count"] = d["candidate_count"]
        record["candidates"] = [
            {"url": c.url, "description": c.description, "confidence": c.confidence}
            for c in d["candidates"]
        ]
        record["firecrawl_credits"] += d.get("firecrawl_credits", 0)

        if d["error"]:
            record["error"] = d["error"]
            record["total_time_ms"] = int((time.time() - total_start) * 1000)
            return record

        # Step 2: Download/parse first document candidate (format-aware)
        if not d["candidates"]:
            record["total_time_ms"] = int((time.time() - total_start) * 1000)
            record["quality_checks"] = run_quality_checks(d["candidates"], [], url)
            return record

        target = d["candidates"][0]
        record["pdf_url"] = target.url
        doc_type = CivicOrchestrator._detect_document_type(target.url)
        logging.info("run_audit_scenario: detected format=%s for %s", doc_type, target.url)

        parse = await step_download_and_parse(orchestrator, target.url, language=language)
        record["steps"].append({k: v for k, v in parse.items() if k != "text_preview"})
        record["pdf_size_kb"] = parse.get("file_size_kb", 0)
        record["text_length"] = parse["text_length"]
        record["llamaparse_pages"] = parse.get("llamaparse_pages", 0)

        if parse["error"] or not parse["text_length"]:
            record["error"] = parse.get("error") or "Empty text after parse"
            record["total_time_ms"] = int((time.time() - total_start) * 1000)
            return record

        # Step 3: Extract promises
        source_date = orchestrator._extract_date_from_url(target.url)
        ex = await step_extract_promises(
            orchestrator, parse.get("text", ""), target.url, source_date, criteria
        )
        record["steps"].append({k: v for k, v in ex.items() if k != "promises"})
        record["promise_count"] = ex["promise_count"]
        record["promises"] = [
            {
                "promise_text": p.promise_text[:200],
                "due_date": p.due_date,
                "date_confidence": p.date_confidence,
                "criteria_match": p.criteria_match,
            }
            for p in ex["promises"]
        ]
        record["gemini_tokens_in"] += ex.get("gemini_tokens_in", 0)
        record["gemini_tokens_out"] += ex.get("gemini_tokens_out", 0)

        if ex["error"]:
            record["error"] = ex["error"]

    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    record["total_time_ms"] = int((time.time() - total_start) * 1000)

    # Quality checks
    candidates = [
        CandidateUrl(**c) for c in record["candidates"]
    ]
    promise_defaults = {
        "context": "",
        "source_url": record.get("pdf_url") or "",
        "source_date": "",
        "date_confidence": "unknown",
        "criteria_match": False,
    }
    promises = [
        Promise(**{**promise_defaults, **p})
        for p in record["promises"]
    ]
    record["quality_checks"] = run_quality_checks(candidates, promises, url)

    return record


def detect_flaws(records: list[dict]) -> list[str]:
    """Auto-detect issues from audit results."""
    flaws = []

    for r in records:
        name = r["scenario"]

        if r["error"]:
            flaws.append(f"**{name}**: Error -- {r['error']}")
            continue

        if r["candidate_count"] == 0:
            flaws.append(f"**{name}**: Zero candidates discovered")
        elif r["candidate_count"] <= 1:
            flaws.append(f"**{name}**: Only {r['candidate_count']} candidate(s) found")

        if r["pdf_url"] and r["text_length"] == 0:
            flaws.append(f"**{name}**: PDF downloaded ({r['pdf_size_kb']}KB) but parse returned empty text")

        if r["pdf_url"] and r["promise_count"] == 0 and r["text_length"] > 0:
            flaws.append(
                f"**{name}**: {r['text_length']} chars parsed but 0 promises extracted"
            )

        # Quality check failures
        for check in r.get("quality_checks", []):
            if check["status"] == "FAIL":
                flaws.append(
                    f"**{name}**: Quality FAIL — {check['check']}: {check.get('detail', '')}"
                )

        # Step-level errors
        for step in r.get("steps", []):
            if step.get("error"):
                flaws.append(f"**{name}**: Step '{step['step']}' error -- {step['error']}")

    # Cross-scenario: same URL should yield consistent candidate counts
    by_url: dict[str, list[dict]] = {}
    for r in records:
        by_url.setdefault(r["url"], []).append(r)

    for url, runs in by_url.items():
        counts = [r["candidate_count"] for r in runs if not r["error"]]
        if len(counts) > 1 and max(counts) - min(counts) > 5:
            flaws.append(
                f"**{url}**: Inconsistent candidate counts across scenarios: {counts}"
            )

    return flaws


def write_report(records: list[dict], flaws: list[str], output_path: Path):
    """Write structured markdown audit report."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []

    lines.append("# Civic Scout Pipeline Audit Results")
    lines.append(f"Generated: {now}\n")
    lines.append(f"**Scenarios:** {len(records)}\n")

    # Summary Matrix
    lines.append("## Summary Matrix\n")
    lines.append(
        "| Scenario | URL | Candidates | PDF Size | Pages | Promises | "
        "Firecrawl | LlamaParse | Gemini In | Time (ms) | Status |"
    )
    lines.append(
        "|----------|-----|------------|----------|-------|----------|"
        "-----------|------------|-----------|-----------|--------|"
    )

    for r in records:
        if r["error"]:
            status = "ERROR"
        elif r["candidate_count"] == 0:
            status = "FAIL"
        else:
            status = "OK"

        lines.append(
            f"| {r['scenario']} | {r['url'][:50]}... | {r['candidate_count']} | "
            f"{r['pdf_size_kb']}KB | {r['llamaparse_pages']} | {r['promise_count']} | "
            f"{r['firecrawl_credits']} | {r['llamaparse_pages']}pg | "
            f"{r['gemini_tokens_in']:,} | {r['total_time_ms']} | {status} |"
        )

    # Step Timing Breakdown
    lines.append("\n## Step Timing Breakdown\n")
    lines.append("| Scenario | Discover | Download PDF | Parse PDF | Extract | Total |")
    lines.append("|----------|----------|--------------|-----------|---------|-------|")

    for r in records:
        step_times = {s["step"]: s["elapsed_ms"] for s in r["steps"]}
        discover_ms = step_times.get("discover", "--")
        download_ms = step_times.get("download_pdf", "--")
        parse_ms = step_times.get("parse_pdf", "--")
        extract_ms = step_times.get("extract_promises", "--")
        lines.append(
            f"| {r['scenario']} | {discover_ms}ms | {download_ms}ms | "
            f"{parse_ms}ms | {extract_ms}ms | {r['total_time_ms']}ms |"
        )

    # Cost Summary
    lines.append("\n## Cost Estimates\n")
    lines.append("| Scenario | Firecrawl Credits | LlamaParse Pages | Gemini Tokens In | Gemini Tokens Out |")
    lines.append("|----------|-------------------|-----------------|-----------------|------------------|")
    total_credits = 0
    total_pages = 0
    total_tokens_in = 0
    total_tokens_out = 0
    for r in records:
        lines.append(
            f"| {r['scenario']} | {r['firecrawl_credits']} | {r['llamaparse_pages']} | "
            f"{r['gemini_tokens_in']:,} | {r['gemini_tokens_out']:,} |"
        )
        total_credits += r["firecrawl_credits"]
        total_pages += r["llamaparse_pages"]
        total_tokens_in += r["gemini_tokens_in"]
        total_tokens_out += r["gemini_tokens_out"]
    lines.append(
        f"| **TOTAL** | **{total_credits}** | **{total_pages}** | "
        f"**{total_tokens_in:,}** | **{total_tokens_out:,}** |"
    )

    # Quality Checks
    lines.append("\n## Quality Checks\n")
    lines.append("| Scenario | Discovery | URL Coverage | Promises |")
    lines.append("|----------|-----------|--------------|----------|")

    for r in records:
        checks = {c["check"]: c for c in r.get("quality_checks", [])}
        disc = checks.get("discovery", {})
        cov = checks.get("url_coverage", {})
        prom = checks.get("promises", {})
        lines.append(
            f"| {r['scenario']} | "
            f"{disc.get('status', '--')} ({disc.get('detail', '')}) | "
            f"{cov.get('status', '--')} ({cov.get('detail', '')}) | "
            f"{prom.get('status', '--')} ({prom.get('detail', '')}) |"
        )

    # Detailed Results
    lines.append("\n## Detailed Results\n")

    for r in records:
        lines.append(f"### {r['scenario']}\n")
        lines.append(f"- **URL:** {r['url']}")
        lines.append(f"- **Language:** {r['language']}")
        lines.append(f"- **Criteria:** {r['criteria'] or '--'}")
        lines.append(f"- **Candidates found:** {r['candidate_count']}")
        if r["pdf_url"]:
            lines.append(f"- **PDF processed:** {r['pdf_url']}")
            lines.append(f"- **PDF size:** {r['pdf_size_kb']}KB")
            lines.append(f"- **Parsed pages:** ~{r['llamaparse_pages']}")
            lines.append(f"- **Text length:** {r['text_length']} chars")
        lines.append(f"- **Promises extracted:** {r['promise_count']}")
        lines.append(f"- **Total time:** {r['total_time_ms']}ms")
        lines.append(f"- **Firecrawl credits:** {r['firecrawl_credits']}")
        lines.append(f"- **Gemini tokens:** in={r['gemini_tokens_in']:,}  out={r['gemini_tokens_out']:,}")

        if r["error"]:
            lines.append(f"- **Error:** `{r['error']}`")

        # Step timing
        if r["steps"]:
            lines.append("\n**Step timing:**")
            for step in r["steps"]:
                err = f" (ERROR: {step['error']})" if step.get("error") else ""
                lines.append(f"- `{step['step']}`: {step['elapsed_ms']}ms{err}")

        # Top candidates
        if r["candidates"]:
            lines.append(f"\n**Candidates (top 5):**")
            for c in r["candidates"][:5]:
                lines.append(f"- [{c['confidence']:.2f}] {c['url']}")
                lines.append(f"  {c['description'][:100]}")

        # Promises
        if r["promises"]:
            lines.append(f"\n**Promises ({len(r['promises'])}):**")
            for i, p in enumerate(r["promises"][:5], 1):
                lines.append(f"{i}. {p['promise_text'][:150]}")
                if p["due_date"]:
                    lines.append(f"   Due: {p['due_date']} (confidence: {p['date_confidence']})")
                if p.get("criteria_match") is False:
                    lines.append(f"   criteria_match: false")

        # Quality check issues
        failed_checks = [c for c in r.get("quality_checks", []) if c["status"] in ("FAIL", "WARN")]
        if failed_checks:
            lines.append("\n**Quality issues:**")
            for c in failed_checks:
                lines.append(f"- {c['check']} ({c['status']}): {c['detail']}")
                for issue in c.get("issues", [])[:5]:
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
    lines.append("| Scenario | URL | Language | Criteria |")
    lines.append("|----------|-----|----------|----------|")
    for s in AUDIT_SCENARIOS:
        lines.append(
            f"| {s['name']} | {s['url']} | {s.get('language', 'de')} | "
            f"{s.get('criteria') or '--'} |"
        )

    # Raw JSON
    lines.append("\n## Raw Data (JSON)\n")
    lines.append("```json")
    # Strip heavy fields from JSON output
    sanitized = []
    for r in records:
        r_copy = {k: v for k, v in r.items()}
        r_copy.pop("candidates", None)  # large list in detailed section already
        sanitized.append(r_copy)
    lines.append(json.dumps(sanitized, indent=2, default=str))
    lines.append("```\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {output_path}")


async def run_audit():
    """Run all audit scenarios with quality checks and flaw detection."""
    total = len(AUDIT_SCENARIOS)
    all_records = []

    print("=" * 70)
    print(f"  CIVIC SCOUT PIPELINE AUDIT -- {total} scenarios")
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
            print(
                f"       candidates={record['candidate_count']}  "
                f"promises={record['promise_count']}  "
                f"{step_summary}"
            )
            print(
                f"       cost: firecrawl={record['firecrawl_credits']}  "
                f"llamaparse={record['llamaparse_pages']}pg  "
                f"gemini_in={record['gemini_tokens_in']:,}tok"
            )

        # Quality check summary
        failed = [c for c in record.get("quality_checks", []) if c["status"] == "FAIL"]
        warned = [c for c in record.get("quality_checks", []) if c["status"] == "WARN"]
        if failed:
            print(f"       QUALITY FAIL: {', '.join(c['check'] for c in failed)}")
        if warned:
            print(f"       QUALITY WARN: {', '.join(c['check'] for c in warned)}")

    flaws = detect_flaws(all_records)
    output_path = BACKEND_DIR / "civic-scout-results.md"
    write_report(all_records, flaws, output_path)

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for r in all_records:
        status = "ERROR" if r["error"] else ("FAIL" if r["candidate_count"] == 0 else "OK")
        print(
            f"  {r['scenario']:40s} -> {r['candidate_count']:2d} candidates  "
            f"{r['promise_count']:2d} promises  {r['total_time_ms']:6d}ms  [{status}]"
        )

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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark the Civic Scout (civic) pipeline."
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Council URL to benchmark (default: run both Basel and Bozeman)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run full audit across all test scenarios",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.audit:
        asyncio.run(run_audit())
    elif args.url:
        asyncio.run(run_url_benchmark(args.url))
    else:
        # Run both default URLs
        async def _run_defaults():
            for name, url in DEFAULT_URLS:
                print(f"\n{'#' * 70}")
                print(f"  {name}")
                print(f"{'#' * 70}")
                await run_url_benchmark(url)

        asyncio.run(_run_defaults())
