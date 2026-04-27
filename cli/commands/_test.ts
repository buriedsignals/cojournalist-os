// Deno tests for cojo CLI
import {
  assert,
  assertEquals,
  assertRejects,
  assertStringIncludes,
  assertThrows,
} from "jsr:@std/assert";
import {
  apiFetch,
  configPath,
  loadConfig,
  printTable,
  readConfigFile,
  resolvePath,
  unwrapItems,
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

Deno.test("resolvePath — bare Supabase URL keeps /functions/v1/ prefix", () => {
  const api = "https://gfmdziplticfoakhrfpt.supabase.co";
  assertEquals(
    resolvePath("/functions/v1/scouts", api),
    "/functions/v1/scouts",
  );
  assertEquals(
    resolvePath("/functions/v1/units/abc?verified=true", api),
    "/functions/v1/units/abc?verified=true",
  );
});

Deno.test("resolvePath — base URL with /functions/v1 strips duplicate prefix", () => {
  const hosted = "https://www.cojournalist.ai/functions/v1";
  const supabase = "https://gfmdziplticfoakhrfpt.supabase.co/functions/v1";
  assertEquals(resolvePath("/functions/v1/scouts", hosted), "/scouts");
  assertEquals(resolvePath("/functions/v1/scouts", supabase), "/scouts");
});

Deno.test("resolvePath — FastAPI URL strips /functions/v1/ prefix", () => {
  const api = "https://www.cojournalist.ai/api";
  assertEquals(resolvePath("/functions/v1/scouts", api), "/scouts");
  assertEquals(
    resolvePath("/functions/v1/projects/xyz", api),
    "/projects/xyz",
  );
  assertEquals(
    resolvePath("/functions/v1/units/search", api),
    "/units/search",
  );
});

Deno.test("resolvePath — leaves non-/functions/v1 paths alone on both backends", () => {
  const supa = "https://x.supabase.co/functions/v1";
  const fastapi = "https://www.cojournalist.ai/api";
  assertEquals(resolvePath("/health", supa), "/health");
  assertEquals(resolvePath("/health", fastapi), "/health");
  assertEquals(resolvePath("health", fastapi), "/health");
});

Deno.test("unwrapItems — accepts Edge items envelopes and legacy data envelopes", () => {
  assertEquals(unwrapItems<{ id: string }>([{ id: "array" }]), [{
    id: "array",
  }]);
  assertEquals(unwrapItems<{ id: string }>({ items: [{ id: "items" }] }), [{
    id: "items",
  }]);
  assertEquals(unwrapItems<{ id: string }>({ data: [{ id: "data" }] }), [{
    id: "data",
  }]);
  assertEquals(unwrapItems<{ id: string }>({ ok: true }), []);
});

Deno.test("VERSION — exports a non-empty string", () => {
  assert(typeof VERSION === "string");
  assert(VERSION.length > 0, "VERSION must not be empty");
});

// ---- api-key / supabase_anon_key auth path ------------------------------

Deno.test("loadConfig — accepts api_key only (no auth_token required)", async () => {
  await withTempHome(() => {
    writeConfigFile({
      api_url: "https://example.test/api",
      api_key: "cj_test_key",
    });
    const cfg = loadConfig();
    assertEquals(cfg.api_url, "https://example.test/api");
    assertEquals(cfg.api_key, "cj_test_key");
    assertEquals(cfg.auth_token, undefined);
  });
});

Deno.test("loadConfig — throws if neither api_key nor auth_token set", async () => {
  await withTempHome(() => {
    writeConfigFile({ api_url: "https://example.test/api" });
    assertThrows(() => loadConfig(), Error, "No credential set");
  });
});

Deno.test("loadConfig — throws if api_url missing", async () => {
  await withTempHome(() => {
    writeConfigFile({ api_key: "cj_test_key" });
    assertThrows(() => loadConfig(), Error, "api_url not set");
  });
});

Deno.test("apiFetch — uses api_key over auth_token, sends apikey header for Supabase", async () => {
  await withTempHome(async () => {
    // Convention: api_url is the bare Supabase host. The /functions/v1/ prefix
    // lives in the path so resolvePath can strip it for the FastAPI backend.
    writeConfigFile({
      api_url: "https://x.supabase.co",
      auth_token: "legacy_token_should_be_ignored",
      api_key: "cj_preferred",
      supabase_anon_key: "anon_test_key",
    });

    let observed:
      | { url: string; auth: string | null; apikey: string | null }
      | null = null;
    const origFetch = globalThis.fetch;
    globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      const headers = new Headers(init?.headers);
      observed = {
        url,
        auth: headers.get("Authorization"),
        apikey: headers.get("apikey"),
      };
      return Promise.resolve(
        new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    try {
      await apiFetch("/functions/v1/units?limit=1");
    } finally {
      globalThis.fetch = origFetch;
    }

    assert(observed !== null, "fetch was not called");
    const obs = observed as unknown as {
      url: string;
      auth: string;
      apikey: string;
    };
    assertStringIncludes(obs.url, "x.supabase.co/functions/v1/units");
    assertEquals(obs.auth, "Bearer cj_preferred");
    assertEquals(obs.apikey, "anon_test_key");
  });
});

Deno.test("apiFetch — sends apikey header for hosted Edge Functions when configured", async () => {
  await withTempHome(async () => {
    writeConfigFile({
      api_url: "https://www.cojournalist.ai/functions/v1",
      api_key: "cj_preferred",
      supabase_anon_key: "anon_test_key",
    });

    let observed:
      | { url: string; auth: string | null; apikey: string | null }
      | null = null;
    const origFetch = globalThis.fetch;
    globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      const headers = new Headers(init?.headers);
      observed = {
        url,
        auth: headers.get("Authorization"),
        apikey: headers.get("apikey"),
      };
      return Promise.resolve(
        new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    try {
      await apiFetch("/functions/v1/units?limit=1");
    } finally {
      globalThis.fetch = origFetch;
    }

    assert(observed !== null, "fetch was not called");
    const obs = observed as unknown as {
      url: string;
      auth: string;
      apikey: string;
    };
    assertStringIncludes(obs.url, "www.cojournalist.ai/functions/v1/units");
    assertEquals(obs.auth, "Bearer cj_preferred");
    assertEquals(obs.apikey, "anon_test_key");
  });
});

Deno.test("apiFetch — falls back to auth_token when api_key absent, omits apikey header for non-Supabase", async () => {
  await withTempHome(async () => {
    writeConfigFile({
      api_url: "https://www.cojournalist.ai/api",
      auth_token: "cj_legacy",
    });

    let observed:
      | { url: string; auth: string | null; apikey: string | null }
      | null = null;
    const origFetch = globalThis.fetch;
    globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      const headers = new Headers(init?.headers);
      observed = {
        url,
        auth: headers.get("Authorization"),
        apikey: headers.get("apikey"),
      };
      return Promise.resolve(
        new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    try {
      await apiFetch("/functions/v1/units?limit=1");
    } finally {
      globalThis.fetch = origFetch;
    }

    assert(observed !== null);
    const obs = observed as unknown as {
      url: string;
      auth: string;
      apikey: string | null;
    };
    assertStringIncludes(obs.url, "www.cojournalist.ai/api/units");
    assertEquals(obs.auth, "Bearer cj_legacy");
    assertEquals(obs.apikey, null);
  });
});

Deno.test("apiFetch — surfaces non-2xx as a thrown Error", async () => {
  await withTempHome(async () => {
    writeConfigFile({
      api_url: "https://x.supabase.co",
      api_key: "cj_test",
      supabase_anon_key: "anon",
    });

    const origFetch = globalThis.fetch;
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify({ error: "nope" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )) as typeof fetch;

    try {
      await assertRejects(
        () => apiFetch("/functions/v1/units"),
        Error,
        "401",
      );
    } finally {
      globalThis.fetch = origFetch;
    }
  });
});
