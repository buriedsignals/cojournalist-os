# Civic Scout Service (type `civic`)

> **Naming:** In the UI, this appears as "Track a Council". The backend type code is `civic`.
> **Tier:** Requires Pro plan. Free-tier users see the option with a "PRO" badge and are redirected to the pricing page.

Monitor local council websites for meeting minutes, agendas, and official decisions. Extracts political promises and commitments from documents and tracks them with due-date notifications.

## Overview

Civic Scout uses Firecrawl's Map API to discover all URLs on a council domain, ranks them with an LLM to find the best index pages for meeting protocols, lets the user confirm which URLs to track (max 2), tests extraction on those pages, and then runs on a monthly schedule to detect new documents. Documents (both PDF and HTML) are parsed via Firecrawl and analyzed by an LLM to extract promises and commitments with dates. When a due date approaches, a separate Lambda sends a digest notification to the journalist.

## UI Flow (3 Steps)

```
1. Start Search — User enters council domain
         │
         ▼
   Firecrawl Map API discovers all URLs (~3 seconds)
   LLM ranks top 5 INDEX pages (not individual documents)
   User selects up to 2 pages to track
         │
         ▼
2. Test Extraction — User sets optional criteria, clicks "Test Extraction"
         │
         ▼
   POST /api/civic/test — fetches pages, finds document links,
   parses up to 2 docs via Firecrawl, extracts promises with LLM
   Filter: future dates only; criteria mismatches dropped when criteria set
   Preview displayed in UI
         │
         ▼
3. Schedule Scout — User clicks "Schedule Scout"
         │
         ▼
   POST /api/scrapers/monitoring — creates SCRAPER# record + EventBridge schedule
   Initial promises from test step stored as PROMISE# records in DynamoDB
   Credits consumed at schedule time
```

## Discovery Pipeline

```
User enters domain (e.g. "gemeinde.zermatt.ch")
         │
         ▼
Firecrawl Map API → 150-200 URLs discovered (no scraping, ~3s)
         │
         ▼
LLM ranks URLs → top 5 INDEX pages returned
  - Prefers listing/archive pages over individual documents
  - Prompt: "Do NOT return individual PDF URLs — return pages that LINK TO them"
  - Multilingual: handles German, French, English council sites
         │
         ▼
User selects up to 2 pages to track
```

## Test Extraction

Before scheduling, the user tests extraction on selected URLs:

1. Fetch tracked URLs via Firecrawl scrape (rawHtml)
2. Extract all `<a>` links from HTML
3. Classify links as meeting documents (keyword match → LLM fallback)
4. PDFs prioritized over HTML; navigation links filtered (path depth ≤ 2)
5. Parse up to 2 documents via Firecrawl scrape (markdown format)
6. LLM extracts promises (two prompt strategies — see below)
7. Filter: drop promises without dates, drop past dates, drop criteria mismatches
8. Return preview (no storage, no credit decrement)

## Promise Extraction

Two distinct LLM prompt strategies depending on whether the user set criteria:

**No criteria (exhaustive):** Extracts every promise, budget item, commitment, and investment individually. Compact context (1-2 sentences) keeps output within the 4000-token budget. All extracted items get `criteria_match=True`.

**With criteria (targeted):** Tells the LLM to ONLY extract items directly relevant to the criteria topic. Unrelated items are never emitted. Returns `[]` if nothing matches. All returned items are matches by definition (`criteria_match=True`).

Date extraction is aggressive in both modes:
- Specific dates → use as-is
- Year references (e.g. "2027") → YYYY-12-31
- Quarter references (e.g. "Q3 2026") → end-of-quarter date
- Budget years → year-end date
- No date inferrable → null (filtered out)

## Promise Storage at Schedule Time

When the user schedules a civic scout, promises from the test extraction are stored immediately as PROMISE# records. This follows the same pattern as social scout `baseline_posts`. The journalist gets value from day one — not just after the first scheduled Lambda run.

## Execution Flow (Scheduled)

```
┌──────────────────────────────────────────────────────────────────┐
│                   CIVIC SCOUT EXECUTION                          │
│                                                                  │
│  Trigger: EventBridge → scraper-lambda → POST /api/civic/execute │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: Fetch + Hash                                            │
│  ├─ GET each tracked_url (raw HTML via Firecrawl)                │
│  └─ SHA-256 hash of all concatenated content                     │
│           │                                                      │
│           ▼                                                      │
│  Step 2: Change Detection                                        │
│  ├─ Load stored content_hash from SCRAPER# record                │
│  └─ If hash unchanged → return status="no_changes"               │
│           │                                                      │
│           ▼                                                      │
│  Step 3: Detect New Documents                                    │
│  ├─ Extract href links from fetched HTML                         │
│  ├─ Classify as meeting documents (keywords → LLM fallback)      │
│  └─ PDFs prioritized, navigation filtered, exclude processed     │
│           │                                                      │
│           ▼                                                      │
│  Step 4: Parse + Extract (max 2 docs per run)                    │
│  ├─ Firecrawl scrape with markdown format (PDF + HTML)           │
│  ├─ LLM extracts promises (exhaustive or criteria-targeted)      │
│  └─ Filter: future dates only + criteria match (when set)        │
│           │                                                      │
│           ▼                                                      │
│  Step 5: Store + Notify                                          │
│  ├─ Store PROMISE# records in DynamoDB (one per promise)         │
│  ├─ Update SCRAPER# with new hash + processed URLs               │
│  ├─ Store EXEC# record                                           │
│  └─ Send notification if promises_found > 0                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Promise Notification Flow

A separate Lambda (`promise-checker-lambda`) handles due-date notifications:

```
Daily cron → promise-checker-lambda
  1. Query PROMISE# records via GSI2 (GSI2PK = "DUEDATE#{YYYY-MM-DD}")
  2. Find promises due within the next notification window
  3. POST /api/civic/notify-promises with matched promises
  4. FastAPI sends accountability-framed digest email via Resend
  5. Marks promises as "notified"
