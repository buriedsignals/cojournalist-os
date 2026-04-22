#!/usr/bin/env -S deno run --allow-net --allow-env --allow-read
/**
 * cojo-mcp — stdio bridge for the coJournalist MCP Edge Function.
 *
 * Launched by MCP clients that only speak stdio (Claude Desktop, some
 * Cursor configs, local agent frameworks). Forwards JSON-RPC messages to
 * the deployed HTTP MCP server with the user's cj_… API key.
 *
 * Usage:
 *   cojo-mcp                       # read config from ~/.cojournalist/config.json
 *   cojo-mcp --version             # print version, exit
 *   cojo-mcp --help                # print help, exit
 *
 * Config precedence (per key): env var > ~/.cojournalist/config.json.
 * Accepted env vars:
 *   COJOURNALIST_API_URL (default: https://gfmdziplticfoakhrfpt.supabase.co)
 *   COJOURNALIST_API_KEY (required)
 *   COJOURNALIST_SUPABASE_ANON_KEY (required when api_url is a Supabase host)
 */

import { loadConfig } from "./lib/config.ts";
import { runBridge } from "./lib/bridge.ts";
import { VERSION } from "./lib/version.ts";

async function main(): Promise<void> {
  const args = Deno.args;

  if (args.includes("--version") || args.includes("-v")) {
    console.log(`cojo-mcp ${VERSION}`);
    Deno.exit(0);
  }
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`cojo-mcp ${VERSION} — stdio bridge to the coJournalist MCP Edge Function

Runs as a subprocess of your MCP client (Claude Desktop, Cursor, …).
The client speaks newline-delimited JSON-RPC on stdin/stdout; this bridge
forwards each request to https://<api_url>/functions/v1/mcp-server/ with
your cj_… API key.

Configure with the cojo CLI before first use:
  cojo config set api_url=https://gfmdziplticfoakhrfpt.supabase.co
  cojo config set supabase_anon_key=<public anon key>
  cojo config set api_key=cj_<your api key>

Claude Desktop example (~/Library/Application Support/Claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "cojournalist": {
        "command": "cojo-mcp"
      }
    }
  }
`);
    Deno.exit(0);
  }

  let cfg;
  try {
    cfg = loadConfig();
  } catch (e) {
    await Deno.stderr.write(
      new TextEncoder().encode(`cojo-mcp: config error — ${e instanceof Error ? e.message : String(e)}\n`),
    );
    Deno.exit(2);
  }

  try {
    await runBridge(cfg, {
      stdin: Deno.stdin.readable,
      stdout: Deno.stdout.writable,
      stderr: Deno.stderr.writable,
      fetch: fetch,
    });
  } catch (e) {
    await Deno.stderr.write(
      new TextEncoder().encode(`cojo-mcp: fatal — ${e instanceof Error ? e.message : String(e)}\n`),
    );
    Deno.exit(1);
  }
}

if (import.meta.main) {
  await main();
}
