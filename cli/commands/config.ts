// cojo config — manage ~/.cojournalist/config.json
import {
  configPath,
  readConfigFile,
  writeConfigFile,
} from "../lib/client.ts";

const VALID_KEYS = ["api_url", "auth_token"] as const;
type Key = typeof VALID_KEYS[number];

function usage(): void {
  console.log(
    [
      "Usage: cojo config <subcommand>",
      "",
      "  get <key>            Print value of api_url | auth_token",
      "  set <key>=<value>    Write key/value to config",
      "  show                 Show the full config (auth_token redacted)",
      "",
      `Config file: ${configPath()}`,
    ].join("\n"),
  );
}

function redact(token: string): string {
  if (!token) return "";
  if (token.length <= 8) return "****";
  return `${token.slice(0, 4)}...${token.slice(-4)}`;
}

export function run(argv: string[]): void {
  const [sub, ...rest] = argv;

  if (!sub || sub === "--help" || sub === "-h") {
    usage();
    if (!sub) Deno.exit(1);
    return;
  }

  if (sub === "show") {
    const cfg = readConfigFile();
    const display = {
      api_url: cfg.api_url ?? "(unset)",
      auth_token: cfg.auth_token ? redact(cfg.auth_token) : "(unset)",
    };
    console.log(JSON.stringify(display, null, 2));
    return;
  }

  if (sub === "get") {
    const key = rest[0];
    if (!key || !VALID_KEYS.includes(key as Key)) {
      console.error(`Usage: cojo config get <${VALID_KEYS.join("|")}>`);
      Deno.exit(1);
    }
    const cfg = readConfigFile();
    const val = cfg[key as Key];
    if (val === undefined) {
      console.error(`${key} is not set`);
      Deno.exit(1);
    }
    console.log(val);
    return;
  }

  if (sub === "set") {
    const pair = rest.join(" ");
    const eq = pair.indexOf("=");
    if (eq < 0) {
      console.error("Usage: cojo config set <key>=<value>");
      Deno.exit(1);
    }
    const key = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    if (!VALID_KEYS.includes(key as Key)) {
      console.error(
        `Unknown key: ${key}. Valid keys: ${VALID_KEYS.join(", ")}`,
      );
      Deno.exit(1);
    }
    if (!value) {
      console.error("Value cannot be empty");
      Deno.exit(1);
    }
    const cfg = readConfigFile();
    cfg[key as Key] = value;
    writeConfigFile(cfg);
    console.log(`Set ${key}`);
    return;
  }

  console.error(`Unknown subcommand: ${sub}`);
  usage();
  Deno.exit(1);
}
