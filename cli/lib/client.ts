// Shared REST client + helpers for cojo

export interface Config {
  api_url?: string;
  auth_token?: string;
}

export function configDir(): string {
  const home = Deno.env.get("HOME");
  if (!home) throw new Error("HOME environment variable is not set");
  return `${home}/.cojournalist`;
}

export function configPath(): string {
  return `${configDir()}/config.json`;
}

export function readConfigFile(): Config {
  try {
    const raw = Deno.readTextFileSync(configPath());
    return JSON.parse(raw) as Config;
  } catch (err) {
    if (err instanceof Deno.errors.NotFound) return {};
    throw err;
  }
}

export function writeConfigFile(cfg: Config): void {
  Deno.mkdirSync(configDir(), { recursive: true });
  Deno.writeTextFileSync(configPath(), JSON.stringify(cfg, null, 2) + "\n");
}

export function loadConfig(): Required<Config> {
  const cfg = readConfigFile();
  if (!cfg.api_url) {
    throw new Error(
      "api_url not set. Run: cojo config set api_url=https://www.cojournalist.ai/api",
    );
  }
  if (!cfg.auth_token) {
    throw new Error(
      "auth_token not set. Generate an API key at https://www.cojournalist.ai → Agents → API → Create key, then run: cojo config set auth_token=<cj_... key>",
    );
  }
  return cfg as Required<Config>;
}

// Rewrite `/functions/v1/<rest>` → `/<rest>` when talking to the pre-cutover
// FastAPI backend (anything that isn't a supabase.co URL). Lets a single
// command set work against both backends during the migration window.
export function resolvePath(path: string, apiUrl: string): string {
  const prefixed = path.startsWith("/") ? path : `/${path}`;
  if (apiUrl.includes("supabase.co")) return prefixed;
  return prefixed.replace(/^\/functions\/v1\//, "/");
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const cfg = loadConfig();
  const url = `${cfg.api_url.replace(/\/$/, "")}${
    resolvePath(path, cfg.api_url)
  }`;
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${cfg.auth_token}`);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const res = await fetch(url, { ...init, headers });
  const text = await res.text();
  let parsed: unknown = text;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      // leave as string
    }
  }

  if (!res.ok) {
    const errMsg =
      parsed && typeof parsed === "object" && parsed !== null &&
        "error" in parsed
        ? (parsed as { error: unknown }).error
        : parsed;
    throw new Error(`API error ${res.status}: ${errMsg}`);
  }

  return parsed as T;
}

// ---- Arg parser (no deps) ------------------------------------------------

export interface ParsedArgs {
  positional: string[];
  flags: Record<string, string | boolean>;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const positional: string[] = [];
  const flags: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const eq = key.indexOf("=");
      if (eq >= 0) {
        flags[key.slice(0, eq)] = key.slice(eq + 1);
      } else {
        const next = argv[i + 1];
        if (next !== undefined && !next.startsWith("--")) {
          flags[key] = next;
          i++;
        } else {
          flags[key] = true;
        }
      }
    } else {
      positional.push(arg);
    }
  }
  return { positional, flags };
}

// ---- Output helpers ------------------------------------------------------

export function isTerminal(): boolean {
  try {
    // Deno 2 exposes isTerminal on the stream
    const stdout = Deno.stdout as unknown as { isTerminal?: () => boolean };
    return typeof stdout.isTerminal === "function" ? stdout.isTerminal() : false;
  } catch {
    return false;
  }
}

export function color(code: string, s: string): string {
  if (!isTerminal()) return s;
  return `\x1b[${code}m${s}\x1b[0m`;
}

export function printTable(
  rows: Record<string, unknown>[],
  cols: string[],
): void {
  if (rows.length === 0) {
    console.log("(no rows)");
    return;
  }
  const cellStr = (v: unknown): string => {
    if (v === null || v === undefined) return "";
    if (typeof v === "string") return v;
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  };

  const widths = cols.map((c) =>
    Math.max(c.length, ...rows.map((r) => cellStr(r[c]).length))
  );

  const sep = widths.map((w) => "-".repeat(w)).join("  ");
  const header = cols
    .map((c, i) => c.padEnd(widths[i]))
    .join("  ");
  console.log(color("1", header));
  console.log(sep);
  for (const r of rows) {
    console.log(
      cols.map((c, i) => cellStr(r[c]).padEnd(widths[i])).join("  "),
    );
  }
}

export function printJSON(v: unknown): void {
  console.log(JSON.stringify(v, null, 2));
}
