# Smart Scout Service (type `pulse`)

> **Naming:** In the UI, this appears as "Smart Scout". The backend type code is `pulse`.

AI-curated digest of niche sources and stories under the radar, with multi-language search and fact-level deduplication.

## Overview

Smart Scout (type `pulse`) surfaces niche sources, community blogs, and underreported stories. Supports location-only, criteria-only, or combined location+criteria scoping. Always sends notifications when executed on schedule.

**`topic` vs `criteria`:** The `criteria` field is the search driver (keywords, topic, or specific criteria passed to the query generator). The `topic` field is an organizational tag set in the Schedule modal, used only for info unit tagging -- it does not drive search. `PulseSearchRequest` has no `topic` field. `PulseExecuteRequest` has both: if `criteria` is empty but `topic` is set, `topic` is copied to `criteria` for backward compatibility with old SCRAPER# records.

## Execution Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                SMART SCOUT (PULSE) EXECUTION                      │
│                                                                  │
│  Trigger: EventBridge → Lambda → POST /api/pulse/execute         │
│           OR: UI search → POST /api/pulse/search                 │
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
│  ├─ Execute all queries concurrently (max 5 parallel)            │
│  ├─ Sources: niche=["news","web"], reliable=["news"]             │
│  ├─ URL dedup + homepage/index/standing page rejection           │
│  └─ Optional: exclude_urls for cross-category dedup              │
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

| File | Location | Purpose |
|------|----------|---------|
| `pulse_orchestrator.py` | `backend/app/services/` | Main orchestration logic |
| `query_generator.py` | `backend/app/services/` | LLM-powered search + discovery query generation |
| `pulse.py` | `backend/app/routers/` | `/api/pulse/*` endpoints |
| `news_utils.py` | `backend/app/services/` | FirecrawlTools, embedding dedup, URL heuristic filters, PDF enrichment |
| `filter_prompts.py` | `backend/app/services/` | AI filter prompt templates (13 prompts across scope/category/mode) |
| `atomic_unit_service.py` | `backend/app/services/` | Fact extraction and dedup |
| `notification_service.py` | `backend/app/services/` | Localized email notifications |
| `email_translations.py` | `backend/app/services/` | Email strings (12 languages) |

**Dependencies:** `langdetect` (for language-aware deduplication scoring)

## Deduplication Mechanisms

### Layer 1: URL Deduplication + Quality Filters
- Simple URL-based dedup during search aggregation
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

**Validation:** At least one of `location` or `criteria` must be provided (enforced by `PulseSearchRequest` and `PulseExecuteRequest`).

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
| Scheduled execution | 1 |
| UI search (preview) | 0 |

## Benchmarking

Run the audit script to test all 12 scope x source_mode permutations:

```bash
cd backend
python scripts/benchmark_pulse.py --audit    # Full audit (12 searches + markdown report)
python scripts/benchmark_pulse.py            # Quick benchmark (3 scenarios, wall-clock time)
```

Results are written to `backend/smart-scout-results.md` with a summary matrix and per-permutation article details.

## Related Docs

- `docs/architecture/records-and-deduplication.md` - DynamoDB record types and dedup layers
