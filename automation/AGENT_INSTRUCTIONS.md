# coJournalist Deployment Agent Instructions

Start with:

```text
Read automation/SETUP_AGENT.md and deploy coJournalist.
```

## Operating assumptions

- Public OSS repo: `https://github.com/buriedsignals/cojournalist-os`
- Public OSS branch: `master`
- Default backend surface: Supabase Edge Functions
- Default auth: Supabase email/password
- FastAPI is optional and should only be deployed if the user wants the legacy/internal `/api/v1` add-on

## What to do

1. Clone the OSS repo and check out `master`.
2. Read `deploy/SETUP.md` and the deployment files before making changes.
3. Collect the required API keys and Supabase values from the user.
4. Run:

```bash
supabase link --project-ref <project-ref>
supabase db push
supabase functions deploy --all
```

5. Set the Supabase function secrets:

```bash
supabase secrets set \
  GEMINI_API_KEY=... \
  FIRECRAWL_API_KEY=... \
  RESEND_API_KEY=... \
  RESEND_FROM_EMAIL=... \
  APIFY_API_TOKEN=... \
  INTERNAL_SERVICE_KEY=...
```

6. Write the project `.env` so the frontend uses:
- `PUBLIC_DEPLOYMENT_TARGET=supabase`
- `PUBLIC_SUPABASE_URL=<SUPABASE_URL>`
- `PUBLIC_SUPABASE_ANON_KEY=<SUPABASE_ANON_KEY>`

7. Build the frontend:

```bash
cd frontend
npm ci
npm run build
```

8. Deploy the static frontend on the user's preferred host.
9. Only if requested, deploy the optional FastAPI add-on from `backend/` or via `deploy/render/render.yaml`.
10. If asked to install the sync workflow, copy `automation/sync-upstream.yml` into `.github/workflows/` and push to `origin master`.

## Do not do these

- Do not use any license validation flow.
- Do not tell the user that Render is required.
- Do not default the frontend to same-origin `/api`.
- Do not push to `origin main` in the OSS repo.

## Verification

Minimum verification:
- the frontend builds
- `/login` is Supabase auth
- a user can sign in
- scouts and units work against Supabase Edge Functions

Optional verification if FastAPI was deployed:

```bash
curl https://<fastapi-host>/api/health
```
