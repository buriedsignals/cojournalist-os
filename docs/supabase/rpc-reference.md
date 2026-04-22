# RPC reference

Every Postgres function exposed via PostgREST. Grouped by system. All are `SECURITY DEFINER` with `SET search_path = public` unless noted.

## Convention

- **Mutating RPCs** (write data, change state): EXECUTE revoked from `PUBLIC, anon, authenticated`. Only `service_role` (Edge Functions via service client) can call them.
- **Read-only RPCs** (search, check): may allow `authenticated` to call, but must take `p_user_id UUID` explicitly and filter internally — because SECURITY DEFINER bypasses RLS.

## Credits (00025)

### `decrement_credits(p_user_id UUID, p_cost INT, p_scout_id UUID, p_scout_type TEXT, p_operation TEXT) RETURNS TABLE(balance INT, owner TEXT)`
Atomic decrement + audit insert in one transaction. Tries team pool first (if `user_preferences.active_org_id` set), falls back to user pool. Raises `insufficient_credits` (SQLSTATE P0002) on overdraft. **Service-role only.**

### `topup_team_credits(p_org_id UUID, p_new_cap INT, p_update_on DATE) RETURNS INT`
Mirrors MuckRock webhook update. `balance += max(0, new_cap - monthly_cap)`; clips balance on downgrade. Idempotent. Returns final balance. **Service-role only.**

### `reset_expired_credits() RETURNS INT`
Cron-driven. Resets balance to monthly_cap where `update_on <= CURRENT_DATE`; advances `update_on` by one month. Returns row count. **Service-role only.**

## Scout scheduling (00015, 00019)

### `schedule_scout(p_scout_id UUID, p_cron_expr TEXT) RETURNS VOID`
Creates a pg_cron job named `scout-<uuid>` that HTTP-POSTs `{scout_id}` to `execute-scout`. Reads vault secrets (`project_url`, `service_role_key`). Idempotent — unschedules existing.

### `unschedule_scout(p_scout_id UUID) RETURNS VOID`
Removes `scout-<uuid>`.

### `trigger_scout_run(p_scout_id UUID, p_user_id UUID) RETURNS UUID`
Manual fire-and-forget. Inserts `scout_runs` row status=running, async POSTs to `execute-scout`, returns run_id.

### `increment_scout_failures(p_scout_id UUID, p_threshold INT DEFAULT 3) RETURNS TABLE(consecutive_failures INT, is_active BOOLEAN)`
On scout error: increments `scouts.consecutive_failures`; flips `is_active=FALSE` at threshold. Returns new state.

### `reset_scout_failures(p_scout_id UUID) RETURNS VOID`
On scout success: resets counter to 0.

### `check_unit_dedup(p_embedding vector(1536), p_scout_id UUID, p_threshold REAL DEFAULT 0.85, p_days INT DEFAULT 90) RETURNS BOOLEAN`
Returns TRUE if any `execution_records` row under the same scout within `p_days` has cosine ≥ `p_threshold`. Used pre-insert in scout-execute functions.

## API keys (00036)

