# Page Scout Service (type `web`)

> **Naming:** In the UI, this appears as "Page Scout". The backend type code is `web`.

Website monitoring with change detection and criteria matching.

## Overview

Page Scouts monitor specific URLs for content changes. Users choose between two modes:
- **Any Change**: Notifies on any content change (criteria is null, skips LLM analysis)
- **Specific Criteria**: Notifies only when changes match user-defined criteria (LLM-analyzed)

Uses Firecrawl's `changeTracking` format with per-scout baselines via the `tag` parameter.

## Provider Detection

Some websites fail Firecrawl's `changeTracking` format (ERR_TIMED_OUT) but work fine with plain scrape. The provider is detected once during the **test step** and persisted for all subsequent runs.

| Provider | Method | Change Detection | When Used |
|----------|--------|------------------|-----------|
| `firecrawl` | changeTracking format | Firecrawl baseline diff | Default — changeTracking works for this URL |
| `firecrawl_plain` | Plain markdown scrape | SHA-256 content hash | Fallback — changeTracking times out or fails |

**How it works (double-probe):**
1. Scout name must be provided before testing (required to build the real tag)
2. User clicks "Test" → backend runs `double_probe()` **concurrently** with the preview scrape
3. Double-probe sends **two** sequential changeTracking requests using the real `{user_id}#{scraper_name}` tag:
   - Call 1: Establishes a baseline (or times out)
   - Call 2: Checks `previousScrapeAt` — if it has a timestamp, Firecrawl stored the baseline; if `null`, the baseline was silently dropped
4. If baseline confirmed → provider = `firecrawl`; if dropped or timeout → `firecrawl_plain`
5. Provider is returned in the test response, passed through the scheduling modal, stored in the SCRAPER# record, and included in the EventBridge input template
6. On every scheduled run, `execute()` uses the persisted provider — skipping the doomed 60s changeTracking attempt for `firecrawl_plain` URLs

**Why double-probe:** Firecrawl can return `changeStatus: "new"` (HTTP 200) but silently drop the baseline. A single probe cannot distinguish "baseline stored" from "baseline dropped". The second call's `previousScrapeAt` field is the only definitive signal. See `page-scout-refactor.md` § Phase 3.

**Backwards compatibility:** Existing scouts without a `provider` field use the original runtime fallback behavior (try changeTracking, fall back to plain on failure).

## Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAGE SCOUT EXECUTION                          │
│                                                                 │
│  Trigger: EventBridge → Lambda → POST /api/scouts/execute       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Stage 1: Change Detection                                      │
│  ├─ If provider = "firecrawl_plain":                            │
│  │   ├─ Plain scrape (no changeTracking)                        │
│  │   └─ SHA-256 hash comparison for change detection            │
│  ├─ If provider = "firecrawl" (or unset):                       │
│  │   ├─ Scrape URL with changeTracking format                   │
│  │   ├─ Uses scout-specific `tag` for per-scout baseline        │
│  │   └─ Falls back to plain if changeTracking fails             │
│  └─ Returns: "new" | "changed" | "same"                         │
│           │                                                     │
│           │ If "same" → return early (no notification)          │
│           ▼                                                     │
│  Stage 2: Criteria Analysis                                     │
│  ├─ If criteria is null ("Any Change" mode):                    │
│  │   └─ Auto-match, summary = "Page content updated"            │
│  ├─ If criteria is set ("Specific Criteria" mode):              │
│  │   ├─ Analyze markdown content against criteria (GPT-4o-mini) │
│  │   └─ Returns: {matches: bool, summary: string}               │
│  │       │                                                      │
│  │       │ If !matches → return early (no notification)         │
│           ▼                                                     │
│  Stage 3: Deduplication (EXEC# records)                         │
│  ├─ Generate embedding for summary                              │
│  ├─ Compare against last 20 EXEC# records                       │
│  └─ Threshold: 0.85 cosine similarity                           │
│           │                                                     │
│           │ If duplicate → return early (no notification)       │
│           ▼                                                     │
│  Stage 4: Notification                                          │
│  ├─ Store EXEC# record                                          │
│  ├─ Extract atomic units (if location/topic set)                │
│  ├─ Send localized email (user's preferred_language)            │
│  └─ Decrement credits via DynamoDB                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `scout_service.py` | `backend/app/services/` | Main execution logic, Firecrawl integration, `double_probe()` |
| `scouts.py` | `backend/app/routers/` | `/api/scouts/execute` endpoint |
| `execution_deduplication.py` | `backend/app/services/` | EXEC# record management |
| `notification_service.py` | `backend/app/services/` | Localized email notifications |
| `email_translations.py` | `backend/app/services/` | Email strings (12 languages) |

## Deduplication Mechanisms

### Layer 1: Firecrawl changeTracking
- Per-scout baseline via `tag` parameter (`{user_id}#{scraper_name}`)
- Prevents re-analyzing unchanged content
- Returns "same" if no changes detected

### Layer 2: EXEC# Records
- Embedding-based similarity (cosine >= 0.85 = duplicate)
- Compares against last 20 executions for this scout
- Prevents duplicate notifications for semantically similar findings

## Preview vs Scheduled Mode

| Mode | Baseline | Notifications | Credits |
|------|----------|---------------|---------|
| **Preview** (Test button) | `content_hash` computed; `firecrawl` baseline confirmed via double-probe | Never sent | Not charged |
| **Scheduled** (Lambda) | Uses baseline from test step | Sent if criteria match | Charged |
| **Run Now** (Manual) | Uses baseline from test step | Sent if criteria match | Charged |

## Schedule-Time Baseline

When the user clicks "Schedule Scout", the `content_hash` from the test run is stored as an EXEC# baseline immediately — no background re-scrape needed. This gives `firecrawl_plain` URLs their hash baseline at schedule time, and `firecrawl` URLs already have their changeTracking baseline confirmed by the double-probe during test.

## Database Records

### EXEC# Records (Execution History)
```
PK: user_xxx
SK: EXEC#{scout_name}#{timestamp_ms}#{exec_id}
Fields: status, scout_type, summary_text, summary_embedding_compressed, is_duplicate
TTL: 90 days
```

## Credit Cost

| Operation | Credits |
|-----------|---------|
| Scheduled execution | 1 |
| Run Now | 1 |
| Preview/Test | 0 |

## Related Docs

- `docs/architecture/records-and-deduplication.md` - DynamoDB record types
