// cojo ingest — ingest URL or text into knowledge base
import { apiFetch, parseArgs, printJSON } from "../lib/client.ts";

function usage(): void {
  console.log(
    [
      "Usage: cojo ingest <subcommand>",
      "",
      "  url <url> [--criteria <text>] [--project <id>]",
      "  text --title <title> [--criteria <text>] [--project <id>] [--file <path>]",
      "",
      "If --file is not given to `text`, body is read from stdin.",
    ].join("\n"),
  );
}

async function readStdin(): Promise<string> {
  const chunks: Uint8Array[] = [];
  for await (const chunk of Deno.stdin.readable) {
    chunks.push(chunk);
  }
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    merged.set(c, off);
    off += c.length;
  }
  return new TextDecoder().decode(merged);
}

export async function run(argv: string[]): Promise<void> {
  const [sub, ...rest] = argv;

  if (!sub || sub === "--help" || sub === "-h") {
    usage();
    if (!sub) Deno.exit(1);
    return;
  }

  const { positional, flags } = parseArgs(rest);

  if (sub === "url") {
    const url = positional[0];
    if (!url) {
      console.error("Usage: cojo ingest url <url> [--criteria] [--project]");
      Deno.exit(1);
    }
    const body: Record<string, unknown> = { kind: "url", url };
    if (typeof flags.criteria === "string") body.criteria = flags.criteria;
    if (typeof flags.project === "string") body.project_id = flags.project;
    const res = await apiFetch("/functions/v1/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    });
    printJSON(res);
    return;
  }

  if (sub === "text") {
    if (typeof flags.title !== "string") {
      console.error("--title is required");
      Deno.exit(1);
    }
    let content: string;
    if (typeof flags.file === "string") {
      content = await Deno.readTextFile(flags.file);
    } else {
      content = await readStdin();
    }
    if (!content.trim()) {
      console.error("No content provided (empty stdin / file)");
      Deno.exit(1);
    }
    const body: Record<string, unknown> = {
      kind: "text",
      title: flags.title,
      text: content,
    };
    if (typeof flags.criteria === "string") body.criteria = flags.criteria;
    if (typeof flags.project === "string") body.project_id = flags.project;
    const res = await apiFetch("/functions/v1/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    });
    printJSON(res);
    return;
  }

  console.error(`Unknown subcommand: ${sub}`);
  usage();
  Deno.exit(1);
}
