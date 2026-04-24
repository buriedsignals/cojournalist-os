# Gemini Embedding 2 task-prefix migration

Status: implemented in this branch.

## What changed

- Gemini embedding requests no longer send `taskType` in the JSON body.
- Both active embedding helpers now rewrite the text payload using Gemini Embedding 2 task-prefix formatting:
  - Python: `backend/app/services/embedding_utils.py`
  - Supabase Edge Functions: `supabase/functions/_shared/gemini.ts`
- Retrieval-document embeddings now support titles explicitly.
- Canonical unit writes still flow through `upsertCanonicalUnit(...)`; only the embedding request shape changed.
- New writes now tag stored vectors with `gemini-embedding-2-preview-task-prefix-v1`.
- `execution_records` now has an `embedding_model` column so execution dedup vectors can be versioned alongside `information_units` and `reflections`.

## Prefix mapping

| Intent | Prefix |
|---|---|
| `RETRIEVAL_QUERY` | `task: search result \| query: {text}` |
| `RETRIEVAL_DOCUMENT` | `title: {title_or_none} \| text: {text}` |
| `SEMANTIC_SIMILARITY` | `task: sentence similarity \| query: {text}` |
| `CLASSIFICATION` | `task: classification \| query: {text}` |
| `CLUSTERING` | `task: clustering \| query: {text}` |

Retrieval remains asymmetric: queries and documents intentionally use different prefixes.

## Updated call sites

### Supabase Edge Functions

- `units` semantic search query embeddings
- `reflections` write + search embeddings
- `scout-web-execute` canonical unit writes
- `scout-beat-execute` canonical unit writes
- `ingest` canonical unit writes
- `apify-callback` canonical unit writes
- `civic-extract-worker` promise embeddings
- `_shared/beat_pipeline.ts` semantic dedupe embeddings

### Residual Python backend

- `feed_search_service.py`
- `execution_deduplication.py`
- `news_utils.py`
- `atomic_unit_service.py`

## Stored model tag

This migration introduces the stored model tag:

```text
gemini-embedding-2-preview-task-prefix-v1
```

New embeddings written by this branch should use that value for:

- `information_units.embedding_model`
- `reflections.embedding_model`
- `execution_records.embedding_model`

## Backfill

Use the one-off script:

```bash
deno run --allow-net --allow-env --allow-read --allow-write scripts/backfill-gemini-embedding-v2.ts
```

Required env vars:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`

Optional env vars:

- `BACKFILL_BATCH_SIZE` — default `100`
- `BACKFILL_TABLES` — comma-separated subset of `information_units,reflections,execution_records`
- `BACKFILL_STATE_PATH` — checkpoint file path
- `RESET_BACKFILL_STATE=true` — ignore any prior checkpoint

Behavior:

- paginated and resumable
- rewrites only rows whose `embedding_model` is not already `gemini-embedding-2-preview-task-prefix-v1`
- updates:
  - `information_units` from `statement` + `source_title`
  - `reflections` from `content`
  - `execution_records` from `summary_text`

## Verification completed in this branch

- Python syntax compilation for the changed Python files
- Deno unit tests for:
  - `_shared/gemini_test.ts`
  - `_shared/unit_dedup_test.ts`
- `deno check` for changed Supabase files and the backfill script

## Verification not completed locally

- Python async pytest suites: local environment is missing the async pytest plugin
- Supabase function integration tests: local environment is missing required `SUPABASE_*` test env vars

## Rollback

- Code rollback: restore the old request shape in the shared embedding helpers.
- Data rollback: run a second re-embed pass for any rows already rewritten to the new prefix format.

Because this migration rewrites stored vectors, code rollback alone does not fully revert the system state.
