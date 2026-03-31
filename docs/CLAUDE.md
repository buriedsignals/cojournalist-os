# Documentation Guide

This directory contains detailed architecture and feature documentation for coJournalist.

## Documentation Structure

```
docs/
├── CLAUDE.md                              # This file
├── architecture/                          # Shared / SaaS-specific
│   ├── aws-architecture.md               # SaaS: DynamoDB, EventBridge, Lambda
│   ├── developer-guide.md                 # Local setup, extending scouts, contributing
│   ├── fastapi-endpoints.md               # All REST endpoints with examples
│   └── records-and-deduplication.md       # DynamoDB record types, dedup layers
├── features/                              # What each feature does
│   ├── civic.md                           # Civic Scout: council monitoring, promises (incl. design ref)
│   ├── export.md                          # CMS export + Markdown download
│   ├── feed.md                            # Feed panel, export generation from units
│   ├── pulse.md                           # Location Scout / Beat Scout (type `pulse`)
│   ├── scrape.md                          # Firecrawl extraction
│   ├── social.md                          # Social media monitoring (Apify)
│   └── web-scouts.md                      # Website change detection
├── oss/                                   # Everything OSS / self-hosted
│   ├── architecture.md                    # Strategy: two-repo model, licensing, what ships
│   ├── adapter-pattern.md                 # Port/adapter design, DI wiring, async patterns
│   ├── supabase-schema.md                 # PostgreSQL tables, indexes, RLS, migrations
│   ├── edge-functions.md                  # Supabase Edge Functions reference
│   ├── license-key.md                     # Stripe integration, key format, validation
│   ├── deployment-and-mirror.md           # Docker, Render, GitHub mirror CI
│   └── automation.md                      # setup.sh, sync-upstream, agent instructions
├── muckrock/                              # MuckRock integration (auth + billing)
│   ├── oauth-integration.md               # OpenID flow, scopes, session cookies
│   ├── userinfo-and-orgs.md               # Userinfo schema, org structure
│   ├── webhooks.md                        # Webhook payloads, signature verification
│   ├── plans-and-entitlements.md          # Tier definitions (Free/Pro/Team), credit costs
│   ├── entitlements-pro-design.md         # Pro tier design: resolution, pricing, webhooks
│   └── entitlements-team-design.md        # Team plan: shared credit pools, ORG# records, seats
├── benchmarks/                            # LLM model benchmarks
└── research/                              # LLM model research
```

## Key Documentation by Topic

### Scout System
- **Page Scout** (type `web`): `features/web-scouts.md` - Firecrawl changeTracking, per-scout baselines
- **Location Scout / Beat Scout** (type `pulse`): `features/pulse.md` - Multi-language search, AI filtering
- **Social Scout** (type `social`): `features/social.md` - Social media monitoring, Apify scraping
- **Civic Scout** (type `civic`): `features/civic.md` - Council monitoring, promise extraction, design reference

### Feed & Export
- **Feed & Export**: `features/feed.md` - Feed panel and export generation from units
- **Export (CMS)**: `features/export.md` - CMS API export + Markdown download

### Architecture
- **API Endpoints**: `architecture/fastapi-endpoints.md` - All REST endpoints
- **AWS Architecture**: `architecture/aws-architecture.md` - DynamoDB, EventBridge, Lambda (SaaS-only)
- **Records & Dedup**: `architecture/records-and-deduplication.md` - DynamoDB record types, dedup layers
- **Developer Guide**: `architecture/developer-guide.md` - Local setup, extending scouts, contributing

### OSS / Self-Hosted
- **Strategy**: `oss/architecture.md` - Two-repo model, licensing, what ships in the OSS mirror
- **Adapter Pattern**: `oss/adapter-pattern.md` - Port/adapter design, DI wiring, how to add adapters
- **Supabase Schema**: `oss/supabase-schema.md` - PostgreSQL tables, indexes, RLS policies
- **Edge Functions**: `oss/edge-functions.md` - Supabase Edge Function reference
- **License Key**: `oss/license-key.md` - Stripe integration, key format, validation, webhooks
- **Deployment & Mirror**: `oss/deployment-and-mirror.md` - Docker, Render, GitHub mirror CI
- **Automation**: `oss/automation.md` - setup.sh, sync-upstream, agent instructions

### MuckRock / Billing
- **OAuth**: `muckrock/oauth-integration.md` - OpenID flow, session cookies
- **Plans & Credits**: `muckrock/plans-and-entitlements.md` - Tier definitions, credit costs
- **Pro Design**: `muckrock/entitlements-pro-design.md` - Pro tier resolution, pricing page
- **Team Design**: `muckrock/entitlements-team-design.md` - Shared credit pools, seats
- **Webhooks**: `muckrock/webhooks.md` - Webhook payloads, processing flow

## Updating Documentation

When making code changes:

1. **New feature**: Create doc in `features/`
2. **API change**: Update `architecture/fastapi-endpoints.md`
3. **Schema change**: Update `oss/supabase-schema.md`
4. **Adapter change**: Update `oss/adapter-pattern.md`
5. **Edge Function change**: Update `oss/edge-functions.md`
6. **Billing change**: Update `muckrock/plans-and-entitlements.md`
7. **New integration**: Document within relevant feature doc in `features/`
