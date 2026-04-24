# Information units & entities

Canonical facts extracted from scout runs + the canonical-entity graph that links them. `information_units` is now the per-user canonical layer; `unit_occurrences` stores every scout/run/source hit that attached to that canonical fact. This doc covers `information_units`, `unit_occurrences`, `entities`, `unit_entities`, `reflections`, and the search / merge RPCs.

## Tables

### `information_units`

One canonical row per user-visible fact, promise, or entity update. Cross-run and cross-scout duplicates merge into the same row; provenance lives in `unit_occurrences`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | |
| `scout_id` | UUID → `scouts(id)` ON DELETE SET NULL | Canonical origin only; filtering happens via `unit_occurrences` |
| `scout_type` | TEXT | `web`/`beat`/`social`/`civic` |
| `project_id` | UUID → `projects(id)` | Backfilled to default Inbox project (00013) |
| `raw_capture_id` | UUID → `raw_captures(id)` | Provenance for verification |
| `statement` | TEXT NOT NULL | The fact itself |
| `type` | TEXT CHECK IN ('fact','event','entity_update','promise') | `promise` is the civic canonical type |
| `entities` | TEXT[] | Mention list (canonical resolution happens via `unit_entities`) |
| `context_excerpt` | TEXT | Supporting snippet from source |
| `embedding` | `vector(1536)` | Gemini embedding of `statement` |
| `embedding_model` | TEXT | Version tag |
| `source_url` | TEXT | |
| `source_domain` | TEXT | |
| `source_title` | TEXT | |
| `source_type` | TEXT CHECK IN ('scout','manual_ingest','agent_ingest','civic_promise') DEFAULT 'scout' | Canonical origin only |
| `event_date` | DATE | Legacy field |
| `occurred_at` | DATE | When the event happened (if known) |
| `extracted_at` | TIMESTAMPTZ DEFAULT NOW() | First-seen timestamp for the canonical row |
| `first_seen_at` | TIMESTAMPTZ | First time any occurrence created this canonical row |
| `last_seen_at` | TIMESTAMPTZ | Most recent occurrence timestamp |
| `occurrence_count` | INT DEFAULT 1 | Number of attached provenance rows |
| `source_count` | INT DEFAULT 1 | Distinct source signatures across occurrences |
| `country`, `state`, `city`, `topic`, `dataset_id` | TEXT | Denormalised filter fields |
| `used_in_article` | BOOLEAN DEFAULT FALSE | Flipped when exported |
| `verified` | BOOLEAN DEFAULT FALSE | Manual verification flag |
| `verification_notes` | TEXT | |
| `verified_by` | UUID → `auth.users(id)` | |
| `verified_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ DEFAULT (NOW() + 90d) | TTL |

Indexes: HNSW `idx_unit_embedding(embedding)` vector_cosine_ops, `idx_units_user_last_seen(user_id, last_seen_at DESC)`, plus the legacy inbox indexes.

### `unit_occurrences` (00038)

One row per scout/run/source hit that attached to a canonical unit.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `unit_id` | UUID → `information_units(id)` ON DELETE CASCADE | Canonical fact |
| `user_id` | UUID → `auth.users(id)` | |
| `project_id` | UUID → `projects(id)` ON DELETE SET NULL | Project membership is occurrence-scoped |
| `scout_id` | UUID → `scouts(id)` ON DELETE SET NULL | Scout membership is occurrence-scoped |
| `scout_run_id` | UUID → `scout_runs(id)` ON DELETE SET NULL | Run pointer survives run cleanup |
| `raw_capture_id` | UUID → `raw_captures(id)` ON DELETE SET NULL | Verification provenance |
| `scout_type` | TEXT | `web` / `beat` / `social` / `civic` |
| `source_kind` | TEXT CHECK IN ('scout','manual_ingest','agent_ingest','civic_promise') | |
| `source_url` / `normalized_source_url` | TEXT | Exact-match dedup keys |
| `source_title` / `source_domain` | TEXT | |
| `content_sha256` | TEXT | Exact-match dedup key |
| `statement_hash` | TEXT NOT NULL | Normalized statement SHA-256 |
| `occurred_at` | DATE | |
| `extracted_at` | TIMESTAMPTZ | When this occurrence landed |
| `metadata` | JSONB | Scout-specific context |

Hot indexes: `(scout_id, extracted_at DESC)`, `(project_id, unit_id)`, `(user_id, normalized_source_url)`, `(user_id, content_sha256)`, `(user_id, statement_hash)`.

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

### `semantic_search_units(p_embedding vector(1536), p_user_id UUID, p_project_id UUID DEFAULT NULL, p_limit INT DEFAULT 20, p_query_text TEXT DEFAULT NULL, p_rrf_k INT DEFAULT 50) RETURNS TABLE(...)`

Hybrid keyword + vector search over canonical `information_units`. `p_project_id` now scopes through `unit_occurrences`, not `information_units.project_id`, so a canonical row created by one scout still appears when another scout/project later attaches provenance to it.

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

### `upsert_canonical_unit(...) RETURNS TABLE(unit_id UUID, created_canonical BOOLEAN, merged_existing BOOLEAN, match_scope TEXT, occurrence_created BOOLEAN)`

Single authoritative write path for scout/web/beat/social/civic/manual-ingest writes. The function:

1. Acquires a per-user advisory lock keyed by normalized statement hash.
2. Checks same-scout exact matches first (`normalized_source_url`, `content_sha256`, `statement_hash`).
3. Checks cross-scout exact matches across the user's corpus.
4. Falls back to semantic matching against canonical rows only.
   Social scouts stay on the same write path, but semantic matching is blocked
   across the `social` / `non-social` boundary. Exact matches still merge
   across that boundary (`normalized_source_url`, `content_sha256`,
   `statement_hash`).
5. Either inserts a new canonical `information_units` row or appends a `unit_occurrences` row to an existing one.

## RLS

Core policies in 00004 + 00011:

| Table | Policy | Rule |
|---|---|---|
| `information_units` | `units_read` (SELECT) | `auth.uid() = user_id OR project shared via project_members` |
| `information_units` | `units_insert/update/delete` | `auth.uid() = user_id` |
| `unit_occurrences` | `unit_occurrences_user` | `auth.uid() = user_id` (writes revoked from user roles; workers use service-role) |
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
CRUD over canonical `information_units`. Project and scout filters resolve through `unit_occurrences`, not the canonical origin row.

### `units-search`
Semantic search entrypoint. Takes a text query, embeds via Gemini, calls `semantic_search_units` RPC.

### `entities`
CRUD over `entities`. The merge endpoint wraps `merge_entities` RPC.

### `reflections`
CRUD + search over `reflections`. Wraps `semantic_search_reflections`.

### `ingest`
User-driven ingest (text/url/pdf). Fetches content (firecrawl or direct), stores in `raw_captures`, extracts via Gemini, and calls `upsert_canonical_unit` with `source_type='manual_ingest'`.

## Extraction pipeline

```
Scout run → raw_captures (source of truth)
          → geminiExtract(EXTRACTION_SCHEMA, content) → [{statement, type, context_excerpt, occurred_at, entities}, ...]
          → geminiEmbed(statement) → vector(1536)
          → upsert_canonical_unit(...)              # exact same-scout → exact cross-scout → semantic canonical match
          → information_units INSERT or unit_occurrences INSERT
          → NER on statement → candidates
          → unit_entities INSERT (entity_id = NULL if no canonical match yet)
          → canonical resolution worker (offline) → attaches entity_id
