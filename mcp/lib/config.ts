/**
 * Config loader for the cojo-mcp stdio bridge.
 *
 * Reuses the same ~/.cojournalist/config.json as the cojo CLI so users only
 * configure once. All three keys (api_url, api_key, supabase_anon_key) can
 * also be overridden via environment variables at launch time — convenient
 * for Claude Desktop, where the user's `env:` block in the client config
 * sets them per-connection.
 *
 * Precedence: env var > config file > default.
 */

export interface BridgeConfig {
  apiUrl: string;
  apiKey: string;
  supabaseAnonKey: string;
}

const DEFAULT_API_URL = "https://gfmdziplticfoakhrfpt.supabase.co";

function expandHome(p: string): string {
  if (!p.startsWith("~")) return p;
  const home = Deno.env.get("HOME") ?? Deno.env.get("USERPROFILE") ?? "";
  return home ? `${home}${p.slice(1)}` : p;
}

export interface ReadableFs {
  readTextFileSync?: (path: string) => string;
}

export interface ConfigDeps {
  env: (name: string) => string | undefined;
  readConfigFile: () => Record<string, unknown> | null;
}

export function defaultDeps(configPath = "~/.cojournalist/config.json"): ConfigDeps {
  return {
    env: (name: string) => Deno.env.get(name) ?? undefined,
    readConfigFile: () => {
      try {
        const text = Deno.readTextFileSync(expandHome(configPath));
        const parsed = JSON.parse(text);
        return parsed && typeof parsed === "object" ? parsed : null;
      } catch {
        return null;
      }
    },
  };
}

export function loadConfig(deps: ConfigDeps = defaultDeps()): BridgeConfig {
  const fileCfg = deps.readConfigFile() ?? {};
  const pick = (key: string, envName: string, fallback = ""): string => {
    const fromEnv = deps.env(envName);
    if (fromEnv && fromEnv.trim()) return fromEnv.trim();
    const fromFile = fileCfg[key];
    if (typeof fromFile === "string" && fromFile.trim()) return fromFile.trim();
    return fallback;
  };

  const apiUrl = pick("api_url", "COJOURNALIST_API_URL", DEFAULT_API_URL).replace(/\/$/, "");
  const apiKey = pick("api_key", "COJOURNALIST_API_KEY");
  const supabaseAnonKey = pick("supabase_anon_key", "COJOURNALIST_SUPABASE_ANON_KEY");

  if (!apiKey) {
    throw new Error(
      "Missing api_key. Set it via `cojo config set api_key=cj_...` or export " +
        "COJOURNALIST_API_KEY before launching the bridge.",
    );
  }
  if (apiUrl.includes("supabase.co") && !supabaseAnonKey) {
    throw new Error(
      "Supabase api_url requires supabase_anon_key. Set it via " +
        "`cojo config set supabase_anon_key=...` or export " +
        "COJOURNALIST_SUPABASE_ANON_KEY.",
    );
  }
  return { apiUrl, apiKey, supabaseAnonKey };
}

export function remoteUrl(cfg: BridgeConfig): string {
  // Kong routes /functions/v1/mcp-server to the deployed EF. Non-Supabase
  // custom deployments are expected to expose the same path under their
  // own host (or front it via a reverse proxy).
  if (cfg.apiUrl.includes("supabase.co")) {
    return `${cfg.apiUrl}/functions/v1/mcp-server/`;
  }
  return `${cfg.apiUrl}/functions/v1/mcp-server/`;
}

export function remoteHeaders(cfg: BridgeConfig): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": `Bearer ${cfg.apiKey}`,
  };
  if (cfg.supabaseAnonKey) headers["apikey"] = cfg.supabaseAnonKey;
  return headers;
}
