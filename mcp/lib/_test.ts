/**
 * Unit tests for the cojo-mcp stdio bridge.
 *
 * Covers the invariants that keep the bridge dumb-forwarder trustworthy:
 *
 *   config:
 *     1. env vars override the config file
 *     2. config file wins over defaults
 *     3. missing api_key → throws
 *     4. Supabase api_url without supabase_anon_key → throws
 *     5. trailing slash on api_url is stripped
 *     6. remoteUrl points at /functions/v1/mcp-server/
 *     7. remoteHeaders includes apikey only when the key is set
 *
 *   forwardOne (per-line forwarder):
 *     8. valid request → forwards body verbatim, returns remote response
 *     9. notification (no id) → posts, returns null (stdout stays quiet)
 *    10. malformed JSON input → JSON-RPC Parse error (no remote call)
 *    11. missing jsonrpc: "2.0" → Invalid Request error
 *    12. transport failure on a request → Internal error with the id
 *    13. transport failure on a notification → stderr only, returns null
 *    14. remote returns non-JSON body → Internal error with the id
 *
 *   runBridge end-to-end:
 *    15. multi-line stdin → one response per request, skipped for notifications
 *    16. trailing line without newline still forwards on stdin close
 */

import { assertEquals, assertRejects, assertStringIncludes } from "https://deno.land/std@0.224.0/assert/mod.ts";
import {
  ConfigDeps,
  loadConfig,
  remoteHeaders,
  remoteUrl,
} from "./config.ts";
import { forwardOne, runBridge } from "./bridge.ts";

// ---------------------------------------------------------------------------
// Config tests
// ---------------------------------------------------------------------------

function makeDeps(
  file: Record<string, unknown> | null,
  env: Record<string, string> = {},
): ConfigDeps {
  return {
    env: (name) => env[name],
    readConfigFile: () => file,
  };
}

Deno.test("config: env var beats config file", () => {
  const cfg = loadConfig(
    makeDeps(
      { api_url: "https://file.example", api_key: "cj_file", supabase_anon_key: "" },
      {
        COJOURNALIST_API_URL: "https://env.example",
        COJOURNALIST_API_KEY: "cj_env",
      },
    ),
  );
  assertEquals(cfg.apiUrl, "https://env.example");
  assertEquals(cfg.apiKey, "cj_env");
});

Deno.test("config: file wins over default when env is empty", () => {
  const cfg = loadConfig(
    makeDeps({ api_url: "https://self-hosted.example", api_key: "cj_file" }),
  );
  assertEquals(cfg.apiUrl, "https://self-hosted.example");
});

Deno.test("config: trailing slash stripped", () => {
  const cfg = loadConfig(
    makeDeps({ api_url: "https://self.example/", api_key: "cj_x" }),
  );
  assertEquals(cfg.apiUrl, "https://self.example");
});

Deno.test("config: throws without api_key", () => {
  let threw = false;
  try {
    loadConfig(makeDeps({ api_url: "https://self.example" }));
  } catch (e) {
    threw = true;
    assertStringIncludes((e as Error).message, "api_key");
  }
  if (!threw) throw new Error("expected loadConfig to throw without api_key");
});

Deno.test("config: Supabase url without anon key → throws", () => {
  let threw = false;
  try {
    loadConfig(
      makeDeps({ api_url: "https://x.supabase.co", api_key: "cj_x" }),
    );
  } catch (e) {
    threw = true;
    assertStringIncludes((e as Error).message, "supabase_anon_key");
  }
  if (!threw) throw new Error("expected loadConfig to throw for Supabase url without anon key");
});

Deno.test("config: Supabase url with anon key → loads", () => {
  const cfg = loadConfig(
    makeDeps({
      api_url: "https://x.supabase.co",
      api_key: "cj_x",
      supabase_anon_key: "anon_123",
    }),
  );
  assertEquals(cfg.apiUrl, "https://x.supabase.co");
  assertEquals(cfg.supabaseAnonKey, "anon_123");
});

