# Backend Tests

## Running Tests

```bash
cd backend

# All unit tests
python -m pytest tests/unit/ -v

# Specific suite
python -m pytest tests/unit/pulse/ -v
python -m pytest tests/unit/scouts/ -v
python -m pytest tests/unit/shared/ -v

# Single file
python -m pytest tests/unit/scouts/test_scout_pipeline.py -v
```

## Structure

```
tests/unit/
├── adapters/                       # Adapter implementations
│   ├── supabase/
│   │   └── test_auth.py            # SupabaseAuth: JWT validation, user lookup, service key
│   └── aws/
│       └── test_auth.py            # MuckRockAuth: session validation, user lookup
├── auth/                           # Auth router tests
│   └── test_auth_router.py         # MuckRock OAuth: login redirect, /me, logout, callback, webhook
├── api/                            # API endpoint tests
│   ├── test_v1_endpoints.py        # External API (v1) endpoints
│   └── test_admin.py               # Admin dashboard endpoints
├── pulse/                          # Smart Scout (type pulse) pipeline
│   ├── test_domain_cap.py          # Per-domain article limits
│   ├── test_excluded_domains.py    # Domain blocklist
│   ├── test_filter_prompts.py      # AI filter prompt generation
│   ├── test_homepage_filter.py     # Homepage/index URL rejection
│   ├── test_standing_page_filter.py # Standing/section page URL rejection
│   ├── test_pdf_enrichment.py      # PDF OCR enrichment (date extraction, scraping)
│   ├── test_tourism_filter.py      # Tourism/travel content heuristic
│   ├── test_pulse_pipeline.py      # End-to-end pipeline mocking
│   ├── test_rarity_scoring.py      # Source rarity scoring
│   └── test_query_generation.py    # LLM query generation (French/local)
├── scouts/                         # Web Scout pipeline
│   ├── test_scout_pipeline.py      # Change tracking, criteria matching, notifications
│   ├── test_scout_fallback.py      # Plain scrape fallback, hash detection, unified scrape, probe
│   └── test_exec_hash.py           # EXEC# content_hash and provider storage
└── shared/                         # Cross-cutting infrastructure
    ├── test_cron.py                # Cron expression builder
    ├── test_embedding_utils.py     # Embedding compression, cosine similarity
    ├── test_atomic_units.py        # AtomicUnitService key building
    ├── test_scraper_schemas.py     # Pydantic schema validation
    └── test_cms_export.py          # CMS URL validation, SSRF protection, token handling
```

## Conventions

- **Mocking:** Patch at import location (e.g. `app.services.scout_service.get_http_client`, not `app.utils.http.get_http_client`)
- **Async tests:** Use `@pytest.mark.asyncio` with `AsyncMock` for async services
- **HTTP mocks:** Use `AsyncMock` with `side_effect` for sequential HTTP call chains (e.g. Firecrawl then OpenRouter)
- **No network calls:** All external services (Firecrawl, OpenRouter, DynamoDB, Resend) must be mocked
- **Test naming:** `test_<behavior>` describing expected outcome, not implementation

## Key Mock Patterns

### Scout Service (sequential HTTP calls)

```python
mock_client = AsyncMock()
mock_client.post = AsyncMock(side_effect=[firecrawl_response, openrouter_response])
mock_get_client = AsyncMock(return_value=mock_client)
```

