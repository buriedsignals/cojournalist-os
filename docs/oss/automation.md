# OSS Automation

The public OSS automation surface is now:
- `automation/setup.sh`
- `automation/SETUP_AGENT.md`
- `automation/AGENT_INSTRUCTIONS.md`
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

## What changed

Removed from the OSS story:
- license validation
- license portal downloads
- `main` branch assumptions for the public mirror
- Render as the required/default deployment target
