// cojo scouts — manage scouts
import { apiFetch, parseArgs, printJSON, printTable } from "../lib/client.ts";

function usage(): void {
  console.log(
    [
      "Usage: cojo scouts <subcommand>",
      "",
      "  list",
      "  add --name <name> --type <web|pulse|social|civic> [--url <url>]",
      "                   [--criteria <text>] [--project <id>] [--cron <expr>]",
      "  run <id>",
      "  pause <id>",
      "  resume <id>",
      "  delete <id>",
    ].join("\n"),
  );
}

interface Scout {
  id: string;
  name: string;
  type: string;
  is_active: boolean;
  consecutive_failures?: number;
}

const VALID_TYPES = ["web", "pulse", "social", "civic"];

export async function run(argv: string[]): Promise<void> {
  const [sub, ...rest] = argv;

  if (!sub || sub === "--help" || sub === "-h") {
    usage();
    if (!sub) Deno.exit(1);
    return;
  }

  const { positional, flags } = parseArgs(rest);

  switch (sub) {
    case "list": {
      const data = await apiFetch<Scout[] | { data: Scout[] }>(
        "/functions/v1/scouts",
      );
      const rows = Array.isArray(data) ? data : (data.data ?? []);
      printTable(
        rows as unknown as Record<string, unknown>[],
        ["id", "name", "type", "is_active", "consecutive_failures"],
      );
      return;
    }
    case "add": {
      if (typeof flags.name !== "string") {
        console.error("--name is required");
        Deno.exit(1);
      }
      if (
        typeof flags.type !== "string" || !VALID_TYPES.includes(flags.type)
      ) {
        console.error(`--type must be one of: ${VALID_TYPES.join(", ")}`);
        Deno.exit(1);
      }
      const body: Record<string, unknown> = {
        name: flags.name,
        type: flags.type,
      };
      if (typeof flags.url === "string") body.url = flags.url;
      if (typeof flags.criteria === "string") body.criteria = flags.criteria;
      if (typeof flags.project === "string") body.project_id = flags.project;
      if (typeof flags.cron === "string") body.cron = flags.cron;

      const created = await apiFetch<Scout>("/functions/v1/scouts", {
        method: "POST",
        body: JSON.stringify(body),
      });
      printJSON(created);
      return;
    }
    case "run":
    case "pause":
    case "resume": {
      const id = positional[0];
      if (!id) {
        console.error(`Usage: cojo scouts ${sub} <id>`);
        Deno.exit(1);
      }
      const res = await apiFetch(`/functions/v1/scouts/${id}/${sub}`, {
        method: "POST",
      });
      printJSON(res);
      return;
    }
    case "delete": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo scouts delete <id>");
        Deno.exit(1);
      }
      await apiFetch(`/functions/v1/scouts/${id}`, { method: "DELETE" });
      console.log(`Deleted scout ${id}`);
      return;
    }
    default:
      console.error(`Unknown subcommand: ${sub}`);
      usage();
      Deno.exit(1);
  }
}
