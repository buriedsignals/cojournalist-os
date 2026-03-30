# Feed & Export Service

Export generation from information units with source citation.

## Overview

The Feed panel displays information units from the knowledge base. The Export service generates structured exports from selected units using GPT-4o, synthesizing facts with proper source citations.

## Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXPORT EXECUTION                               │
│                                                                 │
│  Trigger: UI → POST /api/export/generate                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Unit Retrieval                                         │
│  ├─ User selects units from knowledge base                      │
│  └─ Units include: statement, source_title, source_url          │
│           │                                                     │
│           ▼                                                     │
│  Step 2: Credit Validation                                      │
│  └─ Verify user has credits for feed_export operation           │
│           │                                                     │
│           ▼                                                     │
│  Step 3: Export Generation (GPT-4o)                             │
│  ├─ Synthesize units into coherent narrative                    │
│  ├─ Generate title and headline                                 │
│  ├─ Create sections with proper flow                            │
│  └─ Identify information gaps                                   │
│           │                                                     │
│           ▼                                                     │
│  Step 4: Source Compilation                                     │
│  ├─ Compile unique sources from units                           │
│  └─ Generate bullet points with citations                       │
│           │                                                     │
│           ▼                                                     │
│  Step 5: Response                                               │
│  └─ Return structured export with all components                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `export.py` | `backend/app/routers/` | `/api/export/*` endpoints |
| `export_generator.py` | `backend/app/services/` | Export generation + AI auto-select logic |
| `feed_search_service.py` | `backend/app/services/` | Unit retrieval and search |
| `units.py` | `backend/app/routers/` | Unit management endpoints |
| `FeedView.svelte` | `frontend/src/lib/components/feed/` | Feed panel, filter bar, AI select orchestration |
| `AISelectPanel.svelte` | `frontend/src/lib/components/feed/` | AI Select quick-button dropdown |

## Unit Management

### Retrieving Units

Units can be retrieved by:
- **Location**: `GET /api/units?country=CH&city=Zurich`
- **Topic**: `GET /api/units/by-topic?topic=climate`
- **Semantic search**: `GET /api/units/search?query=renewable energy`

### Unit Structure
```json
{
  "unit_id": "abc123",
  "statement": "Zurich approved a $50M climate fund",
  "unit_type": "fact",
  "source_title": "Zurich Times",
  "source_url": "https://...",
  "entities": ["Zurich", "climate fund"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Endpoint

### POST /api/export/generate

**Rate limit:** 10 requests/minute

**Request:**
```json
{
  "units": [
    {
      "statement": "Zurich approved a $50M climate fund",
      "source_title": "Zurich Times",
      "source_url": "https://..."
    }
  ],
  "location_name": "Zurich, Switzerland",
  "language": "en"
}
```

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `units` | array | Yes | - | Information units to synthesize |
| `location_name` | string | Yes | - | Location context for the export |
| `language` | string | No | `"en"` | ISO 639-1 language code for export generation |

**Note:** The `language` parameter controls the output language of the generated export. The frontend passes the user's `preferred_language` setting.

**Response:**
```json
{
  "title": "Zurich Takes Bold Climate Action",
  "headline": "City approves major climate initiative",
  "sections": [
    {
      "heading": "Overview",
      "content": "The city of Zurich has approved..."
    }
  ],
  "gaps": ["Timeline for fund deployment unclear"],
  "bullet_points": [
    "• $50M approved for climate initiatives [1]"
  ],
  "sources": [
    {"title": "Zurich Times", "url": "https://..."}
  ]
}
```

## AI Select

AI-powered unit selection via quick-action buttons. Users click a button to populate a prompt, review it, then run the selection.

### Quick Buttons

| Button | Prompt | Requires |
|--------|--------|----------|
| **Location** | "Select the most newsworthy and locally relevant information." | Active location filter |
| **Topic** | "Select the most relevant and important information about this topic." | Active topic filter |
| **Date** | "Select recent and upcoming events from the last 2 days and next 2 days." | Always available |

### Behaviour

1. Clicking a button populates a prompt preview in the dropdown
2. Active location/topic filters are shown as pills above the prompt
3. Location and topic are passed as separate API parameters (not embedded in prompt text)
4. Clicking an unavailable button (e.g. Location with no location filter) shows a tooltip and clears any active prompt
5. User can edit the prompt before clicking "Run Selection"

### Date Pre-Filter

When the Date button is used, the frontend pre-filters units before sending to the LLM:
- Units with `date_value` outside the ±2 day window are **excluded**
- Units without `date_value` (null) **pass through** unfiltered

### Endpoint: POST /api/export/auto-select

**Rate limit:** 10 requests/minute

**Request:**
```json
{
  "units": [
    {
      "unit_id": "abc123",
      "statement": "...",
      "entities": [],
      "source_title": "...",
      "created_at": "2026-03-01T10:00:00Z",
      "date_value": "2026-03-02",
      "unit_type": "fact",
      "scout_type": "pulse"
    }
  ],
  "prompt": "Select the most newsworthy...",
  "location": "Spokane, WA, US",
  "topic": "AI regulation"
}
```

**Response:**
```json
{
  "selected_unit_ids": ["abc123", "def456"],
  "selection_summary": "Selected 2 units about local AI regulation developments"
}
```

**Credit cost:** 1 credit per selection run.

## Filter Bar

The feed filter bar shows location and topic filters directly (no scope dropdown). Filters are always visible:

- **Location** — Filter units by geographic location
- **Topic** — Filter units by topic
- **Scout** — Filter by scout name (shown with divider when multiple scouts exist)

## Marking Units as Used

After generating an export, units can be marked as used:

### PATCH /api/units/mark-used
```json
{
  "unit_ids": ["abc123", "def456"]
}
```

This extends the unit's TTL and tracks usage.

## Credit Cost

| Operation | Credits |
|-----------|---------|
| Generate export | 1 |

## Limitations

- Maximum 20 units per export
- Units must include statement, source_title, source_url
- Location context improves generation quality

## Export

After generating an export, users can download via Markdown or send to CMS API. See `features/export.md` for full details.

## Related Docs

- `features/pulse.md` - How units are created
- `architecture/records-and-deduplication.md` - Unit storage schema