Deno.test("remoteUrl: appends /functions/v1/mcp-server/", () => {
  const url = remoteUrl({
    apiUrl: "https://x.supabase.co",
    apiKey: "cj_x",
    supabaseAnonKey: "a",
  });
  assertEquals(url, "https://x.supabase.co/functions/v1/mcp-server/");
});

Deno.test("remoteHeaders: omits apikey when not set", () => {
  const h = remoteHeaders({ apiUrl: "https://x.example", apiKey: "cj_x", supabaseAnonKey: "" });
  assertEquals(h.Authorization, "Bearer cj_x");
  assertEquals(h.apikey, undefined);
});

Deno.test("remoteHeaders: sends apikey for Supabase", () => {
  const h = remoteHeaders({
    apiUrl: "https://x.supabase.co",
    apiKey: "cj_x",
    supabaseAnonKey: "anon_123",
  });
  assertEquals(h.apikey, "anon_123");
});

// ---------------------------------------------------------------------------
// forwardOne tests
// ---------------------------------------------------------------------------

const CFG = {
  apiUrl: "https://x.supabase.co",
  apiKey: "cj_test",
  supabaseAnonKey: "anon_test",
};

function stubFetchOk(body: string, status = 200): typeof fetch {
  const captured: Array<{ url: string; init: RequestInit | undefined }> = [];
  const stub = (async (input: string | URL | Request, init?: RequestInit) => {
    captured.push({ url: String(input), init });
    return new Response(body, { status });
  }) as unknown as typeof fetch;
  (stub as unknown as { captured: typeof captured }).captured = captured;
  return stub;
}

function stubFetchReject(msg: string): typeof fetch {
  return (async () => {
    throw new Error(msg);
  }) as unknown as typeof fetch;
}

function discardStream(): WritableStream<Uint8Array> {
  return new WritableStream({ write() {} });
}

function captureStream(): { stream: WritableStream<Uint8Array>; chunks: string[] } {
  const chunks: string[] = [];
  const decoder = new TextDecoder();
  const stream = new WritableStream<Uint8Array>({
    write(chunk) {
      chunks.push(decoder.decode(chunk));
    },
  });
  return { stream, chunks };
}

Deno.test("forwardOne: request → returns remote body verbatim", async () => {
  const remote = `{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}`;
  const fetchStub = stubFetchOk(remote);
  const out = await forwardOne(
    `{"jsonrpc":"2.0","id":1,"method":"initialize"}`,
    CFG,
    { fetch: fetchStub, stderr: discardStream() },
  );
  assertEquals(out, remote);
  const captured = (fetchStub as unknown as {
    captured: Array<{ url: string; init: RequestInit }>;
  }).captured;
  assertEquals(captured[0].url, "https://x.supabase.co/functions/v1/mcp-server/");
  const headers = captured[0].init.headers as Record<string, string>;
  assertEquals(headers.Authorization, "Bearer cj_test");
  assertEquals(headers.apikey, "anon_test");
});

Deno.test("forwardOne: notification → returns null (no stdout)", async () => {
  const fetchStub = stubFetchOk("", 202);
  const out = await forwardOne(
    `{"jsonrpc":"2.0","method":"notifications/initialized"}`,
    CFG,
    { fetch: fetchStub, stderr: discardStream() },
  );
  assertEquals(out, null);
});

Deno.test("forwardOne: parse error → JSON-RPC Parse error with id=null", async () => {
  const fetchStub = stubFetchOk(`{"should":"not be called"}`);
  const out = await forwardOne(`not-json`, CFG, { fetch: fetchStub, stderr: discardStream() });
  const parsed = JSON.parse(out!);
  assertEquals(parsed.jsonrpc, "2.0");
  assertEquals(parsed.id, null);
  assertEquals(parsed.error.code, -32700);
});

