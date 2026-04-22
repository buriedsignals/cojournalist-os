# cojo-mcp — stdio bridge for the coJournalist MCP server

`cojo-mcp` is a small, signed binary that lets stdio-only MCP clients
(Claude Desktop, Cursor with local configs, custom local agents) talk to
the hosted coJournalist MCP Edge Function over HTTPS. It does one thing:
read newline-delimited JSON-RPC 2.0 on stdin, POST each line to
`${api_url}/functions/v1/mcp-server/` with your `cj_…` API key, and
write the response back to stdout.

Agents that already support remote HTTP MCP servers (e.g. the web app
versions of Claude and ChatGPT that accept a URL + OAuth) don't need
this bridge — they connect directly.

## Install

### From a release binary (recommended)

```bash
# macOS (Apple Silicon)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mcp-darwin-arm64 \
  | sudo tee /usr/local/bin/cojo-mcp > /dev/null && sudo chmod +x /usr/local/bin/cojo-mcp

# macOS (Intel)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mcp-darwin-x86_64 \
  | sudo tee /usr/local/bin/cojo-mcp > /dev/null && sudo chmod +x /usr/local/bin/cojo-mcp

# Linux (x86_64)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mcp-linux-x86_64 \
  | sudo tee /usr/local/bin/cojo-mcp > /dev/null && sudo chmod +x /usr/local/bin/cojo-mcp

# Linux (arm64)
curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mcp-linux-arm64 \
  | sudo tee /usr/local/bin/cojo-mcp > /dev/null && sudo chmod +x /usr/local/bin/cojo-mcp
```

Verify:

```bash
cojo-mcp --version
```

macOS binaries are codesigned + notarized by Apple. Linux binaries are
statically linked; verify with the published `.sha256` sibling if you'd
like.

## Configure

Reuse the cojo CLI's config file at `~/.cojournalist/config.json`. If
you don't have the CLI, write it yourself.

```bash
cojo config set api_url=https://gfmdziplticfoakhrfpt.supabase.co
cojo config set supabase_anon_key=<public anon key>
cojo config set api_key=cj_<your api key>
```

Or override per-launch with env vars:

| Variable | Default | Required |
|---|---|---|
| `COJOURNALIST_API_URL` | `https://gfmdziplticfoakhrfpt.supabase.co` | no |
| `COJOURNALIST_API_KEY` | — | yes |
| `COJOURNALIST_SUPABASE_ANON_KEY` | — | yes, when `api_url` is a Supabase host |

Generate a `cj_…` API key at [cojournalist.ai](https://www.cojournalist.ai)
→ Agents → API → Create key.

## Wire it into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and
add:

```json
{
  "mcpServers": {
    "cojournalist": {
      "command": "cojo-mcp"
    }
  }
}
```

If you don't want to rely on `~/.cojournalist/config.json` (e.g. multiple
Claude profiles), pass credentials via env instead:

```json
{
  "mcpServers": {
    "cojournalist": {
      "command": "cojo-mcp",
      "env": {
        "COJOURNALIST_API_URL": "https://gfmdziplticfoakhrfpt.supabase.co",
        "COJOURNALIST_API_KEY": "cj_...",
        "COJOURNALIST_SUPABASE_ANON_KEY": "..."
      }
    }
  }
}
```

Restart Claude Desktop. It should advertise tools like `list_scouts`,
`verify_unit`, `search_units` in the tool picker.

## Wire it into Cursor / other local MCP clients

Most clients accept the same command/env shape. Example for Cursor:

```json
{
  "mcp.servers": {
    "cojournalist": {
      "type": "stdio",
      "command": "cojo-mcp"
    }
  }
}
```

## Troubleshooting

- **`config error — Missing api_key`** — run `cojo config set api_key=cj_...`
  or set `COJOURNALIST_API_KEY` in the client's `env` block.
- **`Supabase api_url requires supabase_anon_key`** — set the anon key.
  Find it in your Supabase project → Settings → API → `anon/public`.
- **Client shows zero tools** — double-check the bearer reaches the remote.
  Run `echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | cojo-mcp` —
  you should see a JSON line with `serverInfo.name = "cojournalist"`.
- **`command not found: cojo-mcp`** — install didn't land. Re-run the
  `curl` one-liner above.
- **`401` or `403` in the client error log** — API key was rotated or
  revoked. Mint a fresh one in the app and update the config.

## Build from source

Requires [Deno](https://deno.com) v2.x.

```bash
cd mcp
deno task test             # 18 unit tests
deno task run              # run bridge against stdin
deno task compile-all      # build mac arm/x86 + linux arm/x86 binaries
```

## Release

Push a `mcp-v*` tag on the private monorepo — the
[`mcp-release.yml`](../.github/workflows/mcp-release.yml) workflow
compiles for all four platforms, codesigns + notarizes macOS binaries
with the Apple Developer cert, and publishes the release on
[`buriedsignals/cojournalist-os`](https://github.com/buriedsignals/cojournalist-os/releases)
so anyone can `curl` the assets without GitHub auth.

```bash
git tag mcp-v0.1.0 -m "cojo-mcp 0.1.0 — initial release"
git push origin mcp-v0.1.0
```
