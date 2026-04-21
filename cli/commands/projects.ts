// cojo projects — manage projects
import { apiFetch, parseArgs, printJSON, printTable } from "../lib/client.ts";

function usage(): void {
  console.log(
    [
      "Usage: cojo projects <subcommand>",
      "",
      "  list",
      "  add --name <name> [--description <text>] [--visibility private|team]",
      "  show <id>",
      "  delete <id>",
    ].join("\n"),
  );
}

interface Project {
  id: string;
  name: string;
  description?: string;
  visibility?: string;
  created_at?: string;
}

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
      const data = await apiFetch<Project[] | { data: Project[] }>(
        "/functions/v1/projects",
      );
      const rows = Array.isArray(data) ? data : (data.data ?? []);
      printTable(
        rows as unknown as Record<string, unknown>[],
        ["id", "name", "description", "created_at"],
      );
      return;
    }
    case "add": {
      if (!flags.name || typeof flags.name !== "string") {
        console.error("--name is required");
        Deno.exit(1);
      }
      const body: Record<string, unknown> = { name: flags.name };
      if (typeof flags.description === "string") {
        body.description = flags.description;
      }
      if (typeof flags.visibility === "string") {
        body.visibility = flags.visibility;
      }
      const created = await apiFetch<Project>("/functions/v1/projects", {
        method: "POST",
        body: JSON.stringify(body),
      });
      printJSON(created);
      return;
    }
    case "show": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo projects show <id>");
        Deno.exit(1);
      }
      const data = await apiFetch<Project>(`/functions/v1/projects/${id}`);
      printJSON(data);
      return;
    }
    case "delete": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo projects delete <id>");
        Deno.exit(1);
      }
      await apiFetch(`/functions/v1/projects/${id}`, { method: "DELETE" });
      console.log(`Deleted project ${id}`);
      return;
    }
    default:
      console.error(`Unknown subcommand: ${sub}`);
      usage();
      Deno.exit(1);
  }
}
