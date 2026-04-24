# Spec: Gemini Embedding V2 task-prefix migration

## Problem

Both the Python backend and TypeScript Edge Functions send `taskType` as a JSON field to the `gemini-embedding-2-preview` embedding API. **V2 silently ignores `taskType`** — confirmed by live API test: results with `taskType` are bit-for-bit identical to results without it.

V2's task-optimization mechanism is text prefixes prepended to the input, not the `taskType` field.

## Why this matters

Live API tests (2026-04-23):

| Scenario | Current (no-task, effective) | V2 prefix |
|---|---|---|
| EN retrieval discrimination | delta 0.4003 | delta 0.3323 |
| EN dedup discrimination | delta 0.3497 | delta 0.2225 |
| Cross-language EN query → NO doc | 0.7847 | **0.8604** |
| Dedup threshold (0.85) safe? | ✓ | ✓ |

V2 prefix improves cross-language retrieval by +0.076. This matters for a multilingual app where users search in English for content scraped in Norwegian/German/etc. Within-language discrimination drops slightly but all thresholds remain safe.

**Mixed-mode risk:** after deploy (before backfill), new V2-prefixed embeddings vs old unprefixed embeddings score ~0.81 cosine — below the 0.85 dedup threshold. This means duplicate email notifications will fire for active scouts until backfill completes. The deploy sequence below controls this.

---

## Prefix reference

| `task_type` / `taskType` | V2 text prefix |
|---|---|
| `SEMANTIC_SIMILARITY` | `task: sentence similarity \| query: ` |
| `RETRIEVAL_QUERY` | `task: search result \| query: ` |
| `RETRIEVAL_DOCUMENT` | `title: none \| text: ` |
| `CLASSIFICATION` | `task: classification \| query: ` |
| `CLUSTERING` | `task: clustering \| query: ` |
| `QUESTION_ANSWERING` | `task: question answering \| query: ` |
| `FACT_VERIFICATION` | `task: fact checking \| query: ` |
| `CODE_RETRIEVAL_QUERY` | `task: code retrieval \| query: ` |

Query and document must use matching prefixes for similarity to be meaningful.

---

## Code changes

### 1. `backend/app/services/embedding_utils.py`

Add `_apply_task_prefix()` before `generate_embedding`:

```python
def _apply_task_prefix(text: str, task_type: str) -> str:
    prefixes = {
        "SEMANTIC_SIMILARITY": "task: sentence similarity | query: ",
        "RETRIEVAL_QUERY": "task: search result | query: ",
        "RETRIEVAL_DOCUMENT": "title: none | text: ",
        "CLASSIFICATION": "task: classification | query: ",
        "CLUSTERING": "task: clustering | query: ",
        "QUESTION_ANSWERING": "task: question answering | query: ",
        "FACT_VERIFICATION": "task: fact checking | query: ",
        "CODE_RETRIEVAL_QUERY": "task: code retrieval | query: ",
    }
    prefix = prefixes.get(task_type, "task: sentence similarity | query: ")
    return f"{prefix}{text}"
```

In `generate_embedding`, `generate_embedding_multimodal`, `generate_embeddings_batch`:
- Apply `_apply_task_prefix(text, task_type)` to input text(s)
- Remove `"taskType"` from the JSON body
- Keep `task_type` parameter on function signatures (callers unchanged)

### 2. `backend/tests/unit/shared/test_embedding_utils.py`

Update `test_passes_task_type_in_request` (line ~149) and grep for any other assertions on `taskType` or exact `content.parts[0].text` values:

```python
# was: assert payload["taskType"] == "RETRIEVAL_QUERY"
assert payload["content"]["parts"][0]["text"].startswith("task: search result | query: ")
assert "taskType" not in payload
```

### 3. `supabase/functions/_shared/gemini.ts`

Add `applyTaskPrefix()`:

```typescript
function applyTaskPrefix(text: string, taskType: GeminiTaskType): string {
  const prefixes: Record<GeminiTaskType, string> = {
    SEMANTIC_SIMILARITY: "task: sentence similarity | query: ",
    RETRIEVAL_QUERY: "task: search result | query: ",
    RETRIEVAL_DOCUMENT: "title: none | text: ",
    CLASSIFICATION: "task: classification | query: ",
    CLUSTERING: "task: clustering | query: ",
  };
  return (prefixes[taskType] ?? "task: sentence similarity | query: ") + text;
}
```