```

Email format:
- **"Promises Due for Review"** header
- "Follow up to verify whether they have been delivered"
- Each promise: claim as heading, deadline as eyebrow, source PDF in blockquote callout

## Data Model

All records stored in the `scraping-jobs` DynamoDB table.

### SCRAPER# (scout config — extended for Civic)

| Field | Type | Description |
|-------|------|-------------|
| `tracked_urls` | string[] | Council pages to monitor (max 2) |
| `root_domain` | string | Original domain entered by user |
| `content_hash` | string | SHA-256 hash of last fetched content |
| `processed_pdf_urls` | string[] | Already-parsed document URLs (capped at 100) |
| `location` | object | Optional location (same as other scout types) |
| `topic` | string | Optional topic tag |
| `criteria` | string | Optional filtering criteria |

### PROMISE# Records

```
PK: {user_id}
SK: PROMISE#{scraper_name}#{promise_id}
```

| Field | Type | Description |
|-------|------|-------------|
| `promise_text` | string | Short summary of the commitment |
| `context` | string | Surrounding context from the document |
| `source_url` | string | URL of the source document |
| `source_date` | string | ISO date extracted from document |
| `due_date` | string | ISO date (future only — past dates filtered) |
| `date_confidence` | string | `"high"`, `"medium"`, or `"low"` |
| `criteria_match` | boolean | Whether promise matched user criteria |
| `status` | string | `"pending"` or `"notified"` |
| `GSI2PK` | string | `"DUEDATE#{due_date}"` |
| `GSI2SK` | string | `"{user_id}#{promise_id}"` |
| `ttl` | number | 90 days (with due date) or 180 days (undated) |

**Promise ID:** Deterministic 16-char hex — `SHA-256(source_url + promise_text)[:16]`

### GSI2-DueDate Index

Enables `promise-checker-lambda` to efficiently query promises by due date.

## Document Processing

| Detail | Value |
|--------|-------|
| Parser | Firecrawl scrape (markdown format) |
| Handles | Both PDF and HTML documents |
| Max docs per run | 2 (`MAX_DOCS_PER_RUN`) |
| Max text per LLM call | 15,000 characters |
| Date extraction | Aggressive: years → YYYY-12-31, quarters → end-of-quarter |

## Credit Costs

| Operation | Credits | Notes |
|-----------|---------|-------|
| Discovery (`/civic/discover`) | 10 | Map API + LLM ranking |
| Test extraction (`/civic/test`) | 0 | Validates credits but does not decrement |
| Scheduled execution | 20 | Charged by Lambda |

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| `POST` | `/api/civic/discover` | Session cookie | 3/hour | Map council domain, return ranked candidate URLs (top 5) |
| `POST` | `/api/civic/test` | Session cookie | 3/hour | Test extraction on selected URLs, return promise preview |
| `POST` | `/api/civic/execute` | `X-Service-Key` | — | Scheduled execution: fetch, detect docs, extract promises, notify |
| `POST` | `/api/civic/notify-promises` | `X-Service-Key` | — | Send accountability digest email for due promises |

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `civic_orchestrator.py` | `backend/app/services/` | Discovery (map+rank), test, execute pipeline |
| `civic.py` | `backend/app/routers/` | `/api/civic/*` endpoints |
| `civic.py` | `backend/app/schemas/` | Request/response Pydantic models |
| `CivicScoutView.svelte` | `frontend/src/lib/components/news/` | 3-step UI (search, test, schedule) |
| `StepButtons.svelte` | `frontend/src/lib/components/ui/` | 3-step button component with slot support |
| `FormPanel.svelte` | `frontend/src/lib/components/ui/` | Amber badge variant for civic |
| `NewScoutDropdown.svelte` | `frontend/src/lib/components/ui/` | Pro tier gate with PRO badge |
| `benchmark_civic.py` | `backend/scripts/` | Pipeline benchmark + audit (includes Zermatt) |
| `promise-checker-lambda` | `aws/lambdas/promise-checker-lambda/` | Daily due-date checker |
| `notification_service.py` | `backend/app/services/` | Email notifications via Resend |

## Related Docs

- `docs/architecture/records-and-deduplication.md` - DynamoDB record types
- `docs/architecture/aws-architecture.md` - Lambda functions, DynamoDB, EventBridge
- `docs/architecture/fastapi-endpoints.md` - Full endpoint reference
