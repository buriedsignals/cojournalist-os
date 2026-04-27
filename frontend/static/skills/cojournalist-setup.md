# coJournalist setup skill

Use this when the user wants to install, self-host, configure, or validate
coJournalist. For day-to-day newsroom use, prefer the product skill at
`https://www.cojournalist.ai/skills/cojournalist.md`.

## Public surfaces

For hosted SaaS, the public app is `https://www.cojournalist.ai`.

For self-hosted deployments, use the newsroom's own deployed app URL and the
Supabase/API/MCP targets generated during setup. Do not point newsroom agents at
the hosted cojournalist.ai Supabase project.

## Hosted agent setup

1. Open coJournalist and create a `cj_...` API key from the Agents API panel.
2. Configure the agent to use either MCP or the CLI.
3. Verify with a read-only operation first: list scouts or list units.
4. Do not run scouts or create scheduled monitors until the user confirms credit
   spend.

## CLI setup

Use Deno 2.x to install directly from the public mirror:

Hosted example:

```bash
deno install -A -g -n cojo https://raw.githubusercontent.com/buriedsignals/cojournalist-os/master/cli/cojo.ts
cojo config set api_url=https://www.cojournalist.ai/functions/v1
cojo config set api_key=<cj_... API key>
cojo scouts list
```

Self-hosted example:

```bash
cojo config set api_url=https://<project-ref>.supabase.co/functions/v1
cojo config set supabase_anon_key=<SUPABASE_ANON_KEY>
cojo config set api_key=<cj_... API key>
cojo scouts list
```

## MCP setup

Hosted remote MCP endpoint:

```text
https://www.cojournalist.ai/mcp
```

The MCP server uses OAuth discovery at:

```text
https://www.cojournalist.ai/mcp/.well-known/oauth-authorization-server
https://www.cojournalist.ai/mcp/.well-known/oauth-protected-resource
```

If OAuth is unavailable in the client, use a `cj_...` API key through the CLI or
REST API instead.

Self-hosted MCP endpoint:

```text
https://<project-ref>.supabase.co/functions/v1/mcp-server
```

If a self-hosted deployment fronts Supabase with its own domain, advertise and
use that public MCP URL consistently. Set `MCP_SERVER_BASE_URL` to the same
external URL so issuer, token, register, authorize, and protected-resource
metadata all match what the MCP client connects to.

## Self-hosted setup checks

Before treating a self-hosted install as ready:

- apply all Supabase migrations
- deploy Edge Functions
- create the required Supabase secrets
- confirm MapTiler is configured; location scouting depends on it
- confirm auth mode is intentionally set for hosted or local/demo use
- open `/setup` and verify the instructions match the target deployment
- verify REST list endpoints return `{ "items": [...], "pagination": ... }`
- verify MCP `initialize` and `tools/list` against the self-hosted MCP URL
- verify a read-only CLI call with a `cj_...` API key

## Canonical location

Canonical URL: `https://www.cojournalist.ai/skills/cojournalist-setup.md`
