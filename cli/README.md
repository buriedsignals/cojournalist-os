# cojo — coJournalist v2 CLI

Command-line tool for coJournalist v2. Speaks the REST API using a `cj_...` API
key or legacy JWT bearer token.

## Install

### From source via Deno (recommended until public release assets exist)

Requires [Deno](https://deno.com) v2.x on `$PATH`.

```bash
deno install -A -g -n cojo https://raw.githubusercontent.com/buriedsignals/cojournalist-os/master/cli/cojo.ts
```

Verify install:

```bash
cojo --version
```

### Build a local binary

If you want a self-contained executable instead of a Deno shim:

```bash
git clone https://github.com/buriedsignals/cojournalist-os.git
cd cojournalist-os/cli
deno task compile-mac-arm        # or compile-mac-x86 on Intel
sudo mv dist/cojo-darwin-arm64 /usr/local/bin/cojo
sudo chmod +x /usr/local/bin/cojo
```

Verify:

```bash
cojo --version
```

### Release binaries

Release binaries will appear at
<https://github.com/buriedsignals/cojournalist-os/releases> once the public
mirror starts publishing signed assets.

### Homebrew

Coming soon.

## Configure

Config lives at `~/.cojournalist/config.json`. Set an api_url and **either** an
`api_key` (preferred — generated in the app at /api → Agents → API → Create key)
or a legacy `auth_token` JWT.

```bash
# Hosted coJournalist — recommended
cojo config set api_url=https://www.cojournalist.ai/functions/v1
cojo config set api_key=cj_xxxxxxxxxxxxxxxxxx

# Self-hosted Supabase Edge Functions
cojo config set api_url=https://<project-ref>.supabase.co
cojo config set api_key=cj_xxxxxxxxxxxxxxxxxx
cojo config set supabase_anon_key=<SUPABASE_ANON_KEY>

# Legacy JWT path
cojo config set auth_token=<JWT>          # paste from browser devtools if needed
cojo config show
```

### Auth precedence

`apiFetch` picks the first credential found, in this order:

1. `api_key` — sent as `Authorization: Bearer cj_…`. When `api_url` points at
   the hosted broker, that is sufficient. When `api_url` contains `supabase.co`,
   `supabase_anon_key` is also sent as the `apikey:` header (Supabase Edge
   Functions reject bearer tokens without it).
2. `auth_token` — sent as `Authorization: Bearer <jwt>`. Use this only for
   legacy SaaS sessions.

If both are set, `api_key` wins. If neither is set, every command exits with a
setup hint.

No OAuth flow in the CLI — tokens are pasted manually.

## Quick start

```bash
# Projects
cojo projects list
cojo projects add --name "City Hall Watch" --visibility private

# Scouts
cojo scouts list
cojo scouts add --name "Council agenda" --type web --url https://example.gov
cojo scouts run <id>

# Information units
cojo units list --verified
cojo units show <id>
cojo units verify <id> --notes "Cross-checked with minutes" --by "Tom"
cojo units search --query "zoning variance"

# Ingest a URL or stdin text
cojo ingest url https://example.com/article --project <id>
echo "raw notes" | cojo ingest text --title "Field notes"

# Search and manage units directly
cojo units search --query "zoning variance" --mode hybrid --project <id>
cojo units mark-used <id> --url https://example.com/story
cojo units delete <id>
```

Run `cojo <command> --help` for subcommand-specific usage.

## Development

```bash
cd cli
deno task run projects list     # run from source
deno task test                   # run unit tests
deno task compile-all            # build all 4 release targets locally
```

## Releasing

See `cli/CLAUDE.md` for the release procedure and conventions.
