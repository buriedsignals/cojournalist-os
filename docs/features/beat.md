# Beat Scout (type `beat`)

> **Naming:** Publicly this is the **Beat Scout** surface. It can be scoped by geography, topic/criteria, or both. Older repo references may describe the geography-scoped Beat Scout flow with legacy wording.

AI-curated digest with multi-language search and fact-level deduplication.

## Overview

The beat pipeline surfaces niche sources, community blogs, and underreported stories. It supports location-only, criteria-only, or combined location+criteria scoping. Scheduled creation runs a baseline-only pass first: current findings are deduped and hidden from the inbox, the scout gets `baseline_established_at`, and later Run Now/cron executions notify only on new material.

Beat Scouts can run weekly or monthly. Daily schedules are intentionally
rejected because this pipeline fans out across search, filtering, extraction,
and deduplication; weekly is the highest supported frequency.

**Beat Scout modes:**
- **Geography-scoped Beat Scout** — requires a location, optionally accepts criteria. Often used with **niche** sources.
- **Topic-scoped Beat Scout** — requires criteria, no location. Often used with **reliable** sources.

Both flows expose a source mode toggle so users can switch between niche and reliable. The backend pipeline is identical; only the default parameters differ.

**`topic` vs `criteria` vs `description`:** The `criteria` field is the search/filter driver (keywords, inclusion/exclusion rules, thresholds, and notification requirements). The `topic` field is only for organization and UI filtering: store 1-3 short comma-separated tags such as `housing, council, budget`, not a sentence. The optional `description` field is human/agent context shown on scout cards. Every scout must have either a location or topic tags so it can be scoped and browsed. `BeatSearchRequest` has no `topic` field. `BeatExecuteRequest` has both: if `criteria` is empty but `topic` is set, `topic` is copied to `criteria` for backward compatibility with old SCRAPER# records.

