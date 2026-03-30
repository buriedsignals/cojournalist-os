# Scrape Service

Web content extraction via Firecrawl with format options.

## Overview

The Scrape service provides one-time web content extraction from URLs. Uses Firecrawl for reliable scraping with multiple output formats. No scheduling or monitoring - designed for immediate extraction needs.

## Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCRAPE EXECUTION                              │
│                                                                 │
│  Trigger: UI → POST /api/extract/start (async)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Credit Validation                                      │
│  ├─ POST /api/extract/validate (pre-check)                      │
│  └─ Verify user has sufficient credits                          │
│           │                                                     │
│           ▼                                                     │
│  Step 2: URL Extraction                                         │
│  ├─ Call Firecrawl scrape API                                   │
│  ├─ Extract content in requested format                         │
│  └─ Parse structured data if schema provided                    │
│           │                                                     │
│           ▼                                                     │
│  Step 3: Response Formatting                                    │
│  ├─ Return content in requested format                          │
│  └─ Optionally convert to CSV for download                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `data_extractor.py` | `backend/app/routers/` | `/api/extract/*` endpoints |
| `data_extractor.py` | `backend/app/workflows/` | Core extraction logic |
| `firecrawl_client.py` | `backend/app/workflows/` | Firecrawl API client |

## Format Options

| Format | Description | Use Case |
|--------|-------------|----------|
| `markdown` | Clean markdown text | Reading, analysis |
| `html` | Raw HTML | Preservation |
| `structured` | JSON with schema | Data extraction |

## Endpoints

### POST /api/extract/validate
Pre-validate credits before extraction. Returns credit information or 402 if insufficient.

### POST /api/extract/start
Start an async data extraction job. Returns `job_id` immediately, then polls Firecrawl in the background.

**Request:**
```json
{
  "url": "https://example.com/page",
  "target": "product listings with prices"
}
```

**Response:**
```json
{
  "job_id": "abc123",
  "status": "running"
}
```

### GET /api/extract/status/{job_id}
Poll for async extraction job status. Returns CSV data on completion.

**Response (running):**
```json
{
  "job_id": "abc123",
  "status": "running"
}
```

**Response (completed):**
```json
{
  "job_id": "abc123",
  "status": "completed",
  "result": {
    "csv_content": "col1,col2\nval1,val2",
    "filename": "extract_firecrawl_abc123.csv"
  }
}
```

### POST /api/data/extract
Synchronous extraction endpoint. Waits for completion and returns CSV directly.

### GET /api/data/extract/stream
SSE streaming extraction with real-time progress updates. Uses query parameter auth (`token`) for SSE compatibility.

## Credit Cost

| Operation | Credits |
|-----------|---------|
| Single page extraction | 1 |

## Error Handling

| Error | Response |
|-------|----------|
| Invalid URL | 400 Bad Request |
| Insufficient credits | 402 Payment Required |
| Firecrawl error | 500 with error details |
| Timeout | 504 Gateway Timeout |

## Related Docs

- `features/web-scouts.md` - For scheduled URL monitoring
