// cojo export — export project context
import { apiFetch, parseArgs } from "../lib/client.ts";

function usage(): void {
  console.log(
    [
      "Usage: cojo export <subcommand>",
      "",
      "  claude [--project <id>] [--limit N]",
      "",
      "Prints markdown to stdout. Pipe to pbcopy / clipboard tools as needed.",
    ].join("\n"),
  );
}

export async function run(argv: string[]): Promise<void> {
  const [sub, ...rest] = argv;

  if (!sub || sub === "--help" || sub === "-h") {
    usage();
    if (!sub) Deno.exit(1);
    return;
  }

  if (sub !== "claude") {
    console.error(`Unknown subcommand: ${sub}`);
    usage();
    Deno.exit(1);
  }

  const { flags } = parseArgs(rest);
  const params = new URLSearchParams();
  if (typeof flags.project === "string") params.set("project_id", flags.project);
  if (typeof flags.limit === "string") params.set("limit", flags.limit);
  const qs = params.toString();

  const data = await apiFetch<string | { markdown?: string; content?: string }>(
    `/functions/v1/export-claude${qs ? `?${qs}` : ""}`,
  );

  if (typeof data === "string") {
    console.log(data);
    return;
  }
  const md = (data && typeof data === "object" && (data.markdown ?? data.content)) ??
    JSON.stringify(data, null, 2);
  console.log(md);
}
