---
name: cojournalist-ingest
description: Trigger a one-off ingestion of a URL or a block of raw text into coJournalist v2. Returns the extracted information units. Use when the user says "extract facts from this", "save this article to my project", or pastes a PDF/URL/blob asking for structured capture.
---

# coJournalist — One-off Ingestion

Push any URL or raw text into coJournalist v2's extraction pipeline and get back a list of
information units (verifiable statements with provenance). This is the **one-off** path — for
ongoing monitoring of a source, use the `cojournalist-scouts` skill instead.

Sibling skill `cojournalist-units` covers reading units back out.

## When to use

Trigger on any of:
- "Extract the promises / claims / facts from this PDF/URL"
- "Save this article to my <project>"
- "Pull the key points out of this transcript" (paste-in text)
- "What does this source say about <criteria>?"

**Do NOT use for:** "keep watching this page" / "alert me when X changes" — that's a Scout,
not an ingest. Redirect to `cojournalist-scouts`.

## Environment

```bash
export COJO_URL="${COJO_URL:-https://<project-ref>.functions.supabase.co}"
export COJO_AUTH="${COJO_AUTH:-$COJOURNALIST_TOKEN}"
```

`COJO_AUTH` is a Supabase user JWT. Never log it.

## Tool call

### `POST /functions/v1/ingest`

```bash
curl -sS -X POST "$COJO_URL/functions/v1/ingest" \
  -H "Authorization: Bearer $COJO_AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "url",
    "url": "https://stadt-zuerich.ch/council/minutes/2026-03-14.pdf",
    "title": "Zurich council minutes, 14 March 2026",
    "criteria": ["housing", "child care"],
    "project_id": "p_01J..."
  }'
```

Body fields:
- `kind` (required) — `"url"` or `"text"`
- `url` (required if `kind=url`) — https URL; Firecrawl fetches + parses (PDF/HTML both OK)
- `text` (required if `kind=text`) — raw text blob, max 200k chars
- `title` (optional) — human label shown in the UI; inferred from page `<title>` if omitted
- `criteria` (optional) — array of strings; guides the extractor and tags the units
- `project_id` (optional) — attaches units to a project; otherwise they land in "Inbox"

### Response

```json
{
  "ingest_id": "i_01J...",
  "raw_capture_id": "r_01J...",
  "units": [
    { "id": "u_01J...", "statement": "Council approved CHF 12M for 2026 child care expansion." },
    { "id": "u_01J...", "statement": "Three new daycare centres planned in Kreis 4 by Q3 2026." }
  ]
}
```

- `ingest_id` — the ingestion run record
- `raw_capture_id` — the stored source text/HTML (fetch via `/captures/:id` for full provenance)
- `units` — newly created units; IDs are stable and can be passed to `cojournalist-units`

Synchronous call; typical latency 3–20s depending on source length.

## Examples

### 1. "Here's a council PDF — extract the promises"

User pastes a URL like `https://stadt-zuerich.ch/.../minutes.pdf`.

```bash
curl -sS -X POST "$COJO_URL/functions/v1/ingest" \
  -H "Authorization: Bearer $COJO_AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "url",
    "url": "https://stadt-zuerich.ch/.../minutes.pdf",
    "criteria": ["promise", "commitment", "funding"],
    "project_id": "'"$ZURICH_PID"'"
  }'
```

Summarize the returned `units[].statement` as a numbered list; cite the ingest's
`raw_capture_id` so the user can open the source in the UI.

### 2. "I'm reading this article, save the key facts to my project"

User pastes article text into the chat.

```bash
curl -sS -X POST "$COJO_URL/functions/v1/ingest" \
  -H "Authorization: Bearer $COJO_AUTH" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "kind": "text",
  "text": $(jq -Rs . <<< "$ARTICLE_TEXT"),
  "title": "NZZ — Housing crisis feature, 2026-04-10",
  "project_id": "$ZURICH_PID"
}
JSON
```

Return the unit count + first 3 statements as a preview.

### 3. "Watch this story and flag anything about child care"

This is **not** an ingest — it's a Scout. Respond:

> That's a monitoring job, not a one-off capture. I'll hand off to `cojournalist-scouts` to
> set up a Beat Scout with criteria "child care" pointed at that source. Want me to proceed?

Then invoke the scouts skill. Do **not** call `/ingest` repeatedly to simulate monitoring.

## Gotchas

- Paywalled URLs return a `raw_capture` but zero `units` — surface this to the user; suggest
  pasting the text directly instead.
- Very short inputs (<100 chars) usually yield 0 units; the extractor needs context.
- Units land unverified by default. User verifies via the frontend; only then do they count
  as "verified" in the units skill.
- 429 means Firecrawl or Gemini rate limits hit — back off 30s and retry once.
