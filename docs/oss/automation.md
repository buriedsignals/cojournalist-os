# OSS Automation

The public OSS automation surface is now:
- `automation/setup.sh`
- `automation/SETUP_AGENT.md`
- `automation/sync-upstream.yml`

These files are public and no longer use any license-gated flow.

## Current model

- Supabase is the default runtime.
- Supabase Edge Functions are the default backend surface.
- Static frontend hosting is the default deployment path.
- FastAPI is optional and only kept for newsrooms that want the legacy/internal Python API add-on.

## Sync workflow

`automation/sync-upstream.yml` is designed for forks of `buriedsignals/cojournalist-os` on branch `master`.

It can optionally:
- apply new Supabase migrations if `SUPABASE_PROJECT_REF` and `SUPABASE_ACCESS_TOKEN` are configured
- trigger a Render redeploy if `RENDER_DEPLOY_HOOK` is configured

For first-time installs or manual catch-up pulls, use
`automation/upstream-maintenance-codex-prompt.txt`. That prompt is intentionally
conservative for newsroom deployments:
- it searches for a nested Git checkout before editing, instead of assuming the
  current directory is the repo root
- it sets a repository-local Git committer identity if the server has none
- it preserves local `.env`, Supabase config, and deployment-specific edits
- it refuses to run `supabase db push` while local or untracked migration files
  are present
- it reports missing `gh` or GitHub push credentials instead of asking anyone to
  paste secrets into chat

## What changed

Removed from the OSS story:
- license validation
- license portal downloads
- `main` branch assumptions for the public mirror
- Render as the required/default deployment target
