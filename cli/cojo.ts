#!/usr/bin/env -S deno run --allow-net --allow-env --allow-read --allow-write
// cojo — coJournalist v2 CLI
// Entry point: dispatches subcommands to commands/<name>.ts

import { VERSION } from "./lib/version.ts";

const SUBCOMMANDS = [
  "config",
  "projects",
  "scouts",
  "units",
  "ingest",
  "export",
] as const;

type Subcommand = typeof SUBCOMMANDS[number];

function printUsage(): void {
  const lines = [
    "cojo — coJournalist v2 CLI",
    "",
    "Usage: cojo <command> [args...]",
    "",
    "Commands:",
    "  config     Manage ~/.cojournalist/config.json (api_url, auth_token)",
    "  projects   List, add, show, delete projects",
    "  scouts     List, add, run, pause, resume, delete scouts",
    "  units      List, show, verify, reject, mark-used, search information units",
    "  ingest     Ingest a URL or raw text into the knowledge base",
    "  export     Export a project (e.g. export claude → markdown for LLM)",
    "",
    "Run `cojo <command> --help` for command-specific usage.",
  ];
  console.log(lines.join("\n"));
}

async function main(): Promise<void> {
  const [cmd, ...rest] = Deno.args;

  if (cmd === "--version" || cmd === "-v") {
    console.log(`cojo ${VERSION}`);
    Deno.exit(0);
  }

  if (!cmd || cmd === "--help" || cmd === "-h" || cmd === "help") {
    printUsage();
    Deno.exit(cmd ? 0 : 1);
  }

  if (!SUBCOMMANDS.includes(cmd as Subcommand)) {
    console.error(`Unknown command: ${cmd}`);
    console.error("");
    printUsage();
    Deno.exit(1);
  }

  try {
    const mod = await import(`./commands/${cmd}.ts`);
    await mod.run(rest);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`Error: ${msg}`);
    Deno.exit(1);
  }
}

if (import.meta.main) {
  await main();
}
