# Documentation Guide

This directory contains detailed architecture and feature documentation for coJournalist.

## Documentation Structure

```
docs/
├── CLAUDE.md                              # This file
├── architecture/
│   ├── adapter-pattern.md                 # How the adapter pattern works (port/adapter)
│   ├── developer-guide.md                 # How to develop and extend coJournalist
│   ├── edge-functions.md                  # Supabase Edge Function reference
│   ├── fastapi-endpoints.md               # All REST endpoints with examples
│   └── supabase-schema.md                 # PostgreSQL schema (tables, indexes, RLS)
├── features/
│   ├── civic.md                           # Civic Scout: council monitoring, promise extraction
│   ├── export.md                          # CMS export + Markdown download
│   ├── feed.md                            # Feed panel, export generation from units
│   ├── pulse.md                           # Smart Scout type `pulse` (news digest)
│   ├── scrape.md                          # Firecrawl extraction
│   ├── social.md                          # Social media monitoring (Apify)
│   └── web-scouts.md                      # Website change detection
├── specs/
│   └── oss-architecture.md                # OSS architecture design spec
└── deploy/
    └── SETUP.md                           # Self-host setup guide
```

## Key Documentation by Topic

### Scout System
- **Page Scout** (type `web`): `features/web-scouts.md` - Firecrawl changeTracking, per-scout baselines
- **Smart Scout** (type `pulse`): `features/pulse.md` - Multi-language search, AI filtering
- **Social Scout** (type `social`): `features/social.md` - Social media monitoring, Apify scraping
- **Civic Scout** (type `civic`): `features/civic.md` - Council website monitoring, promise extraction

### Feed & Export
- **Feed & Export**: `features/feed.md` - Feed panel and export generation from units
- **Export (CMS)**: `features/export.md` - CMS API export + Markdown download

### Architecture & Development
- **Adapter Pattern**: `architecture/adapter-pattern.md` - Port/adapter design, how to add new adapters
- **Developer Guide**: `architecture/developer-guide.md` - Local setup, extending scouts, contributing
- **Edge Functions**: `architecture/edge-functions.md` - Supabase Edge Function reference
- **API Endpoints**: `architecture/fastapi-endpoints.md` - All REST endpoints
- **Supabase Schema**: `architecture/supabase-schema.md` - PostgreSQL tables, indexes, RLS policies

## Writing Documentation

### Format Guidelines

1. **Start with overview** - Brief description and flow diagram
2. **Include code examples** - Request/response JSON, API calls
3. **Document edge cases** - Error handling, rate limits
4. **Link related docs** - Cross-reference other files

### Diagram Style

Use ASCII flow diagrams:
```
User Action → Frontend → Backend → External API
                ↓
           DynamoDB (record storage)
```

### Code Block Labels

Always specify language:
```json
{"example": "response"}
```

```python
def example_function():
    pass
```

```bash
curl -X POST https://api.example.com
```

## Updating Documentation

When making code changes:

1. **New feature**: Create doc in `features/`
2. **API change**: Update `architecture/fastapi-endpoints.md`
3. **Schema change**: Update `architecture/supabase-schema.md`
4. **Adapter change**: Update `architecture/adapter-pattern.md`
5. **Edge Function change**: Update `architecture/edge-functions.md`
6. **New integration**: Document within relevant feature doc in `features/`

### Documentation Checklist

- [ ] Overview section with flow diagram
- [ ] API endpoints with request/response examples
- [ ] Error handling section
- [ ] Rate limits documented
- [ ] Related docs linked
- [ ] Root CLAUDE.md updated if new major feature
