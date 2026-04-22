# `cojo-mcp` stdio bridge

Ships the MCP server surface to stdio-only clients (Claude Desktop, some
Cursor configs, any local agent framework that doesn't speak remote MCP).
The hosted HTTP MCP server at
`${SUPABASE_URL}/functions/v1/mcp-server/` is always the source of truth;
this bridge is just transport translation.

## Architecture

```
MCP client (Claude Desktop) ──(stdio JSON-RPC)──> cojo-mcp ──(HTTPS + Bearer + apikey)──> Supabase Edge Function mcp-server
```

- Read newline-delimited JSON-RPC on stdin
- For each line: validate it's JSON-RPC 2.0, forward body verbatim to the
  remote, write the remote's response back on stdout (one line)
- Notifications (no `id`) forward but emit no stdout line — per JSON-RPC
- Errors from the forwarder become JSON-RPC error responses so the
  framing stays intact; non-protocol diagnostics go to stderr

The bridge is **deliberately dumb** — it never parses, mutates, or
validates tool payloads. This keeps it forward-compatible with new tools
and new MCP protocol versions without needing a bridge release. Its only
jobs are (1) transport translation and (2) auth injection.

## Release procedure

Identical pattern to the CLI (see `cli/CLAUDE.md`):

1. Pick a semver. First release: `0.1.0`.
2. `git tag mcp-v0.1.0 -m "cojo-mcp 0.1.0 — initial release"`
3. `git push origin mcp-v0.1.0`
4. `.github/workflows/mcp-release.yml` fires on the private monorepo:
   - 4 matrix builds (mac arm/x86, linux arm/x86)
   - macOS binaries are code-signed + notarized via the same Apple
     Developer cert used for `cojo`
   - Release published on `buriedsignals/cojournalist-os` (public OSS
     mirror) with 4 binaries + 4 sha256 files, via `OSS_RELEASE_PAT`.
5. Smoke test: `curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mcp-darwin-arm64 -o /tmp/cojo-mcp && chmod +x /tmp/cojo-mcp && /tmp/cojo-mcp --version`.

## Tag naming

- Release: `mcp-v<MAJOR>.<MINOR>.<PATCH>` (e.g. `mcp-v0.1.0`)
- Pre-release (workflow marks as prerelease on GitHub):
  - `mcp-v0.1.0-rc1`, `mcp-v0.1.0-beta2`, `mcp-v0.1.0-alpha1`

CI injects the version string into `mcp/lib/version.ts` via `sed` before
`deno compile`. Local dev builds stay `"dev"`.

## Structure

- `cojo-mcp.ts` — entry point; handles `--version` / `--help`, loads
  config, kicks off the bridge loop.
- `lib/bridge.ts` — `forwardOne` (single line) + `runBridge` (stdin loop).
- `lib/config.ts` — config loader + `remoteUrl` + `remoteHeaders`.
  Reads `~/.cojournalist/config.json` (same file as the cojo CLI) with
  env-var overrides.
- `lib/version.ts` — `VERSION` constant rewritten by CI at release time.
- `lib/_test.ts` — 18 unit tests (config + forwarder + integration).
- `deno.json` — tasks: test, run, compile-mac-arm/x86, compile-linux-arm/x86, compile-all.

## Auth — reuses the CLI's config

- `api_key` (preferred) — `cj_…` key generated in the app at /api →
  Agents → API. Sent as `Authorization: Bearer cj_…`.
- `supabase_anon_key` — **required** when `api_url` is a Supabase host.
  Sent as the `apikey:` header. Without it, Kong rejects the request.
- `api_url` — bare host. Trailing slash stripped. Default
  `https://gfmdziplticfoakhrfpt.supabase.co` if unset.

Env-var overrides: `COJOURNALIST_API_URL`, `COJOURNALIST_API_KEY`,
`COJOURNALIST_SUPABASE_ANON_KEY` — same names the CLI already uses.

## Why not embed the tools directly in the bridge?

Two reasons:

1. **Single source of truth.** Tools live in
   `supabase/functions/mcp-server/rpc.ts`. Bridge updates would need to
   ship every time a tool is added; forwarder updates never need to.
2. **Auth.** The `cj_…` key lives on the user's machine. If the bridge
   called sibling EFs directly it would need to understand each tool's
   RLS semantics. Forwarding through `mcp-server` means the same
   `requireUserOrApiKey` path gates every tool call.

## Secrets

Identical to the CLI release — `APPLE_CERT_P12`, `APPLE_CERT_PASSWORD`,
`APPLE_SIGNING_IDENTITY`, `APPLE_TEAM_ID`, `APPLE_API_KEY_P8`,
`APPLE_API_KEY_ID`, `APPLE_API_ISSUER_ID`, `OSS_RELEASE_PAT`. All sit on
the private `buriedsignals/coJournalist` repo.