## Execution Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                  BEAT SCOUT (CURRENT v2)                         │
│                                                                  │
│  Trigger: pg_cron → execute-scout EF → scout-beat-execute       │
│           OR: UI preview → POST /functions/v1/beat-search       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: Query Generation (query_generator.py)                   │
│  ├─ LLM generates queries in local language + English            │
│  ├─ News category: also generates discovery_queries              │
│  │   (community events, jobs, civic groups, local blogs)         │
│  ├─ Government category: discovery_queries for public sector     │
│  └─ Categories: news, government, analysis                       │
│           │                                                      │
│           ▼                                                      │
│  Step 2: Direct Search (Firecrawl)                               │
│  ├─ Execute explicit source passes concurrently                  │
│  ├─ Location/combined: web pass per query                         │
│  ├─ Topic-only: web + news + recent-web passes per query          │
│  ├─ Discovery queries: web only                                   │
│  └─ Firecrawl filters invalid URLs and excluded domains           │
│           │                                                      │
│           ▼                                                      │
│  Step 2.5: PDF OCR Enrichment                                    │
│  ├─ Detect PDF URLs in results (max 3 per search)                │
│  ├─ Scrape via Firecrawl OCR (max 5 pages per PDF)               │
│  └─ Enrich dates, descriptions, titles from extracted text       │
│           │                                                      │
│           ▼                                                      │
│  Step 3: Date Filter + Staleness Gate                            │
│  ├─ Scope-aware date windows (7d–21d depending on config)        │
│  ├─ 90-day absolute staleness floor (no article older than 90d)  │
│  └─ Undated cap: separate buckets for news vs discovery          │
│           │                                                      │
│           ▼                                                      │
│  Step 4: Embedding Deduplication                                 │
│  ├─ Embed each result title+description                          │
│  ├─ Cluster by cosine similarity (threshold: 0.80)               │
│  └─ Keep highest-scoring from each cluster                       │
│           │                                                      │
│           ▼                                                      │
│  Step 5: Cluster + Tourism Filter (niche only)                   │
│  ├─ Drop mainstream news (cluster_size >= 3)                     │
│  └─ Drop tourism/travel content (niche+location+news only)       │
│           │                                                      │
│           ▼                                                      │
│  Step 6: AI Filtering (GPT-4o-mini)                              │
│  ├─ Filter by relevance to location/topic                        │
│  ├─ Target: 5-6 (niche) or 6-8 (reliable) articles              │
│  ├─ Niche: HARD REJECT tourism/travel at top of prompt           │
│  ├─ Priority: community blogs, civic groups, indie publications  │
│  └─ Domain cap: 2/domain (niche) or 3/domain (reliable)         │
│           │                                                      │
│           ▼                                                      │
│  Step 7: Fact-Level Deduplication (Scheduled only)               │
│  ├─ Extract 1-3 atomic facts per article                         │
│  ├─ Compare against facts from previous runs                     │
│  └─ Return only NEW facts (not seen before)                      │
│           │                                                      │
│           ▼                                                      │
│  Step 8: Summary & Notification                                  │
│  ├─ Generate summary from new facts                              │
│  ├─ Store EXEC# record                                           │
│  ├─ Store atomic units in knowledge base                         │
│  └─ Send localized email (user's preferred_language)             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Files

### v2 (Supabase Edge Functions) — authoritative source of truth

| File | Location | Purpose |
|------|----------|---------|
| `scout-beat-execute/index.ts` | `supabase/functions/` | Beat scout entrypoint. Branches on `priority_sources`: explicit → direct scrape; empty → full 8-stage pipeline. Parallel news + government category fan-out when criteria + location are both set. Two-section email (news + gov) via `sendBeatAlert`. |
| `_shared/beat_pipeline.ts` | `supabase/functions/` | Ported legacy pipeline: `generateQueries` (LLM multilingual), `runSearches` (explicit Firecrawl web/news/recent-web passes), `applyDateFilter` + `capUndatedResults` (14/28/90d windows + two-bucket caps), `isLikelyTourismContent` (niche+location+news prefilter), `dedupeByEmbedding` (cosine + rarity + +8 local-language bonus), `clusterFilter` (niche only), `aiFilterResults` (LLM picks top-N), `generateBeatSummary` (bulleted email summary). |
| `beat-search/index.ts` | `supabase/functions/` | Preview endpoint — synchronous version of the pipeline for the New Scout modal's "Start Search" button. No credit charge, no persistence. |

### Legacy (v1 FastAPI) — for reference during cutover only

| File | Location | Purpose |
|------|----------|---------|
| `pulse_orchestrator.py` | `backend/app/services/` | Historical orchestration logic (ported to `_shared/beat_pipeline.ts`) |
| `query_generator.py` | `backend/app/services/` | LLM-powered search + discovery query generation |
| `pulse.py` | `backend/app/routers/` | Historical `/api/pulse/*` endpoints from the pre-cutover backend |
| `news_utils.py` | `backend/app/services/` | FirecrawlTools, embedding dedup, URL heuristic filters, PDF enrichment |
| `filter_prompts.py` | `backend/app/services/` | AI filter prompt templates (13 prompts across scope/category/mode) |
| `atomic_unit_service.py` | `backend/app/services/` | Fact extraction and dedup |
| `notification_service.py` | `backend/app/services/` | Localized email notifications |
| `email_translations.py` | `backend/app/services/` | Email strings (12 languages) |

## v1 → v2 parity notes

The v2 port preserves all 8 pipeline stages with these clarifications:

- **Stage 1 (query gen):** Gemini 2.5 Flash-Lite via Google direct API (legacy used OpenRouter). Schema-constrained output. Caching not yet ported — v1 kept a 24h in-memory query cache with TTL.
- **Stage 5 (tourism pre-filter):** identical 11-domain + 6-title pattern list.
- **Stage 6 (embedding dedup):** scope-aware thresholds preserved (combined 0.85 / location 0.82 / topic 0.80). The `+8` local-language bonus is approximated via a charset heuristic (`/[À-ÿ]/`) instead of `langdetect`, to avoid shipping a heavy ML model in the Edge runtime. Slight precision loss on non-Latin scripts (JP/KR/ZH); flagged as a follow-up if needed.
- **Stage 9 (email summary):** LLM-composed bulletin per category. When the user supplied explicit `priority_sources`, falls back to a plain bulleted statement list.
- **Credit:** 7 credits per run unchanged from legacy. Refunded via `refund_credits` RPC when the pipeline yields 0 URLs or the run errors.

## Deduplication Mechanisms

### Layer 1: URL Deduplication + Quality Filters
- Firecrawl Search is the external-search boundary. `_shared/firecrawl.ts` normalizes both legacy flat results and current `web`/`news` result groups into one `SearchHit` shape with `url`, `title`, `description`, `date`, and `source`.
- The beat pipeline sends `ignoreInvalidURLs: true` and `excludeDomains` to Firecrawl so obvious bad URLs and blocked domains are removed before local filtering.
- Topic-only scouts use separate calls for web, news, and recent-web because Firecrawl's `tbs` recency control applies to web search, not news search. Discovery queries stay web-only.
- `scrapeOptions` is not enabled during search fan-out because Firecrawl charges search plus scrape credits when search results are scraped inline; extraction remains a later, narrowed stage.
- Simple URL-based dedup during search aggregation
- Source dates are normalized through `_shared/atomic_extract.ts::sourcePublishedDate`: Firecrawl scrape metadata first, visible date near the top of scraped markdown second, Firecrawl search date last. This feeds extraction prompts and `information_units.occurred_at` fallback, but it is not a hard relevance gate.
- **Homepage/index rejection**: bare `/`, `/blog`, `/news` etc. are dropped (`is_index_or_homepage`)
- **Standing page rejection**: institutional/section pages with short paths and no numeric IDs (`is_likely_standing_page`) — catches gov landing pages, stats dashboards, agenda indexes
- Removes exact duplicate URLs from multiple queries

### Layer 1.5: PDF OCR Enrichment
- Detects PDF URLs in search results (max 3 per search)
- Scrapes via Firecrawl `/v2/scrape` with `parsers: [{"type": "pdf", "mode": "auto"}]`
- Extracts dates from PDF metadata or text content (multi-language regex patterns)
- Replaces empty/short descriptions with extracted text
- Cost: 1 Firecrawl credit per PDF page (max 5 pages per PDF)

### Layer 2: Embedding Deduplication (0.80 threshold)
- Embeds article title + description
- Clusters similar articles by cosine similarity
- Keeps highest-scoring article from each cluster
- **Language-aware scoring** for non-English locales (see below)

#### Article Scoring (for cluster selection)
When multiple articles cover the same story, the system picks the best one using:

| Factor | Points | Description |
|--------|--------|-------------|
| Has publication date | +5 | Dated articles preferred |
| Undated news penalty | -5 | Undated news articles penalized (discovery undated: neutral) |
| Local domain TLD | +5 | `.ca`, `.ch`, `.fr`, etc. based on location |
| Domain rarity | +4 to +8 | Rare domains get higher scores (freq 1 = +8, freq 2 = +6) |
| Discovery pass bonus | +6 | Community/blog sources preferred over news |
| **Language match** | +8 | Article language matches locale (non-English only) |
| Description length | +0-3 | Longer descriptions slightly preferred |

**Language detection:** Uses `langdetect` library to detect article language from title + description. For non-English locales (e.g., Montreal → French, Zurich → German), articles in the local language get +8 bonus, ensuring they win over English articles covering the same story.

### Layer 2.5: Cluster + Tourism Filter (niche only)
- **Cluster filter**: drops mainstream news articles with cluster_size >= 3
- **Tourism filter**: rejects travel blogs and tourism guides by domain/title patterns (niche + location + news only, via `is_likely_tourism_content`)

### Layer 3: Fact-Level Deduplication
- Extracts atomic facts from articles
- Compares against facts from previous runs (same scout)
- Only NEW facts trigger notifications

## Scope Modes

| Mode | Configuration | Search Behavior |
|------|---------------|-----------------|
| **Location-only** | `location` set, no `criteria` | Local news terms in that location |
| **Criteria-only** | `criteria` set, no `location` | Criteria searches globally |
| **Combined** | Both `location` and `criteria` | Criteria searches scoped to location |

**Validation:** At least one of `location` or `criteria` must be provided (enforced by `BeatSearchRequest` and `BeatExecuteRequest`).

## Source Modes

| Mode | Sources | Discovery | Date Window | AI Target | Domain Cap |
|------|---------|-----------|-------------|-----------|------------|
| **niche** | news + web | LLM-generated discovery queries | 14d (28d fallback) | 5-6 | 2/domain |
| **reliable** | news only | None | 14d (28d fallback) | 6-8 | 3/domain |

### Recency Config by Scope

All scope/mode combinations use a **standard 14-day initial window**. When all dated articles fall outside this window, a **28-day relaxed fallback** is applied (capped at the 90-day absolute floor).

| Scope | Mode | Initial Window | Relaxed Fallback |
|-------|------|----------------|------------------|
| all | all | 14 days | 28 days |

All dated articles must also pass a **90-day absolute staleness floor** regardless of the window.

## Multi-Language Search

For non-English locations, the LLM generates queries in the local language.
Discovery queries (community events, jobs, civic groups) are also generated
in the local language, replacing previous hardcoded translation tables.

## Preview vs Scheduled Mode

| Mode | Dedup | Notifications | Credits | Units |
|------|-------|---------------|---------|-------|
| **Preview** (UI search) | URL + embedding only | Never | Not charged | Not stored |
| **Scheduled** (Lambda) | All 3 layers | Always sent | Charged | Stored |

## Database Records

### EXEC# Records
```
PK: user_xxx
SK: EXEC#{scout_name}#{timestamp_ms}#{exec_id}
Fields: summary_text (from new facts only), is_duplicate
TTL: 90 days
```

### Information Units
```
Table: information-units
PK: USER#{user_id}#LOC#{country}#{state}#{city}
SK: UNIT#{timestamp_ms}#{unit_id}
Fields: statement, unit_type, entities[], source_url, embedding_compressed
TTL: 90 days (extended on use)
```

## Credit Cost

| Operation | Credits |
|-----------|---------|
| Scheduled execution | 7 |
| UI search (preview) | 0 |

## Benchmarking

Run the Supabase-era Beat health benchmark to exercise the real discovery path:

```bash
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts --scout-id <existing-beat-scout-uuid>
deno run --allow-env --allow-net --allow-read=. scripts/benchmark-beat.ts --timeout-min 8
```

The default run checks five canaries (location-only, topic-only, topic+country,
topic+city, second topic+country) through both preview search and scheduled
execution. It retries a canary once on likely transient infra failures such as a
run timeout or zero-result response, but still fails hard on semantic drift.
`--scout-id` replays one existing Beat scout configuration on a temporary
benchmark user to validate backward compatibility without touching the original scout.

## Related Docs

- `docs/architecture/records-and-deduplication.md` - DynamoDB record types and dedup layers