In `geminiEmbed`: apply prefix, remove `taskType` from body. Keep `taskType` parameter.

### 4. Bundled EF files — verify before merging

`supabase/functions/scouts/_bundled.ts` and `supabase/functions/units/_bundled.ts` may contain inlined copies of `geminiEmbed` with their own `taskType` fields. Before merging:

```bash
grep -n "taskType" supabase/functions/scouts/_bundled.ts
grep -n "taskType" supabase/functions/units/_bundled.ts
```

If hits found: regenerate bundles from source, or patch the inlined copies directly.

### No caller changes needed

The prefix is applied transparently inside the wrapper functions. These call sites require no edits:
- `execution_deduplication.py` → `generate_embedding(summary_text, "SEMANTIC_SIMILARITY")`
- `feed_search_service.py` → `generate_embedding(query, "RETRIEVAL_QUERY")`
- `news_utils.py` ×2 → `generate_embeddings_batch(texts, "SEMANTIC_SIMILARITY")`
- `scout-web-execute/index.ts` → `geminiEmbed(u.statement, "RETRIEVAL_DOCUMENT")`

---

## Tables to backfill

All four tables with `vector(1536)` embedding columns must be re-indexed:

| Table | task_type to use | Notes |
|---|---|---|
| `information_units` | `RETRIEVAL_DOCUMENT` | prefix: `title: none \| text: {statement}` |
| `execution_records` | `SEMANTIC_SIMILARITY` | summary dedup embeddings |
| `entities` | `SEMANTIC_SIMILARITY` | entity canonical matching |
| `reflections` | `SEMANTIC_SIMILARITY` | reflection semantic search |

---

## Deploy sequence

### 1. Pause pg_cron scout schedules

```sql
-- saves cron expressions in scouts.schedule_cron_expr
SELECT cron.unschedule(jobname) FROM cron.job WHERE jobname LIKE 'scout-%';
```

### 2. Merge PR → Render auto-deploys backend, deploy Edge Functions

```bash
# After merge to main, Render deploys automatically.
# Deploy EFs:
supabase functions deploy
```

### 3. Backfill all four tables

Use `batchEmbedContents` (up to 100 texts per call) for efficiency. Run as a one-off script against production Supabase with service role key.

```python
# Pseudocode — run from backend/ with venv activated
from app.services.embedding_utils import generate_embeddings_batch
import asyncpg, asyncio

async def backfill():
    conn = await asyncpg.connect(DATABASE_URL)

    # information_units
    rows = await conn.fetch("SELECT id, statement FROM information_units WHERE embedding IS NOT NULL")
    texts = [f"title: none | text: {r['statement']}" for r in rows]
    # batch via generate_embeddings_batch in chunks of 100
    # UPDATE information_units SET embedding=$1, embedding_model='gemini-embedding-2-preview-v2prefix' WHERE id=$2

    # execution_records — statement column may be summary_text, check schema
    # entities, reflections — same pattern with SEMANTIC_SIMILARITY prefix

asyncio.run(backfill())
```

### 4. Rebuild HNSW indexes (no downtime)

```sql
REINDEX INDEX CONCURRENTLY idx_unit_embedding;
-- repeat for entities, execution_records, reflections
-- index names in supabase/migrations/00003_indexes.sql and 00010_phase1_indexes.sql
```

### 5. Re-enable pg_cron schedules

```sql
SELECT schedule_scout(id, schedule_cron_expr)
FROM scouts
WHERE is_active = true AND schedule_cron_expr IS NOT NULL;
```

---

## Verification

```bash
# Tests must pass before merging
cd backend && python3 -m pytest tests/unit/shared/test_embedding_utils.py -v
cd backend && python3 -m pytest tests/unit/ -v

# Confirm taskType stripped from all sources
grep -rn '"taskType"' backend/app/services/embedding_utils.py supabase/functions/_shared/gemini.ts
# → no output expected

# Post-deploy: trigger one manual scout run, verify no duplicate notification fires
```

---

## Rollback

Revert `embedding_utils.py` and `gemini.ts` to include `taskType` in the JSON body (API accepts it silently, just ignores it). Run backfill again without prefixes. Rebuild HNSW. Re-enable schedules. No schema changes involved.
