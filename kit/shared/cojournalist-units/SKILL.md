---
name: cojournalist-units
description: Query verified information units from coJournalist v2 by project, time range, verification status, or semantic search. Use whenever the user asks "what did X say about Y", "show me units/facts/statements", or wants to pull structured knowledge out of their coJournalist workspace.
---

# coJournalist — Query Information Units

coJournalist v2 stores every extracted fact as an **information unit** — a single verifiable
statement with provenance (source URL, timestamp, extraction confidence, verification status).
This skill documents the three endpoints used to read units back out.

Ingestion lives in the sibling `cojournalist-ingest` skill. Ongoing monitoring lives in
`cojournalist-scouts`.

## When to use

Trigger on any of:
- "What did <entity> say about <topic>?"
- "Show me verified facts from my <project> project"
- "Give me all units tagged <criteria> since <date>"
- "Explain / summarize unit <id>"
- "Semantic search across my coJournalist knowledge base"

## Environment

Set these once per shell (read from `~/.hermes/.env`):

```bash
export COJO_URL="${COJO_URL:-https://<project-ref>.functions.supabase.co}"
export COJO_AUTH="${COJO_AUTH:-$COJOURNALIST_TOKEN}"
```

`COJO_AUTH` is a Supabase user JWT (from the browser session) or a service-role key for
server-side work. Never log it.

## Tool calls

### 1. List units — `GET /functions/v1/units`

```bash
curl -sS "$COJO_URL/functions/v1/units?project_id=$PID&since=2026-03-01&verified=true&limit=50" \
  -H "Authorization: Bearer $COJO_AUTH"
```

Query params (all optional):
- `project_id` — scope to a single project
- `since` / `until` — ISO 8601 timestamps
- `verified` — `true` | `false` | omit for both
- `criteria` — substring match against the unit's tagged criteria
- `limit` — default 20, max 100
- `cursor` — opaque pagination token from previous response

Response:
```json
{
  "units": [
    {
      "id": "u_01J...",
      "project_id": "p_01J...",
      "statement": "Zurich city council committed CHF 200M to affordable housing by 2028.",
      "source_url": "https://...",
      "extracted_at": "2026-03-14T09:12:00Z",
      "verified": true,
      "criteria": ["housing", "budget"]
    }
  ],
  "next_cursor": null
}
```

### 2. Semantic search — `POST /functions/v1/units/search`

```bash
curl -sS -X POST "$COJO_URL/functions/v1/units/search" \
  -H "Authorization: Bearer $COJO_AUTH" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "housing affordability commitments", "project_id": "p_01J...", "limit": 10}'
```

Body:
- `query_text` (required) — natural-language query; embedded server-side
- `project_id` (optional) — scope to one project
- `limit` (optional, default 10, max 50)

Returns the same `units` shape as `/units`, ordered by cosine similarity.

### 3. Single unit — `GET /functions/v1/units/:id`

```bash
curl -sS "$COJO_URL/functions/v1/units/u_01J..." \
  -H "Authorization: Bearer $COJO_AUTH"
```

Returns the unit plus `raw_capture` (the source passage it was extracted from) and
`related_units` (nearest neighbours in the same project).

## Examples

### 1. "What did the Zurich council say about housing last month?"

```bash
# Semantic search scoped to the user's Zurich project, last 30 days.
curl -sS -X POST "$COJO_URL/functions/v1/units/search" \
  -H "Authorization: Bearer $COJO_AUTH" \
  -H "Content-Type: application/json" \
  -d "{\"query_text\": \"housing\", \"project_id\": \"$ZURICH_PID\", \"limit\": 20}" \
  | jq '.units[] | select(.extracted_at > "2026-03-17")'
```

Summarize the returned `statement` fields grouped by `source_url`.

### 2. "Give me all verified units from my Zurich project"

```bash
curl -sS "$COJO_URL/functions/v1/units?project_id=$ZURICH_PID&verified=true&limit=100" \
  -H "Authorization: Bearer $COJO_AUTH"
```

Paginate via `next_cursor` if >100. Render as a markdown list: `- [statement](source_url)`.

### 3. "Explain unit u_01J..."

```bash
curl -sS "$COJO_URL/functions/v1/units/u_01J..." \
  -H "Authorization: Bearer $COJO_AUTH"
```

Read `statement` + `raw_capture.text`, then summarise in one sentence citing the source URL.
Mention `verified` status and list `related_units` as follow-ups.

## Gotchas

- Unverified units can be hallucinated — always surface the `verified` field to the user.
- Timestamps are UTC. Convert for user-facing output.
- 401 means the JWT expired; re-auth via the frontend before retrying.
