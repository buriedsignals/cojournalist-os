# Information units & entities

Atomic facts extracted from scout runs + the canonical-entity graph that links them. This doc covers `information_units`, `entities`, `unit_entities`, `reflections`, their semantic search and entity-merge RPCs.

## Tables

### `information_units`

One row per atomic fact extracted from a scout run, ingest, or manual edit.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | |
| `scout_id` | UUID → `scouts(id)` ON DELETE CASCADE | |
| `scout_type` | TEXT | `web`/`pulse`/`social`/`civic` |
| `project_id` | UUID → `projects(id)` | Backfilled to default Inbox project (00013) |
| `raw_capture_id` | UUID → `raw_captures(id)` | Provenance for verification |
| `statement` | TEXT NOT NULL | The fact itself |
| `type` | TEXT CHECK IN ('fact','event','entity_update') | |
| `entities` | TEXT[] | Mention list (canonical resolution happens via `unit_entities`) |
| `context_excerpt` | TEXT | Supporting snippet from source |
| `embedding` | `vector(1536)` | Gemini embedding of `statement` |
| `embedding_model` | TEXT | Version tag |
| `source_url` | TEXT | |
| `source_domain` | TEXT | |
| `source_title` | TEXT | |
| `source_type` | TEXT CHECK IN ('scout','manual_ingest','agent_ingest') DEFAULT 'scout' | |
| `event_date` | DATE | Legacy field |
| `occurred_at` | TIMESTAMPTZ | When the event happened (if known) |
| `extracted_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `country`, `state`, `city`, `topic`, `dataset_id` | TEXT | Denormalised filter fields |
| `used_in_article` | BOOLEAN DEFAULT FALSE | Flipped when exported |
| `verified` | BOOLEAN DEFAULT FALSE | Manual verification flag |
| `verification_notes` | TEXT | |
| `verified_by` | UUID → `auth.users(id)` | |
| `verified_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ DEFAULT (NOW() + 90d) | TTL |

Indexes: HNSW `idx_unit_embedding(embedding)` vector_cosine_ops, `idx_units_project(project_id, extracted_at DESC)`, partial `idx_units_unused(user_id, used_in_article, extracted_at DESC) WHERE used_in_article=FALSE`.

### `entities` (00008)

Canonical entity records (people, orgs, places, policies, events, documents).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | Per-user graph — no global dedup |
| `canonical_name` | TEXT NOT NULL | UNIQUE (user_id, name, type) |
| `type` | TEXT CHECK IN ('person','org','place','policy','event','document','other') | |
| `aliases` | TEXT[] | Alternative spellings |
| `embedding` | `vector(1536)` | Embedding of `canonical_name` (and maybe aliases) |
| `embedding_model` | TEXT | |
| `mention_count` | INT DEFAULT 0 | Materialised count from `unit_entities` |
| `first_seen_at`, `last_seen_at` | TIMESTAMPTZ | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

Indexes: trigram `idx_entities_canonical_trgm(canonical_name) USING GIN gin_trgm_ops`, HNSW `idx_entities_embedding(embedding)`, unique index on `(user_id, canonical_name, type)`.

### `unit_entities` (00008) — junction

