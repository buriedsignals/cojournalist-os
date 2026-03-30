# Backend (FastAPI)

Python FastAPI backend hosted on Render. Handles scout execution, news search, and scheduling.

## Structure

```
backend/app/
├── main.py              # FastAPI app, middleware, routes
├── config.py            # Settings from environment
├── dependencies.py      # Session cookie auth, service key verification
├── routers/             # API endpoints
│   ├── scouts.py        # Page Scout execution (Lambda)
│   ├── pulse.py         # Pulse endpoints (UI + Lambda)
│   ├── social.py        # Social Scout endpoints (UI + Lambda)
│   ├── civic.py         # Civic Scout endpoints (UI + Lambda)
│   ├── scraper.py       # Schedule management (UI calls these)
│   ├── units.py         # Information units for Feed panel
│   ├── data_extractor.py # Data extraction (scraping)
│   ├── export.py        # Feed export generation + CMS proxy
│   ├── auth.py          # MuckRock OAuth login/callback/logout
│   ├── user.py          # User preferences
│   ├── onboarding.py    # User onboarding
│   └── v1.py            # External API (v1)
├── services/            # Business logic
│   ├── scout_service.py              # Page Scout execution
│   ├── pulse_orchestrator.py         # Smart Scout (type `pulse`) orchestration
│   ├── social_orchestrator.py        # Social Scout orchestration (Apify scrapers)
│   ├── civic_orchestrator.py         # Civic Scout orchestration (council monitoring)
│   ├── query_generator.py            # LLM-powered search query generation
│   ├── openrouter.py                 # OpenRouter LLM client (configurable model)
│   ├── news_utils.py                 # Shared news utilities (FirecrawlTools, etc.)
│   ├── notification_service.py       # Resend email (localized)
│   ├── email_translations.py         # Email localization (12 languages)
│   ├── embedding_utils.py            # Embedding functions (text + multimodal)
│   ├── url_validator.py              # SSRF protection
│   ├── execution_deduplication.py    # Execution-level dedup (EXEC# records, embeddings)
│   ├── atomic_unit_service.py        # Atomic unit extraction + storage
│   ├── feed_search_service.py        # Feed panel queries + semantic search
│   └── schedule_service.py           # EventBridge schedule management
├── schemas/             # Pydantic models
│   ├── scouts.py        # Page Scout request/response models
│   ├── pulse.py         # Pulse request/response models (includes criteria support)
│   ├── social.py        # Social Scout request/response models
│   ├── civic.py         # Civic Scout request/response models
│   ├── units.py         # Information unit models
│   ├── v1.py            # External API schemas
│   └── common.py        # Shared schema types
└── models/              # Database models (if any)
```

## Key Routers

### `/api/scouts/*` - Scout Execution (Lambda-triggered)
- `POST /scouts/execute` - Page Scout
- `POST /scouts/test` - Test without notifications

**Auth:** `X-Service-Key` header (Lambda → FastAPI)

### `/api/pulse/*` - Smart Scout type `pulse` (UI + Lambda)
- `POST /pulse/search` - AI news search (UI, rate limited)
- `POST /pulse/execute` - Lambda-triggered execution

**Scope:** Requires at least one of `location` or `topic`. Supports location-only, topic-only, or combined.
**Auth:** Session cookie (search) / `X-Service-Key` (execute)

### `/api/social/*` - Social Scout (UI + Lambda)
- `POST /social/test` - Validate profile + baseline scan
- `POST /social/execute` - Full execution (scrape, diff, summarize/criteria, notify)

**Auth:** Session cookie (test) / `X-Service-Key` (execute)

### `/api/civic/*` - Civic Scout (UI + Lambda)
- `POST /civic/discover` - Discover meeting pages from council domain
- `POST /civic/execute` - Full execution (scrape, parse, extract promises)
- `POST /civic/notify-promises` - Send promise notification email

**Auth:** Session cookie (discover) / `X-Service-Key` (execute, notify)

### `/api/scrapers/*` - Schedule Management (UI-triggered)
- `POST /scrapers/monitoring` - Create scout schedule
- `GET /scrapers/active` - List user's scouts
- `DELETE /scrapers/active/{name}` - Delete scout
- `POST /scrapers/run-now` - Manually trigger scout execution (proxies to internal execute endpoints)