### `validate_api_key(p_key text) RETURNS uuid`
SECURITY DEFINER. Hashes `p_key` with `sha256`, looks up the matching `api_keys` row, stamps `last_used_at` on a hit, and returns the owning `user_id` (or NULL on miss). EXECUTE granted to `anon, authenticated, service_role` so the unauthenticated EF gateway can validate before resolving the caller. Only the `requireUserOrApiKey()` helper in `_shared/auth.ts` calls it. See [auth-users.md](./auth-users.md#api-keys-agent-tokens).

## Search (00016, 00018)

### `semantic_search_units(p_embedding vector(1536), p_user_id UUID, p_project_id UUID DEFAULT NULL, p_limit INT DEFAULT 20) RETURNS TABLE(id UUID, statement TEXT, type TEXT, source_url TEXT, source_title TEXT, occurred_at TIMESTAMPTZ, extracted_at TIMESTAMPTZ, similarity_score REAL)`
Cosine similarity over `information_units`. **Requires caller to pass `auth.uid()` as `p_user_id`** — otherwise it bypasses ownership.

### `semantic_search_reflections(p_embedding, p_user_id, p_project_id DEFAULT NULL, p_limit DEFAULT 20)`
Same over `reflections`.

## Entity management (00017)

### `merge_entities(p_user_id UUID, p_keep_id UUID, p_merge_ids UUID[]) RETURNS VOID`
Verifies ownership of `p_keep_id` + all `p_merge_ids`. Unions aliases, remaps `unit_entities.entity_id` (skipping `(unit_id, mention_text)` collisions), deletes merged rows, recomputes `mention_count`. Raises on ownership mismatch.

## Queues (00020, 00022)

### `claim_civic_queue_item() RETURNS TABLE(id UUID, user_id UUID, scout_id UUID, source_url TEXT, doc_kind TEXT, attempts INT)`
Atomic `FOR UPDATE SKIP LOCKED` claim: picks one `pending` row or stuck-`processing` row; marks it `processing`, increments `attempts`, sets `claimed_at`. Returns 0 or 1 row.

### `civic_queue_failsafe() RETURNS VOID`
Every 10 minutes: resets `processing` rows stuck > 30 minutes → `pending` (or `failed` if attempts ≥ 3).

### `apify_mark_timeouts() RETURNS VOID`
Every 15 minutes: marks `pending`/`running` rows started > 2 hours ago as `timeout`.

## Cleanup (00006, 00014, 00024, 00026)

All take no params, return VOID, batch `LIMIT 10000` per invocation to keep cron runs short.

| Function | Target | Condition |
|---|---|---|
| `cleanup_scout_runs()` | `scout_runs` | `expires_at < NOW()` |
| `cleanup_execution_records()` | `execution_records` | `expires_at < NOW()` |
| `cleanup_information_units()` | `information_units` | `expires_at < NOW()` |
| `cleanup_seen_records()` | `seen_records` | `expires_at < NOW()` |
| `cleanup_raw_captures()` | `raw_captures` | `expires_at < NOW()` |
| `cleanup_civic_queue()` | `civic_extraction_queue` | status in ('done','failed') AND updated_at < NOW() - 7d |
| `cleanup_apify_queue()` | `apify_run_queue` | status in ('succeeded','failed','timeout') AND completed_at < NOW() - 7d |
| `cleanup_mcp_oauth_codes()` | `mcp_oauth_codes` | `used_at > NOW() - 5m` OR `expires_at < NOW()` |
| `cleanup_usage_records()` | `usage_records` | `expires_at < NOW()` |

## Cron wrappers (00006)

### `schedule_cron_job(job_name TEXT, cron_expr TEXT, command TEXT) RETURNS BIGINT`
Wraps `cron.schedule()` so PostgREST callers (Edge Functions) can schedule jobs. Returns the jobid.

### `unschedule_cron_job(job_name TEXT) RETURNS BOOLEAN`
Wraps `cron.unschedule()`.

**Use case**: `schedule_scout` calls these internally. Edge Functions that dynamically provision cron jobs (e.g. `manage-schedule`) go through them too.

## Permissions table

| RPC | EXECUTE granted to |
|---|---|
| `decrement_credits` | service_role only |
| `topup_team_credits` | service_role only |
| `reset_expired_credits` | service_role only |
| `schedule_scout`, `unschedule_scout`, `trigger_scout_run` | service_role only (reads vault) |
| `increment_scout_failures`, `reset_scout_failures`, `check_unit_dedup` | service_role (called from Edge Functions) |
| `semantic_search_units`, `semantic_search_reflections` | authenticated (filter by `p_user_id`) |
| `merge_entities` | authenticated (internal ownership check) |
| `claim_civic_queue_item`, `civic_queue_failsafe`, `apify_mark_timeouts` | service_role only |
| `validate_api_key` | anon, authenticated, service_role (called by `requireUserOrApiKey` before the caller is known) |
| `cleanup_*` | service_role only (called from pg_cron) |
| `schedule_cron_job`, `unschedule_cron_job` | service_role only |

To inspect actual grants:

```sql
SELECT p.proname, r.rolname AS grantee, acl.privilege_type
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  LEFT JOIN aclexplode(p.proacl) acl ON TRUE
  LEFT JOIN pg_roles r ON r.oid = acl.grantee
 WHERE n.nspname = 'public'
   AND p.proname IN ('decrement_credits', 'topup_team_credits', 'reset_expired_credits')
 ORDER BY p.proname, r.rolname;
```

## How to call from an Edge Function

User-scoped RPC (read-only, uses user JWT):
```typescript
const userClient = getUserClient(bearerToken);
const { data, error } = await userClient.rpc('semantic_search_units', {
  p_embedding: embedding,
  p_user_id: user.id,
  p_project_id: projectId ?? null,
  p_limit: 20,
});
```

Service-role RPC (mutating):
```typescript
const svc = getServiceClient();
const { data, error } = await svc.rpc('decrement_credits', {
  p_user_id: scout.user_id,
  p_cost: CREDIT_COSTS.website_extraction,
  p_scout_id: scout.id,
  p_scout_type: 'web',
  p_operation: 'website_extraction',
});
```

## See also

- `docs/supabase/credits-entitlements.md` — decrement/topup flow
- `docs/supabase/scouts-runs.md` — scheduling RPCs
- `docs/supabase/units-entities.md` — merge and search
- `docs/supabase/civic-pipeline.md` — queue RPCs
- `docs/supabase/rls-reference.md` — why SECURITY DEFINER needs explicit user_id
