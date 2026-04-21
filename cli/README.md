# cojo — coJournalist v2 CLI

Command-line tool for coJournalist v2. Speaks the REST API using a JWT bearer
token. No external dependencies: the release binary ships as a single signed,
notarized executable per platform.

## Install

### From a release binary (recommended)

Single-line install — no auth required. Binaries are code-signed and
notarized by Apple on macOS (no Gatekeeper warning), and Linux binaries
are statically linked.

```bash
# macOS (Apple Silicon)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-darwin-arm64 \
  | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo

# macOS (Intel)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-darwin-x86_64 \
  | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo

# Linux (x86_64)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-linux-x86_64 \
  | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo

# Linux (arm64)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-linux-arm64 \
  | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo
```

Verify install:

```bash
cojo --version
```

### Verify the checksum (optional)

Each binary ships with a matching `.sha256` file:

```bash
# macOS (Apple Silicon) example — adjust for your platform
curl -fsSL -O https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-darwin-arm64.sha256
shasum -a 256 -c cojo-darwin-arm64.sha256   # macOS
# or: sha256sum -c cojo-darwin-arm64.sha256  # Linux
```

### Manual download

Grab any release directly from
<https://github.com/buriedsignals/cojournalist-os/releases>.

### Homebrew

Coming soon.

### From source (Deno)

Requires Deno 2.x on `$PATH`.

```bash
git clone https://github.com/buriedsignals/cojournalist-os.git
cd cojournalist-os/cli
deno install -A -g -n cojo cojo.ts         # installs to ~/.deno/bin
# or build a self-contained binary for your machine:
deno task compile-mac-arm                   # or -mac-x86 / -linux-arm / -linux-x86
```

## Configure

Config lives at `~/.cojournalist/config.json`:

```bash
# Point at production (pre-cutover — current FastAPI backend)
cojo config set api_url=https://www.cojournalist.ai/api

# Post-cutover (Supabase Edge Functions) — the CLI auto-adjusts paths
cojo config set api_url=https://gfmdziplticfoakhrfpt.supabase.co/functions/v1

# Paste your JWT from the browser devtools (Application → Cookies or
# localStorage, whichever holds the access token in your session)
cojo config set auth_token=<JWT>

cojo config show
```

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
cojo units list --since 7d --verified
cojo units show <id>
cojo units verify <id> --notes "Cross-checked with minutes" --by "Tom"
cojo units search --query "zoning variance"

# Ingest a URL or stdin text
cojo ingest url https://example.com/article --project <id>
echo "raw notes" | cojo ingest text --title "Field notes"

# Export a project as markdown for Claude / LLM context
cojo export claude --project <id> --limit 50 | pbcopy
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
