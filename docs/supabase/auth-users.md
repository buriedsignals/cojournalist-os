# Auth & users

How identity flows from MuckRock → Supabase Auth → the `user` Edge Function → the frontend store.

## Identity

- **Identity provider**: MuckRock OIDC (Custom OIDC provider on Supabase Auth). The cutover ran in the 4-hour Sunday window 2026-04-21; design and preflight gates archived in the closed migration PRs.
- **User ID**: `auth.users.id` is the **MuckRock user UUID** preserved across the migration. Pre-seeded via `scripts/migrate/main.ts` Phase 0 using `supabase.auth.admin.createUser({ id: muckrock_uuid, email, email_confirm: true, user_metadata: { muckrock_subject, muckrock_username } })`.
- **Sign-in**: `supabase.auth.signInWithOAuth({ provider: 'muckrock', options: { redirectTo: 'https://cojournalist.ai/auth/callback' } })`. Supabase handles the OIDC dance; issues a JWT with `user_metadata.muckrock_subject`.
- **Session**: Supabase JS stores the JWT client-side. API calls send `Authorization: Bearer <jwt>` to Edge Functions.

## Tables

### `auth.users` (Supabase-managed)

Managed by Supabase; we don't own the schema. We interact with it via:
- `auth.admin.createUser()` during the preseed (service-role)
- `auth.getUser()` in Edge Function `requireUser()` helper (user JWT)
- `auth.uid()` inside RLS policies

Relevant fields:
- `id UUID PK` — MuckRock UUID
- `email TEXT`
- `user_metadata JSONB` — contains `muckrock_subject`, `muckrock_username` (added at preseed)

### `user_preferences`

Owned by the app. One row per user.

| Column | Type | Default | Notes |
|---|---|---|---|
| `user_id` | UUID PK → `auth.users(id)` ON DELETE CASCADE | — | |
| `timezone` | TEXT | `'UTC'` | IANA id |
| `preferred_language` | TEXT | `'en'` | ISO 639-1 |
| `notification_email` | TEXT | — | Where scheduled scout notifications go (may differ from `auth.users.email`) |
| `default_location` | JSONB | — | `GeocodedLocation` shape |
| `excluded_domains` | TEXT[] | — | Global Beat exclusion list |
| `preferences` | JSONB | `'{}'` | Overflow for ui_density, theme, digest_frequency, email_notifications |
| `onboarding_completed` | BOOLEAN | `FALSE` | |
| `onboarding_tour_completed` | BOOLEAN | `FALSE` | |
| `tier` | TEXT CHECK IN ('free','pro','team') | `'free'` | **Added by 00025.** Denormalized from `credit_accounts`. |
| `active_org_id` | UUID → `orgs(id)` | — | **Added by 00025.** Denormalized pointer; team pool to decrement against. NULL for individual users. |
| `created_at` | TIMESTAMPTZ | `NOW()` | |
| `updated_at` | TIMESTAMPTZ | `NOW()` | Maintained by `trg_user_prefs_updated_at` trigger |

Why the denormalized columns: `decrement_credits` reads `user_preferences` to pick the pool (team vs user). Without this, every RPC would need to join `org_members` — slower and adds a lock.

## RLS

### `user_preferences`

```sql
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY prefs_user ON user_preferences FOR ALL USING (auth.uid() = user_id);
```

Users may read and update their own row. Service-role (via Edge Functions) bypasses RLS.

The `tier` and `active_org_id` columns are writable by users via RLS, but in practice Edge Functions drive them from MuckRock webhook payloads. User-facing PATCH `/user/preferences` validates against a Zod schema that does **not** include `tier` or `active_org_id` — so users can't self-promote.

## RPCs used by this system

None owned by this doc. `user_preferences` upserts go through `supabase.from('user_preferences').upsert()` inside the `user` Edge Function.

## Edge Functions

### `user` — `supabase/functions/user/index.ts`

Routes:
- `GET /user/me` — JWT → profile. Joins `user_preferences` + `credit_accounts` + `orgs` to build the response the frontend stores on `$authStore.user`:
  ```json
  {
    "user_id": "<uuid>", "email": "...", "muckrock_subject": "...",
    "tier": "pro", "credits": 850, "monthly_cap": 1000,
    "org_id": null, "team": null,
    "upgrade_url": "https://accounts.muckrock.com/plans/70-cojournalist-pro/?source=cojournalist",
    "team_upgrade_url": "https://accounts.muckrock.com/plans/71-cojournalist-team/?source=cojournalist"
  }
  ```
  New users with no `credit_accounts` row yet get `credits: 100, monthly_cap: 100, tier: 'free'` defaults (seeded by the next MuckRock webhook).
- `GET /user/preferences` — reads user_preferences row (RLS-scoped via user client).
- `PATCH /user/preferences` — validates Zod schema `{ timezone?, language?, onboarding_completed?, email_notifications?, digest_frequency?, ui_density?, theme? }`, merges JSONB overflow into `preferences`.
- `POST /user/onboarding-complete` — flips `onboarding_completed = TRUE`.

Auth model: `requireUser(req)` extracts + verifies the JWT. Most operations use the user-scoped client (RLS applies). `GET /me` uses the service client so it can join `credit_accounts` on `org_id` even when the caller isn't listed in `org_members` yet (first-time team members during onboarding).

## Frontend glue

`frontend/src/lib/stores/auth-supabase.ts`:
- `init()` — reads Supabase session, then tries `GET /user/me` to enrich. Falls back to session-derived user on network error (so refresh doesn't bounce to /login).
- `login()` — redirects to `/login`.
- `signOut()` — `supabase.auth.signOut()` + navigate to `/login`.
- `refreshUser()` — re-fetches `/user/me`.
- `setCredits(credits)` — optimistic mutation after a scout run returns a new balance.
- `updatePreferences({ preferred_language?, timezone? })` — PATCH with fine-grained update.
- `getToken()` — returns the current access_token for API calls.

## Data flow

```
Browser login → MuckRock OIDC → Supabase issues JWT
Browser        → GET /functions/v1/user/me  (Bearer JWT)
user fn        → requireUser → authenticated client
user fn        → service client:
                    SELECT tier, active_org_id FROM user_preferences WHERE user_id = me
                    SELECT balance, monthly_cap, tier FROM credit_accounts
                      WHERE (active_org_id ? org_id = active_org_id : user_id = me)
                    IF team: SELECT name FROM orgs, COUNT FROM org_members
               → returns profile payload
Browser        → authStore.user populated, topnav credits pill renders
```

Subsequent scout runs update balance server-side and return it in the 200/402 response body. The browser calls `setCredits()` to keep the topnav pill live without a full `/me` refetch.

## Invariants

1. **`auth.users.id == muckrock_subject`** — preserved across migration; FKs in every app table trust this.
2. **`user_preferences.user_id` is 1:1 with `auth.users.id`** — upsert-by-user_id always.
3. **`user_preferences.active_org_id` mirrors `org_members`** for that user — the MuckRock webhook handler keeps these in sync; direct SQL writes are unsafe.
4. **Users cannot self-promote their tier** — API `PATCH /user/preferences` excludes `tier`/`active_org_id` from the Zod schema; only the webhook handler (service-role) writes them.

## See also

- `docs/supabase/credits-entitlements.md` — how tier + active_org_id drive credits
- `docs/muckrock/oauth-integration.md` — upstream OIDC details
- `scripts/migrate/main.ts` Phase 0 — preseeding of `auth.users`