```

`execution_records` holds a parallel card-sized summary for the UI — separate from `information_units` which are atomic facts.

## Invariants

1. **Entity identity is per-user.** No shared canonical graph across users. Merging Marc1's "UBS" with Marc2's "UBS" would be wrong — they might be talking about different things.
2. **`unit_entities.entity_id` can be NULL.** Unresolved mentions stay in the graph so a later canonicalisation pass can attach them; don't filter them out.
3. **`information_units.expires_at` is 90 days by default.** Renewal requires explicit retention policy work if that changes. Entities and reflections do not expire.
4. **Dedup scope is per-user and global across scouts/projects.** A fact discovered by Page Scout, Beat Scout, Civic Scout, Social Scout, or manual ingest should converge on one canonical unit with multiple occurrences when the evidence is exact or when semantic matching is allowed.
5. **Social scouts are stricter across scout boundaries.** Same-social reruns use the same dedup path as every other scout. Exact cross-scout matches are allowed, but semantic matching does not cross between `social` and `non-social` canonical rows.
6. **Semantic search RPCs require `p_user_id`.** SECURITY DEFINER bypasses RLS, so the callsite must pass `auth.uid()` explicitly — otherwise it's a data leak.

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
- `supabase/migrations/00008_phase1_tables.sql` — tables
- `supabase/migrations/00016_semantic_search_rpc.sql`, `00017_merge_entities_rpc.sql`, `00018_reflection_search_rpc.sql`, `00019_scout_rpcs.sql`
