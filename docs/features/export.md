# Export Service

Draft export to Markdown files and CMS endpoints.

## Overview

After generating an export in the Feed panel, users can export it via two channels:

1. **Markdown** — Download as a `.md` file (client-side, no backend call)
2. **CMS API** — Send to a user-configured CMS endpoint (proxied through backend)

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXPORT FLOW                                │
│                                                                 │
│  Feed panel generates export                                    │
│           │                                                     │
│           ▼                                                     │
│  User clicks Export dropdown                                    │
│  ├─ "Export as Markdown"  → client-side .md file download       │
│  └─ "Send to CMS"        → POST /api/export/to-cms     │
│                                       │                         │
│                                       ▼                         │
│                              Backend proxy                      │
│                              ├─ Fetch CMS config from DynamoDB   │
│                              ├─ Validate URL (SSRF)             │
│                              └─ POST draft to CMS endpoint      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `export.py` | `backend/app/routers/` | `/api/export/to-cms` endpoint |
| `user.py` | `backend/app/routers/` | CMS config in user preferences |
| `ExportSlideOver.svelte` | `frontend/src/lib/components/feed/` | Export slide-over UI |
| `AISelectPanel.svelte` | `frontend/src/lib/components/feed/` | AI Select quick-button dropdown |
| `FeedView.svelte` | `frontend/src/lib/components/feed/` | Feed orchestration, AI select, export logic |
| `PreferencesModal.svelte` | `frontend/src/lib/components/modals/` | CMS endpoint + token config |

## Markdown Export

Client-side only. The frontend builds a `.md` file from the draft object and triggers a browser download. No backend call, no credits charged.

## CMS Export

### Configuration

Users configure CMS export in the Preferences modal (Settings):

1. **API Endpoint** (`cms_api_url`) — HTTPS URL where drafts are POSTed. Stored in DynamoDB user preferences.
2. **Bearer Token** (`cms_api_token`) — Optional auth token. Stored in DynamoDB user preferences (never exposed to frontend). Frontend only sees `has_cms_token: boolean`.

### Endpoint

#### POST /api/export/to-cms

**Rate limit:** 10 requests/minute

**Request:**
```json
{
  "draft": {
    "title": "Article Title",
    "headline": "A headline",
    "sections": [{"heading": "Overview", "content": "..."}],
    "gaps": [],
    "bullet_points": [],
    "sources": [{"title": "Source", "url": "https://..."}]
  },
  "units": [
    {
      "statement": "A key fact",
      "source_title": "Source Name",
      "source_url": "https://..."
    }
  ]
}
```

**CMS receives:**
```json
{
  "draft": { ... },
  "units": [ ... ],
  "exported_at": "2026-02-19T10:00:00+00:00"
}
```

**Error responses:**

| Status | Detail | When |
|--------|--------|------|
| `400` | `No CMS API endpoint configured` | User has no `cms_api_url` in metadata |
| `502` | `CMS returned {status}` | CMS endpoint returned HTTP 4xx/5xx |
| `504` | `CMS endpoint timed out` | CMS did not respond within 30 seconds |

### Security

- CMS URL must use HTTPS
- Private/internal IP addresses are blocked (SSRF protection)
- Bearer token stored in DynamoDB user preferences, never returned to frontend
- Export proxied through backend to avoid exposing CMS token to browser

## Related Docs

- `features/feed.md` - Feed panel and export generation from information units
- `architecture/fastapi-endpoints.md` - All REST endpoints
- Credit costs: see `backend/app/utils/credits.py` (export is free, draft generation costs 1 credit)
