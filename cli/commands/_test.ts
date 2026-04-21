// Deno tests for cojo CLI
import { assert, assertEquals, assertStringIncludes } from "jsr:@std/assert";
import {
  configPath,
  printTable,
  readConfigFile,
  resolvePath,
  writeConfigFile,
} from "../lib/client.ts";
import { VERSION } from "../lib/version.ts";

async function withTempHome(
  fn: () => void | Promise<void>,
): Promise<void> {
  const originalHome = Deno.env.get("HOME");
  const tmp = await Deno.makeTempDir({ prefix: "cojo-test-" });
  Deno.env.set("HOME", tmp);
  try {
    await fn();
  } finally {
    if (originalHome === undefined) {
      Deno.env.delete("HOME");
    } else {
      Deno.env.set("HOME", originalHome);
    }
    try {
      await Deno.remove(tmp, { recursive: true });
    } catch {
      /* ignore */
    }
  }
}

Deno.test("config set + get round-trip", async () => {
  await withTempHome(() => {
    const path = configPath();
    assertStringIncludes(path, "/.cojournalist/config.json");

    // Initially absent
    const empty = readConfigFile();
    assertEquals(empty, {});

    // Write
    writeConfigFile({
      api_url: "https://example.test/api",
      auth_token: "abc123token",
    });

    // Read back
    const cfg = readConfigFile();
    assertEquals(cfg.api_url, "https://example.test/api");
    assertEquals(cfg.auth_token, "abc123token");

    // Overwrite single key
    writeConfigFile({ ...cfg, auth_token: "newtoken" });
    const cfg2 = readConfigFile();
    assertEquals(cfg2.api_url, "https://example.test/api");
    assertEquals(cfg2.auth_token, "newtoken");
  });
});

Deno.test("printTable — header + separators + rows", () => {
  // Capture stdout via console.log spy
  const lines: string[] = [];
  const origLog = console.log;
  console.log = (...args: unknown[]) => {
    lines.push(args.map((a) => String(a)).join(" "));
  };
  try {
    printTable(
      [
        { id: "1", name: "alpha", active: true },
        { id: "22", name: "beta", active: false },
      ],
      ["id", "name", "active"],
    );
  } finally {
    console.log = origLog;
  }

  // Header line should include all column names
  const header = lines[0];
  assertStringIncludes(header, "id");
  assertStringIncludes(header, "name");
  assertStringIncludes(header, "active");

  // Separator line should be dashes
  const sep = lines[1];
  assert(/^[-\s]+$/.test(sep), `separator row was: ${sep}`);

  // Data rows present
  assertStringIncludes(lines[2], "alpha");
  assertStringIncludes(lines[3], "beta");
  assertStringIncludes(lines[3], "false");

  // Column widths: id column width = max(2, 2) = 2, so "1 " padded
  assert(lines[2].startsWith("1 "), `row: '${lines[2]}'`);
});

Deno.test("printTable — empty rows prints (no rows)", () => {
  const lines: string[] = [];
  const origLog = console.log;
  console.log = (...args: unknown[]) => {
    lines.push(args.map((a) => String(a)).join(" "));
  };
  try {
    printTable([], ["id", "name"]);
  } finally {
    console.log = origLog;
  }
  assertEquals(lines, ["(no rows)"]);
});

Deno.test("resolvePath — Supabase URL keeps /functions/v1/ prefix", () => {
  const api = "https://gfmdziplticfoakhrfpt.supabase.co/functions/v1";
  assertEquals(resolvePath("/functions/v1/scouts", api), "/functions/v1/scouts");
  assertEquals(
    resolvePath("/functions/v1/units/abc?verified=true", api),
    "/functions/v1/units/abc?verified=true",
  );
});

Deno.test("resolvePath — FastAPI URL strips /functions/v1/ prefix", () => {
  const api = "https://www.cojournalist.ai/api";
  assertEquals(resolvePath("/functions/v1/scouts", api), "/scouts");
  assertEquals(
    resolvePath("/functions/v1/projects/xyz", api),
    "/projects/xyz",
  );
  assertEquals(
    resolvePath("/functions/v1/export-claude?project=1", api),
    "/export-claude?project=1",
  );
});

Deno.test("resolvePath — leaves non-/functions/v1 paths alone on both backends", () => {
  const supa = "https://x.supabase.co/functions/v1";
  const fastapi = "https://www.cojournalist.ai/api";
  assertEquals(resolvePath("/health", supa), "/health");
  assertEquals(resolvePath("/health", fastapi), "/health");
  assertEquals(resolvePath("health", fastapi), "/health"); // bare path normalised
});

Deno.test("VERSION — exports a non-empty string", () => {
  assert(typeof VERSION === "string");
  assert(VERSION.length > 0, "VERSION must not be empty");
});
