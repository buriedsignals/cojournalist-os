# RLS policies reference

Every Row Level Security policy, table by table. RLS is enabled on every application table — a missing policy effectively denies access.

**Model**: writes are always owner-only (`auth.uid() = user_id`). Reads are sometimes broadened via `project_members` (team-shared projects). Service-role bypasses RLS entirely — that's how Edge Functions write.

## Core tables (00004)

| Table | Policy | Ops | Condition |
|---|---|---|---|
| `scouts` | `scouts_user` | ALL | `auth.uid() = user_id` |
| `scout_runs` | `runs_user` | ALL | `auth.uid() = user_id` |
| `execution_records` | `exec_user` | ALL | `auth.uid() = user_id` |
| `post_snapshots` | `posts_user` | ALL | `auth.uid() = user_id` |
| `seen_records` | `seen_user` | ALL | `auth.uid() = user_id` |
| `information_units` | `units_user` | ALL | `auth.uid() = user_id` *(expanded by 00011, see below)* |
| `promises` | `promises_user` | ALL | `auth.uid() = user_id` |
| `user_preferences` | `prefs_user` | ALL | `auth.uid() = user_id` |

## Phase 1 tables (00011) — project-aware sharing

| Table | Policy | Ops | Condition |
|---|---|---|---|
| `raw_captures` | `raw_user` | ALL | `auth.uid() = user_id` |
| `ingests` | `ing_user` | ALL | `auth.uid() = user_id` |
| `civic_extraction_queue` | `civq_user` | ALL | `auth.uid() = user_id` |
| `apify_run_queue` | `apq_user` | ALL | `auth.uid() = user_id` |
| `entities` | `ent_user` | ALL | `auth.uid() = user_id` |
| `unit_entities` | `ue_user` | ALL | `auth.uid() = user_id` |
| `projects` | `projects_read` | SELECT | `auth.uid() = user_id OR EXISTS(SELECT 1 FROM project_members pm WHERE pm.project_id = projects.id AND pm.user_id = auth.uid())` |
| `projects` | `projects_write` | INSERT/UPDATE/DELETE | `auth.uid() = user_id` |
| `project_members` | `pm_self` | ALL | `auth.uid() = user_id` |
| `reflections` | `refl_read` | SELECT | owner OR project shared |
| `reflections` | `refl_write` | INSERT | `auth.uid() = user_id` |
| `reflections` | `refl_update` | UPDATE | `auth.uid() = user_id` |
| `reflections` | `refl_delete` | DELETE | `auth.uid() = user_id` |
| `scouts` | `scouts_read` (expands 00004) | SELECT | owner OR project shared |
| `scouts` | `scouts_insert/update/delete` | INSERT/UPDATE/DELETE | `auth.uid() = user_id` |
| `information_units` | `units_read` (expands 00004) | SELECT | owner OR project shared |
| `information_units` | `units_insert/update/delete` | INSERT/UPDATE/DELETE | `auth.uid() = user_id` |

## MCP OAuth (00024)

| Table | Policy | Ops | Condition |
|---|---|---|---|
| `mcp_oauth_clients` | `clients_owner_select` | SELECT | `auth.uid() = user_id` |
| `mcp_oauth_codes` | *(none)* | — | service-role only; never exposed to auth users |

## Credits (00025)

| Table | Policy | Ops | Condition |
|---|---|---|---|
| `orgs` | `orgs_read` | SELECT | `id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |
| `org_members` | `org_members_read` | SELECT | `user_id = auth.uid()` |
| `credit_accounts` | `credit_accounts_read` | SELECT | `user_id = auth.uid() OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |
| `usage_records` | `usage_records_read` | SELECT | `user_id = auth.uid() OR org_id IN (SELECT org_id FROM org_members WHERE user_id = auth.uid())` |

**No mutating policies** on any credits table. Only the `SECURITY DEFINER` RPCs (`decrement_credits`, `topup_team_credits`, `reset_expired_credits`) and service-role can change balances.

## Service-role & SECURITY DEFINER

- **Service-role bypasses RLS.** All Edge Functions that need cross-user work use `getServiceClient()`.
- **SECURITY DEFINER RPCs bypass RLS** too — they run as the function owner (postgres). So semantic search RPCs take `p_user_id UUID` as an explicit parameter and filter internally; without that parameter, they'd leak data.

## How to verify an RLS policy

```sql
-- Simulate a user query:
SET LOCAL "request.jwt.claims" = '{"sub":"<user_uuid>","role":"authenticated"}';
SELECT * FROM credit_accounts WHERE user_id = '<user_uuid>';  -- works
SELECT * FROM credit_accounts WHERE user_id = '<other_user_uuid>';  -- 0 rows

-- Reset to service role:
RESET ALL;
```

Or run an integration test with the user-scoped client (`getUserClient(userJwt)`) and assert the expected 403 / empty result.

## Pitfalls

1. **Forgetting RLS on a new table** — the table is wide open to any authenticated user. Enable RLS in the same migration that creates the table.
2. **Only adding SELECT policies** — users can then read their rows but not update them (FOR ALL covers everything, FOR SELECT does not). Use `FOR ALL` when the same condition applies to all operations.
3. **Using auth.uid() in an RPC body** — SECURITY DEFINER resets `auth.uid()` to the function owner (postgres), which is NULL. Always pass `p_user_id UUID` as a parameter and filter on it explicitly.
4. **Shared-project read escalation** — the project-shared SELECT policies on `scouts`/`information_units`/`reflections` depend on `project_members` containing the caller. Never allow self-insert into `project_members` without an owner check.

## See also

- `docs/supabase/rpc-reference.md` — SECURITY DEFINER grants
- `docs/supabase/edge-functions.md` — user vs service client usage
- Each system doc has an RLS section specific to its tables.