**Auth:** Session cookie (user auth via `get_current_user`) + HMAC-signed service key (API Gateway)

### `/api/units/*` - Information Units (UI-triggered)
- `GET /units/locations` - List user's distinct locations
- `GET /units/topics` - List user's distinct topics
- `GET /units` - Get units by location for Feed panel
- `GET /units/by-topic` - Get units by topic for Feed panel
- `GET /units/search` - Semantic search (supports optional `topic` filter)
- `PATCH /units/mark-used` - Mark units as used in article

**Auth:** Session cookie

### `/api/auth/*` - Authentication
- `GET /auth/login` - OAuth login redirect
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/me` - Get current user
- `GET /auth/status` - Check auth status
- `POST /auth/logout` - Clear session
- `POST /auth/webhook` - MuckRock webhook (HMAC-SHA256)

**Auth:** None (login/callback), Session cookie (me/status/logout), HMAC (webhook)

### `/api/onboarding/*` - User Initialization
- `POST /onboarding/initialize` - Set timezone, language, location
- `GET /onboarding/status` - Check onboarding status
- `POST /onboarding/tour-complete` - Mark tour completed

**Auth:** Session cookie

### `/api/extract/*`, `/api/data/*` - Data Extraction
- `POST /extract/validate` - Validate credits for extraction
- `POST /data/extract` - Sync extraction (CSV download)
- `POST /extract/start` - Start async extraction
- `GET /extract/status/{job_id}` - Poll job status

**Auth:** Session cookie

### `/api/user/*` - User Preferences
- `GET /user/preferences` - Get preferences
- `PUT /user/preferences` - Update preferences

**Auth:** Session cookie

### `/api/v1/*` - External API (API key + session cookie auth)

See `docs/architecture/fastapi-endpoints.md` for full v1 API documentation.

## Key Services

| Service | Purpose |
|---------|---------|
| `scout_service.py` | Scrape URLs, AI criteria check |
| `pulse_orchestrator.py` | Smart Scout - direct search, dedup, filter, summary (location and/or topic, optional criteria) |
| `query_generator.py` | LLM-powered search query + discovery query generation (local language) |
| `news_utils.py` | Shared utilities (FirecrawlTools, embedding dedup, homepage/tourism filters) |
| `filter_prompts.py` | AI filter prompts for news, government, and topic analysis categories |
| `notification_service.py` | Unified email notifications via Resend (markdown→HTML, localized) |
| `email_translations.py` | Email localization (12 languages) + LLM title translation |
| `url_validator.py` | Validate URLs against allowlist (SSRF protection) |
| `execution_deduplication.py` | Execution-level dedup via EXEC# records + summary embeddings |
| `atomic_unit_service.py` | LLM extraction of atomic units from articles + DynamoDB storage (with topic metadata) |
| `feed_search_service.py` | Feed panel queries (location/topic retrieval, semantic search, mark-used) |
| `social_orchestrator.py` | Social Scout - Apify scraping, post diffing, criteria matching |
| `civic_orchestrator.py` | Civic Scout - council website discovery, PDF parsing, promise extraction |
| `openrouter.py` | OpenRouter LLM client (configurable model via `settings.llm_model`) |
| `schedule_service.py` | EventBridge schedule management (create/delete/run-now) |
| `embedding_utils.py` | Centralized embedding functions (text, multimodal, cosine similarity) |
| `api_key_service.py` | API key generation, validation, storage (v1 API) |
| `execute_pipeline.py` | Post-orchestrator pipeline for Smart Scout (fact dedup, EXEC#, notifications) |
| `export_generator.py` | Article draft generation from atomic units via LLM |
| `cron.py` | AWS EventBridge cron expression building |
| `http_client.py` | Shared HTTP clients with connection pooling |
| `locale_data.py` | Locale/timezone/language data constants |

## Deduplication

Two-layer deduplication prevents duplicate notifications:

### Layer 1: Fact-Level Deduplication (`atomic_unit_service.py`)

For Smart Scout (type `pulse`), operates at the individual fact level:
1. Extract 1-3 atomic facts per article using configurable LLM (settings.llm_model)
2. Embed each fact and compare against recent facts from previous runs
3. Only store NEW facts; duplicates are discarded
4. **Notification decision:** Only send if `new_facts` is non-empty

**Key insight:** Both EXEC# summary and email notification use `new_facts` directly:
- Summary: `generate_summary_from_facts(new_facts)` - describes only new findings
- Notification: Built from `new_facts` list (no URL matching back to articles)

### Layer 2: Execution-Level Records (`execution_deduplication.py`)

Stores EXEC# records for display and history:
1. Generates 1-sentence summary from `new_facts` only
2. Stores summary + embedding in EXEC# record
3. `is_duplicate` flag set based on whether any new facts exist
4. Recent findings injected into orchestrator prompts for context

**Storage:** EXEC# records in `scraping-jobs` table (same table as SCRAPER# and TIME#).

### Execution Flow (scheduled scouts)

```
Lambda → POST /api/pulse/execute
  1. Query recent facts → inject into orchestrator prompt
  2. Orchestrator runs (aware of past findings)
  3. process_results() → extracts facts, compares to history
     └─ Returns: new_facts[], duplicate_facts[], all_duplicates
  4. If all_duplicates:
     └─ Store EXEC# ("No new findings"), return early (no notification)
  5. If new facts exist:
     ├─ Generate summary FROM NEW_FACTS ONLY
     ├─ Store EXEC# with summary
     └─ Send notification with new_facts directly
```

## Email Notifications

The `notification_service.py` provides unified email formatting with localization support.

**Features:**
- `markdown_to_html()` - Converts markdown (headers, bold, lists, links) to email-safe HTML
- `_build_email_html()` - Unified template for all scout types with consistent branding
- `_translate_article_titles()` - Batch translate article titles via configurable LLM

**Localization (`email_translations.py`):**
- Static UI strings for 12 languages: en, no, de, fr, es, it, pt, nl, sv, da, fi, pl
- `get_string(key, language)` - Get localized string with English fallback
- `translate_titles_batch()` - LLM-based title translation for non-English users
- All send methods accept `language` parameter for localized emails

## Authentication

- **User endpoints:** Session cookie (MuckRock OAuth)
- **Lambda endpoints:** `X-Service-Key` header validated against `INTERNAL_SERVICE_KEY`

## Pulse Pipeline Quality Filters

The Smart Scout pipeline includes several quality gates to improve result relevance:

| Filter | Location | Scope | Description |
|--------|----------|-------|-------------|
| Homepage filter | `news_utils.is_index_or_homepage()` | All searches | Rejects `/`, `/blog`, `/news` and other section landing URLs |
| Standing page filter | `news_utils.is_likely_standing_page()` | All searches | Rejects institutional/section pages with short paths (≤2 segments) and no numeric IDs |
| 90-day staleness | `pulse_orchestrator.py` date loop | All searches | Absolute floor — no article older than 90 days regardless of date window |
| Content staleness | `news_utils.is_stale_content()` | Undated articles | Rejects undated articles with year in URL/title older than 1 year |
| Tourism heuristic | `news_utils.is_likely_tourism_content()` | Niche + location + news | Rejects travel blogs, tourism guides by domain/title patterns |
| Cluster filter | `pulse_orchestrator.py` | Niche + news | Drops mainstream articles with cluster_size >= 3 |
| PDF enrichment | `news_utils.enrich_pdf_results()` | All searches | Scrapes PDF URLs via Firecrawl OCR to extract dates and descriptions (max 3 per search) |
| Domain cap | `news_utils.ai_filter_results()` | All searches | 2 per domain (niche), 3 per domain (reliable) |
| Cross-category dedup | `exclude_urls` param | UI preview | Optional URL list to exclude across categories |

**Discovery queries** are LLM-generated (not hardcoded) via `query_generator.py`. The news category prompt requests community-focused queries targeting events, civic groups, volunteer networks, and local blogs in the local language. Government category discovery queries are criteria-aware: when criteria is present, they target government resources related to the criteria instead of generic institutions.

**Niche + location (no criteria)** runs only the news category (no government). Institutional content contradicts the niche promise of community/indie sources.

**Reliable mode** uses higher AI filter targets (6-8 articles) and a domain cap of 3 to ensure comprehensive coverage from established sources. All modes use a standard 14-day date window with a 28-day fallback when no dated results survive.

**Benchmarking:** Run `python scripts/benchmark_pulse.py --audit` to test all 12 permutations. Results are written to `backend/smart-scout-results.md`.

## Detailed Documentation

- `docs/architecture/fastapi-endpoints.md` - All endpoints with request/response examples
- `docs/architecture/records-and-deduplication.md` - DynamoDB record types and dedup architecture
- `docs/features/web-scouts.md` - Page Scout change detection and deduplication

---

## Critical Architecture - DO NOT REMOVE

### Page Scout Change Detection (`scout_service.py`)

**CRITICAL:** Page Scouts use Firecrawl's changeTracking format with **user-scoped** `tag` baselines.

```python
# _scrape_with_change_tracking() MUST use this exact format
tag = f"{user_id}#{scraper_name}"  # User-scoped: guarantees unique baselines
if len(tag) > 128:  # Safety margin — Firecrawl's max tag length is undocumented
    tag = tag[:128]

"formats": [
    "markdown",
    {
        "type": "changeTracking",
        "tag": tag  # User-scoped baseline
    }
]
```

**Tag format:** `{user_id}#{scraper_name}` — Firecrawl matches baselines on `{url} + {team_id} + {format} + {tag}`. Including `user_id` in the tag ensures two users monitoring the same URL with the same scout name get independent baselines.

**API format note:** The `tag` MUST be inside the object in the `formats` array, NOT in a separate `changeTrackingOptions` field. Firecrawl returns HTTP 400 "Unrecognized key" for `changeTrackingOptions`.

**Why this matters:**
- Without user-scoped `tag`: Two users with the same scout name monitoring the same URL share one baseline (BUG)
- With user-scoped `tag`: Each user's scout has independent change detection (CORRECT)
- Removing `user_id` from the tag re-introduces the shared-baseline bug

**DO NOT:**
- Remove the `user_id` parameter from `_scrape_with_change_tracking()`
- Remove the `tag` field from the Firecrawl request
- Replace `changeTracking` with a simple format string
- Use `scraper_name` alone as the tag (not user-scoped)

### Deduplication Services

| Service | Used For | DO NOT REMOVE |
|---------|----------|---------------|
| `ExecutionDeduplicationService` | EXEC# records, summary embeddings | `check_duplicate()`, `store_execution()` |
| `AtomicUnitService` | Fact-level dedup for Smart Scouts | `process_results()` |
| `embedding_utils` | Centralized embedding functions | `generate_embedding()`, `cosine_similarity()` |

**Service Dependencies:**
```
ExecutionDeduplicationService
  └─ uses embedding_utils.generate_embedding()

AtomicUnitService
  └─ uses embedding_utils.generate_embeddings_batch()

FeedSearchService
  └─ uses embedding_utils.generate_embedding()
```

**embedding_utils.py** provides all embedding functions: `generate_embedding()`, `generate_embeddings_batch()`, `cosine_similarity()`, `compress_embedding()`, `decompress_embedding()`.

### Preview Mode (`scout_service.py`)

**CRITICAL:** Preview mode uses `_firecrawl_scrape()` without a tag (no `changeTracking`).

```python
# preview_mode=True — plain scrape, no baseline established
scrape_result = await self._firecrawl_scrape(url)  # No tag = no changeTracking
```

Preview mode also computes `content_hash` from the scraped markdown. This hash is returned to the frontend and passed back at schedule time to establish the EXEC# baseline without re-scraping.

**Why this matters:**
- Test runs should not establish baselines (the probe establishes Firecrawl baselines separately)
- `content_hash` enables schedule-time baseline for `firecrawl_plain` URLs without re-scraping

### Schedule-Time Baseline (`scraper.py`)

**CRITICAL:** When a user schedules a web scout, the EXEC# baseline is stored immediately using `content_hash` from the test run. There is no background re-scrape.

```python
# schedule_monitoring() — store baseline at schedule time
if payload.scout_type == "web" and payload.content_hash:
    await exec_dedup.store_execution(
        content_hash=payload.content_hash,
        ...
    )
```

**Why this matters:**
- Eliminates wasteful re-scrape on first run
- `firecrawl_plain` URLs get their hash baseline established at schedule time
- `firecrawl` URLs get their changeTracking baseline confirmed via double-probe during test (two sequential changeTracking calls — second call's `previousScrapeAt` verifies storage)

**DO NOT:**
- Re-introduce `execute_initial_run_background` (deleted — baseline is now at schedule time)
- Remove `content_hash` from the test→frontend→schedule flow
