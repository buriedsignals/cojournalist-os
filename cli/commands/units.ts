// cojo units — information unit management
import { apiFetch, parseArgs, printJSON, printTable } from "../lib/client.ts";

function usage(): void {
  console.log(
    [
      "Usage: cojo units <subcommand>",
      "",
      "  list [--project <id>] [--since 7d|30d] [--verified] [--used]",
      "       [--offset N] [--limit N]",
      "  show <id>",
      "  verify <id> [--notes <text>] [--by <name>]",
      "  reject <id> [--notes <text>]",
      "  mark-used <id> [--url <published-url>]",
      "  delete <id>",
      "  search --query \"<text>\" [--project <id>] [--limit N]",
    ].join("\n"),
  );
}

interface Unit {
  id: string;
  statement?: string;
  type?: string;
  source_url?: string;
  entities?: unknown;
  verified?: boolean;
  verified_by?: string;
  verification_notes?: string;
  used_in_article?: boolean;
  used_at?: string;
  used_in_url?: string;
}

function toQuery(params: Record<string, string | number | boolean>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
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
      const params: Record<string, string | number | boolean> = {};
      if (typeof flags.project === "string") params.project_id = flags.project;
      if (typeof flags.since === "string") params.since = flags.since;
      if (flags.verified === true) params.verified = "true";
      if (flags.used === true) params.used = "true";
      if (typeof flags.offset === "string") params.offset = flags.offset;
      if (typeof flags.limit === "string") params.limit = flags.limit;

      const data = await apiFetch<Unit[] | { data: Unit[] }>(
        `/functions/v1/units${toQuery(params)}`,
      );
      const rows = Array.isArray(data) ? data : (data.data ?? []);
      printTable(
        rows as unknown as Record<string, unknown>[],
        ["id", "type", "statement", "verified", "used_in_article"],
      );
      return;
    }
    case "show": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo units show <id>");
        Deno.exit(1);
      }
      const unit = await apiFetch<Unit>(`/functions/v1/units/${id}`);
      const lines = [
        `ID:           ${unit.id}`,
        `Type:         ${unit.type ?? "(unset)"}`,
        `Statement:    ${unit.statement ?? "(unset)"}`,
        `Source URL:   ${unit.source_url ?? "(unset)"}`,
        `Entities:     ${
          unit.entities ? JSON.stringify(unit.entities) : "(none)"
        }`,
        `Verified:     ${unit.verified ?? false}${
          unit.verified_by ? ` by ${unit.verified_by}` : ""
        }`,
        `  Notes:      ${unit.verification_notes ?? "(none)"}`,
        `Used:         ${unit.used_in_article ?? false}${
          unit.used_at ? ` at ${unit.used_at}` : ""
        }`,
        `  URL:        ${unit.used_in_url ?? "(none)"}`,
      ];
      console.log(lines.join("\n"));
      return;
    }
    case "verify": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo units verify <id> [--notes] [--by]");
        Deno.exit(1);
      }
      const body: Record<string, unknown> = { verified: true };
      if (typeof flags.notes === "string") {
        body.verification_notes = flags.notes;
      }
      if (typeof flags.by === "string") body.verified_by = flags.by;
      const res = await apiFetch(`/functions/v1/units/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      printJSON(res);
      return;
    }
    case "reject": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo units reject <id> [--notes]");
        Deno.exit(1);
      }
      const body: Record<string, unknown> = { verified: false };
      if (typeof flags.notes === "string") {
        body.verification_notes = flags.notes;
      }
      const res = await apiFetch(`/functions/v1/units/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      printJSON(res);
      return;
    }
    case "mark-used": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo units mark-used <id> [--url]");
        Deno.exit(1);
      }
      const body: Record<string, unknown> = {
        used_in_article: true,
        used_at: new Date().toISOString(),
      };
      if (typeof flags.url === "string") body.used_in_url = flags.url;
      const res = await apiFetch(`/functions/v1/units/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      printJSON(res);
      return;
    }
    case "delete": {
      const id = positional[0];
      if (!id) {
        console.error("Usage: cojo units delete <id>");
        Deno.exit(1);
      }
      await apiFetch(`/functions/v1/units/${id}`, { method: "DELETE" });
      console.log(`Deleted unit ${id}`);
      return;
    }
    case "search": {
      if (typeof flags.query !== "string") {
        console.error("--query is required");
        Deno.exit(1);
      }
      const body: Record<string, unknown> = { query: flags.query };
      if (typeof flags.project === "string") body.project_id = flags.project;
      if (typeof flags.limit === "string") {
        body.limit = Number(flags.limit);
      }
      const data = await apiFetch<Unit[] | { data: Unit[] }>(
        "/functions/v1/units/search",
        { method: "POST", body: JSON.stringify(body) },
      );
      const rows = Array.isArray(data) ? data : (data.data ?? []);
      printTable(
        rows as unknown as Record<string, unknown>[],
        ["id", "type", "statement", "source_url"],
      );
      return;
    }
    default:
      console.error(`Unknown subcommand: ${sub}`);
      usage();
      Deno.exit(1);
  }
}