Maps units to entities. **`entity_id` is nullable** for unresolved mentions (NER found a candidate, canonical resolution hasn't matched yet).

| Column | Type | Notes |
|---|---|---|
| `unit_id` | UUID → `information_units(id)` ON DELETE CASCADE | |
| `entity_id` | UUID → `entities(id)` ON DELETE CASCADE | **nullable** |
| `mention_text` | TEXT | As it appeared in the source |
| `confidence` | REAL CHECK 0–1 | |
| `resolved_at` | TIMESTAMPTZ | NULL while unresolved |
| PRIMARY KEY `(unit_id, mention_text)` | | One row per mention in a unit |

Partial index `idx_ue_unresolved(user_id) WHERE entity_id IS NULL` surfaces the backlog.

### `reflections` (00008)

Agent-synthesised summaries over a scope (project + time range). Think: "What changed in Zurich housing policy this month?"

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | |
| `project_id` | UUID → `projects(id)` | |
| `scope_description` | TEXT | Human-readable frame |
| `content` | TEXT | The reflection itself |
| `time_range_start/_end` | TIMESTAMPTZ | |
| `generated_by` | TEXT | `agent` / `user` |
| `source_unit_ids` | UUID[] | Which units informed it |
| `source_entity_ids` | UUID[] | Which entities it's about |
| `embedding` | `vector(1536)` | For semantic lookup |
| `metadata` | JSONB | Model used, prompt version, etc. |
| `created_at` | TIMESTAMPTZ | |

Index: HNSW on `embedding`.

## RPCs

### `semantic_search_units(p_embedding vector(1536), p_user_id UUID, p_project_id UUID DEFAULT NULL, p_limit INT DEFAULT 20) RETURNS TABLE(...)`

Cosine-similarity search over `information_units`. Scoped to the caller's rows via the `p_user_id` parameter (SECURITY DEFINER bypasses RLS, so ownership is enforced by the RPC body — callers must pass `auth.uid()`).

Returns: `id, statement, type, source_url, source_title, occurred_at, extracted_at, similarity_score`. Ordered by similarity DESC.

### `semantic_search_reflections(p_embedding, p_user_id, p_project_id?, p_limit?)`

Same shape, targets `reflections`.

### `merge_entities(p_user_id UUID, p_keep_id UUID, p_merge_ids UUID[]) RETURNS VOID`

Merges duplicate entities into a keeper.

1. Verify `p_keep_id` + every `p_merge_ids` belong to `p_user_id` — raises if not.
2. Union `aliases` arrays into keeper.
3. Update `unit_entities.entity_id` from merged → keeper, **handling collisions** via ON CONFLICT (skips rows that would duplicate `(unit_id, mention_text)`).
4. Delete the merged entities.
5. Recompute `mention_count` for keeper from `unit_entities`.

### `check_unit_dedup(p_embedding vector(1536), p_scout_id UUID, p_threshold REAL DEFAULT 0.85, p_days INT DEFAULT 90) RETURNS BOOLEAN`

Returns TRUE if any `execution_records` row under the same scout within `p_days` has cosine ≥ `p_threshold`. Used by `scout-*-execute` before inserting a new unit.

## RLS

Core policies in 00004 + 00011:

| Table | Policy | Rule |
|---|---|---|
| `information_units` | `units_read` (SELECT) | `auth.uid() = user_id OR project shared via project_members` |
| `information_units` | `units_insert/update/delete` | `auth.uid() = user_id` |
| `entities` | `ent_user` | `auth.uid() = user_id` (ALL) |
| `unit_entities` | `ue_user` | `auth.uid() = user_id` (ALL) |
| `reflections` | `refl_read` (SELECT) | owner OR project shared |
| `reflections` | `refl_write/update/delete` | owner only |

Service-role (via Edge Functions) bypasses RLS.

## Cron

- `cleanup-information-units` (`10 3 * * *`) → `cleanup_information_units()` prunes `expires_at < NOW()` (batch 10k).

Entities, unit_entities, and reflections have no TTL — they're the durable knowledge graph.

## Edge Functions

### `units`
CRUD over `information_units`. Handles listing, filtering (project/topic/location/date range), single fetch. Enforces RLS via the user-scoped client.

### `units-search`
Semantic search entrypoint. Takes a text query, embeds via Gemini, calls `semantic_search_units` RPC.

### `entities`
CRUD over `entities`. The merge endpoint wraps `merge_entities` RPC.

### `reflections`
CRUD + search over `reflections`. Wraps `semantic_search_reflections`.

### `ingest`
User-driven ingest (text/url/pdf). Fetches content (firecrawl or direct), stores in `raw_captures`, extracts via Gemini (same EXTRACTION_SCHEMA as scout-web-execute), inserts units with `source_type='manual_ingest'`, runs embedding, resolves NER candidates into `unit_entities` (entity_id=NULL until canonicalised).

### `export-claude`
Returns a markdown dump of verified units in a project — for pulling into Claude/Claude Code as context. Authed via API key (not JWT) for headless use.

## Extraction pipeline

```
Scout run → raw_captures (source of truth)
          → geminiExtract(EXTRACTION_SCHEMA, content) → [{statement, type, context_excerpt, occurred_at}, ...]
          → geminiEmbed(statement) → vector(1536)
          → check_unit_dedup(embedding, scout_id)   # skip if ≥ 0.85 cosine
          → information_units INSERT
          → NER on statement → candidates
          → unit_entities INSERT (entity_id = NULL if no canonical match yet)
          → canonical resolution worker (offline) → attaches entity_id
```

`execution_records` holds a parallel card-sized summary for the UI — separate from `information_units` which are atomic facts.

## Invariants

1. **Entity identity is per-user.** No shared canonical graph across users. Merging Marc1's "UBS" with Marc2's "UBS" would be wrong — they might be talking about different things.
2. **`unit_entities.entity_id` can be NULL.** Unresolved mentions stay in the graph so a later canonicalisation pass can attach them; don't filter them out.
3. **`information_units.expires_at` is 90 days by default.** Renewal requires user action (verification or export). Entities and reflections do not expire.
4. **Dedup is per-scout, not global.** Different scouts covering the same topic will each get their own units — intentional, because dedup thresholds collapse perspective.
5. **Semantic search RPCs require `p_user_id`.** SECURITY DEFINER bypasses RLS, so the callsite must pass `auth.uid()` explicitly — otherwise it's a data leak.

## Operations

### Rebuild `mention_count` for an entity

```sql
UPDATE entities SET mention_count = (SELECT COUNT(*) FROM unit_entities WHERE entity_id = entities.id)
 WHERE id = '<entity_uuid>';
```

### Find unresolved mentions for a user

```sql
SELECT ue.mention_text, COUNT(*) AS occurrences
  FROM unit_entities ue
  JOIN information_units u ON u.id = ue.unit_id
 WHERE u.user_id = '<uuid>' AND ue.entity_id IS NULL
 GROUP BY ue.mention_text
 ORDER BY occurrences DESC
 LIMIT 50;
```

### Merge two entities

```sql
SELECT merge_entities(
  '<user_uuid>',
  '<keep_entity_uuid>',
  ARRAY['<merge_entity_uuid_1>', '<merge_entity_uuid_2>']::UUID[]
);
```

## See also

- `docs/supabase/scouts-runs.md` — how units get created
- `docs/supabase/projects-ingest.md` — manual ingest + project scoping
- `docs/features/feed.md` — UI feed view over units
- `supabase/migrations/00008_phase1_tables.sql` — tables
- `supabase/migrations/00016_semantic_search_rpc.sql`, `00017_merge_entities_rpc.sql`, `00018_reflection_search_rpc.sql`, `00019_scout_rpcs.sql`
