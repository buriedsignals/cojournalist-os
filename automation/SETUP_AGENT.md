# coJournalist Self-Hosted Setup

Use this when the user wants to deploy `buriedsignals/cojournalist-os`.

## Deployment Model

Assume the OSS deployment is:
- Supabase Auth for login
- Supabase Postgres for storage
- Supabase Edge Functions for the default backend surface
- Static frontend on any host

FastAPI is optional. Treat it as an add-on only if the user explicitly wants the legacy/internal `/api/v1` surface.

## Required Inputs

Collect these before you start:
- `GEMINI_API_KEY`
- `FIRECRAWL_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`
- `APIFY_API_TOKEN`

Optional:
- `PUBLIC_MAPTILER_API_KEY`
- `OPENROUTER_API_KEY`

Supabase:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_JWT_SECRET`
- `SUPABASE_PROJECT_REF`

## Required Steps

1. Clone the OSS repo and use branch `master`.

```bash
git clone https://github.com/buriedsignals/cojournalist-os.git
cd cojournalist-os
git checkout master
```

2. Read the setup docs before changing anything:
- `deploy/SETUP.md`
- `deploy/docker/.env.example`
- `deploy/docker/docker-compose.yml`
- `deploy/render/render.yaml`

3. Run Supabase migrations:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

4. Deploy Edge Functions:

```bash
supabase functions deploy --all
```

5. Set the function secrets:

```bash
supabase secrets set \
  GEMINI_API_KEY=... \
  FIRECRAWL_API_KEY=... \
  RESEND_API_KEY=... \
  RESEND_FROM_EMAIL=... \
  APIFY_API_TOKEN=... \
  INTERNAL_SERVICE_KEY=...
```

6. Write the project `.env` with the Supabase and frontend values:
- `DEPLOYMENT_TARGET=supabase`
- `PUBLIC_DEPLOYMENT_TARGET=supabase`
- `PUBLIC_SUPABASE_URL=<SUPABASE_URL>`
- `PUBLIC_SUPABASE_ANON_KEY=<SUPABASE_ANON_KEY>`

7. Build and deploy the frontend:

```bash
cd frontend
npm ci
npm run build
```

8. If the user wants the optional Python API add-on, deploy `backend/` separately or use `deploy/render/render.yaml`.

## Guardrails

- Do not assume Render is required.
- Do not assume same-origin `/api` is required.
- Do not use any license-key flow; the setup is public.
- Do not use `main` for the public OSS repo. Use `master`.
- If you install the sync workflow, push it to `origin master`.

## Verification

Verify these:
- `/login` uses Supabase email/password auth
- the frontend can reach Supabase Edge Functions
- scouts can be created
- feed units load

If the optional FastAPI add-on was deployed, also verify:

```bash
curl https://<fastapi-host>/api/health
```
