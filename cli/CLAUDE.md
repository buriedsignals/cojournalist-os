# `cojo` CLI

Shipping product. Users install from GitHub releases and run against prod.
Breaking changes need a version bump; do not rename flags, subcommands, or
env vars without thinking about existing installs.

## Release procedure

1. Ensure `main`/`migration` is clean and tests pass:
   ```bash
   cd cli && deno task test && deno task compile-all
   ```
2. Pick the next semver. First release: `0.1.0`.
3. Tag and push:
   ```bash
   git tag cli-v0.1.0 -m "cojo 0.1.0 — <headline>"
   git push origin cli-v0.1.0
   ```
4. `.github/workflows/cli-release.yml` fires (on the private monorepo,
   where the Apple secrets live):
   - 4 matrix builds (mac arm/x86, linux arm/x86)
   - macOS binaries are code-signed + notarized via Apple
   - Release published on the PUBLIC mirror
     (`buriedsignals/cojournalist-os`) with 4 binaries + 4 sha256 files,
     via `OSS_RELEASE_PAT`. Anyone can `curl` the assets without auth.
5. Smoke test: `curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-darwin-arm64 -o /tmp/cojo && chmod +x /tmp/cojo && /tmp/cojo --version`.

## Tag naming

- Release: `cli-v<MAJOR>.<MINOR>.<PATCH>` (e.g. `cli-v0.1.0`)
- Pre-release (workflow marks as prerelease on GitHub):
  - `cli-v0.1.0-rc1`, `cli-v0.1.0-beta2`, `cli-v0.1.0-alpha1`

The workflow injects the version string into `cli/lib/version.ts` via
`sed` before `deno compile`, so `cojo --version` reports the real tag
in shipped binaries. Local dev builds stay `"dev"`.

## Structure

- `cojo.ts` — entry point, subcommand dispatch, `--version` handling
- `commands/<name>.ts` — one file per subcommand (config, projects,
  scouts, units, ingest, export)
- `commands/_test.ts` — Deno unit tests
- `lib/client.ts` — REST client (`apiFetch`), `resolvePath` dual-backend
  shim, arg parser, table/json output helpers
- `lib/version.ts` — `VERSION` string rewritten by CI at release time
- `deno.json` — tasks: test, run, compile-mac-arm, compile-mac-x86,
  compile-linux-arm, compile-linux-x86, compile-all

## Dual-backend shim

`resolvePath` in `lib/client.ts` strips `/functions/v1/` from paths when
`api_url` doesn't contain `supabase.co`. Lets the same CLI talk to both the
pre-cutover FastAPI backend (`https://www.cojournalist.ai/api`) and the
post-cutover Supabase Edge Functions (`https://*.supabase.co/functions/v1`).
Remove the shim after the cutover is complete and all users have migrated.

## Secrets

All on the private `buriedsignals/coJournalist` repo:

| Secret | Purpose |
|---|---|
| `APPLE_CERT_P12` | base64 of Developer ID Application `.p12` |
| `APPLE_CERT_PASSWORD` | `.p12` export password |
| `APPLE_SIGNING_IDENTITY` | Cert Common Name (full string with team ID) |
| `APPLE_TEAM_ID` | 10-char team ID |
| `APPLE_API_KEY_P8` | App Store Connect API key file contents |
| `APPLE_API_KEY_ID` | Key ID |
| `APPLE_API_ISSUER_ID` | Issuer ID |
| `OSS_RELEASE_PAT` | Fine-grained PAT with `contents: write` on `buriedsignals/cojournalist-os` — publishes release assets on the public mirror |

Cert valid 5 years (renew 2031). Renewal reminder: `2027-04-15` decide
whether to keep paying Apple Developer Program ($109/yr).
