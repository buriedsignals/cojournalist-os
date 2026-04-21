# Projects & ingest

Projects group scouts, units, and reflections into investigation workspaces. Ingest is the pathway for user-supplied content (URL, PDF, pasted text).

## Tables

### `projects` (00008)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID → `auth.users(id)` | |
| `name` | TEXT NOT NULL | UNIQUE (user_id, name) |
| `visibility` | TEXT CHECK IN ('private','team') DEFAULT 'private' | |
| `is_default` | BOOLEAN DEFAULT FALSE | One "Inbox" per user (backfill 00013) |
| `tags` | TEXT[] | |
| `created_at`, `updated_at` | TIMESTAMPTZ | `updated_at` via trigger |

### `project_members` (00008)

Team sharing. Dormant in OSS today; surfaced in SaaS once Team plans are wired through.

| Column | Type | Notes |
|---|---|---|
| `project_id` | UUID → `projects(id)` ON DELETE CASCADE | |
| `user_id` | UUID → `auth.users(id)` ON DELETE CASCADE | |
| `role` | TEXT CHECK IN ('viewer','editor','owner') | |
| `added_at` | TIMESTAMPTZ | |
| PRIMARY KEY `(project_id, user_id)` | | |

### `ingests` (00008)

User-initiated content uploads.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id`, `project_id` | FKs | |
| `kind` | TEXT CHECK IN ('url','pdf','text','file') | |
| `source_url` | TEXT | For `kind=url`; original filename for pdf/file |
| `status` | TEXT CHECK IN ('pending','processing','success','error') | |
| `error_message` | TEXT | |
| `created_at`, `completed_at` | TIMESTAMPTZ | |

## Default Inbox backfill (00013)

Every user gets an "Inbox" project on first sight. The backfill migration (00013) runs once:

```sql
-- Pseudocode:
INSERT INTO projects (user_id, name, is_default)
SELECT DISTINCT user_id, 'Inbox', TRUE FROM scouts
ON CONFLICT DO NOTHING;

UPDATE scouts SET project_id = (SELECT id FROM projects p WHERE p.user_id = scouts.user_id AND p.is_default)
WHERE project_id IS NULL;

UPDATE information_units SET project_id = (default project per user)
WHERE project_id IS NULL;
```

New users get an Inbox via an onboarding step (`POST /onboarding/initialize` in the `user` Edge Function).

## RLS

```sql
-- 00011:
CREATE POLICY projects_read  ON projects FOR SELECT USING (
    auth.uid() = user_id
    OR EXISTS (SELECT 1 FROM project_members pm WHERE pm.project_id = projects.id AND pm.user_id = auth.uid())
);
CREATE POLICY projects_write ON projects FOR ALL USING (auth.uid() = user_id);

CREATE POLICY pm_self ON project_members FOR ALL USING (auth.uid() = user_id);

CREATE POLICY ing_user ON ingests FOR ALL USING (auth.uid() = user_id);
```

Project-shared SELECT policies also apply to `scouts`, `information_units`, and `reflections` — see `docs/supabase/scouts-runs.md` and `units-entities.md`.

## Edge Functions

### `projects`
CRUD. List, create, update (name/visibility/tags), delete. The default Inbox is protected from deletion.

### `ingest`
Accepts `{ kind, source_url?, content? }`, writes an `ingests` row, kicks off fetch + extraction pipeline:

```
ingests INSERT status=pending
  → Firecrawl scrape (url) | PDF parse (pdf) | text-as-is (text)
  → raw_captures INSERT
  → geminiExtract(EXTRACTION_SCHEMA, content)
  → information_units INSERT (source_type='manual_ingest', project_id = active project)
  → geminiEmbed + unit_entities candidates
  → ingests UPDATE status=success, completed_at
```

On error: `ingests.status='error'`, `error_message` populated.

## Data flow

### Filing a scout into a project

```
Scout creation UI passes project_id
  → scouts INSERT with project_id
  → on run: information_units INSERT inherits project_id from scouts
  → project's Feed shows new units
```

Unattached scouts default to the user's Inbox project.

### Manual URL ingest

```
POST /functions/v1/ingest  { kind: 'url', source_url: 'https://...', project_id: '<uuid>' }
  → ingests row pending
  → firecrawl → raw_captures → gemini extract
  → information_units INSERT source_type=manual_ingest
  → ingests success
```

## Invariants

1. **Every user has at least one project** — the default Inbox. Deletion is blocked.
2. **`information_units.project_id` is set on insert.** The backfill handled legacy NULLs; going forward, the extract pipeline picks the scout's project or the default Inbox.
3. **Team sharing is read-only for members** unless role is `editor`/`owner`. Writes to `information_units` are still owner-only (the RLS update/delete policies check `user_id`), even in a shared project.

## See also

- `docs/supabase/scouts-runs.md` — scouts carry `project_id`
- `docs/supabase/units-entities.md` — units inherit `project_id`
- `supabase/migrations/00013_phase1_backfill.sql` — Inbox backfill mechanics