Deno.test("forwardOne: wrong jsonrpc version → Invalid Request", async () => {
  const fetchStub = stubFetchOk(`{}`);
  const out = await forwardOne(
    `{"jsonrpc":"1.0","id":5,"method":"x"}`,
    CFG,
    { fetch: fetchStub, stderr: discardStream() },
  );
  const parsed = JSON.parse(out!);
  assertEquals(parsed.id, 5);
  assertEquals(parsed.error.code, -32600);
});

Deno.test("forwardOne: transport failure on request → Internal error with id", async () => {
  const fetchStub = stubFetchReject("network down");
  const out = await forwardOne(
    `{"jsonrpc":"2.0","id":7,"method":"tools/list"}`,
    CFG,
    { fetch: fetchStub, stderr: discardStream() },
  );
  const parsed = JSON.parse(out!);
  assertEquals(parsed.id, 7);
  assertEquals(parsed.error.code, -32603);
  assertStringIncludes(parsed.error.message, "network down");
});

Deno.test("forwardOne: transport failure on notification → stderr, no stdout", async () => {
  const fetchStub = stubFetchReject("offline");
  const { stream, chunks } = captureStream();
  const out = await forwardOne(
    `{"jsonrpc":"2.0","method":"notifications/cancelled"}`,
    CFG,
    { fetch: fetchStub, stderr: stream },
  );
  assertEquals(out, null);
  assertEquals(chunks.length, 1);
  assertStringIncludes(chunks[0], "offline");
});

Deno.test("forwardOne: non-JSON remote body → Internal error with id", async () => {
  const fetchStub = stubFetchOk("<html>502 Bad Gateway</html>", 502);
  const out = await forwardOne(
    `{"jsonrpc":"2.0","id":9,"method":"tools/call"}`,
    CFG,
    { fetch: fetchStub, stderr: discardStream() },
  );
  const parsed = JSON.parse(out!);
  assertEquals(parsed.id, 9);
  assertEquals(parsed.error.code, -32603);
});

// ---------------------------------------------------------------------------
// runBridge integration
// ---------------------------------------------------------------------------

function stdinFrom(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const line of lines) controller.enqueue(encoder.encode(line));
      controller.close();
    },
  });
}

Deno.test("runBridge: request + notification + request → two stdout lines", async () => {
  const responses = [
    `{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}`,
    `{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}`,
  ];
  let call = 0;
  const fetchStub = (async () => {
    const body = responses[call++] ?? "";
    return new Response(body, { status: 200 });
  }) as unknown as typeof fetch;

  const stdin = stdinFrom([
    `{"jsonrpc":"2.0","id":1,"method":"initialize"}\n`,
    `{"jsonrpc":"2.0","method":"notifications/initialized"}\n`,
    `{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n`,
  ]);
  const out = captureStream();

  await runBridge(CFG, {
    stdin,
    stdout: out.stream,
    stderr: discardStream(),
    fetch: fetchStub,
  });

  const lines = out.chunks.join("").trim().split("\n");
  assertEquals(lines.length, 2);
  assertEquals(JSON.parse(lines[0]).id, 1);
  assertEquals(JSON.parse(lines[1]).id, 2);
});

Deno.test("runBridge: trailing line without newline still forwards", async () => {
  const fetchStub = stubFetchOk(`{"jsonrpc":"2.0","id":42,"result":{"ok":true}}`);
  const stdin = stdinFrom([
    `{"jsonrpc":"2.0","id":42,"method":"tools/call"}`,
  ]);
  const out = captureStream();

  await runBridge(CFG, {
    stdin,
    stdout: out.stream,
    stderr: discardStream(),
    fetch: fetchStub,
  });

  const text = out.chunks.join("").trim();
  assertEquals(JSON.parse(text).id, 42);
});

// assertRejects import is retained for future tests that need it; suppress
// unused-import lint by referencing it in a noop.
void assertRejects;
