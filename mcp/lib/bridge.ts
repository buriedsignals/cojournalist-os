/**
 * MCP stdio ↔ HTTP bridge core.
 *
 * Reads newline-delimited JSON-RPC 2.0 messages from stdin, forwards each
 * one (unchanged) to the remote coJournalist MCP Edge Function over HTTPS,
 * and writes the response back to stdout as newline-delimited JSON. Errors
 * from the forwarder become JSON-RPC error responses (stdout) so the MCP
 * client never sees broken framing. Non-protocol diagnostics go to stderr.
 *
 * The bridge is deliberately dumb — it does not parse, mutate, or validate
 * the JSON-RPC payloads. That keeps it forward-compatible with MCP protocol
 * updates and with new tools added to the remote server without needing a
 * bridge release. Its only jobs are transport translation + auth injection.
 */

import { BridgeConfig, remoteHeaders, remoteUrl } from "./config.ts";

export interface BridgeDeps {
  stdin: ReadableStream<Uint8Array>;
  stdout: WritableStream<Uint8Array>;
  stderr: WritableStream<Uint8Array>;
  fetch: typeof fetch;
  /** Signal stops the bridge loop (unit tests pass one to exit cleanly). */
  signal?: AbortSignal;
}

interface JsonRpcIdEnvelope {
  jsonrpc?: string;
  id?: unknown;
  method?: unknown;
}

async function writeLine(
  stream: WritableStream<Uint8Array>,
  line: string,
): Promise<void> {
  const writer = stream.getWriter();
  try {
    await writer.write(new TextEncoder().encode(line.endsWith("\n") ? line : `${line}\n`));
  } finally {
    writer.releaseLock();
  }
}

async function writeErrLine(stream: WritableStream<Uint8Array>, msg: string): Promise<void> {
  await writeLine(stream, msg);
}

function rpcErrorFor(id: unknown, code: number, message: string): string {
  return JSON.stringify({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

function isNotification(env: JsonRpcIdEnvelope): boolean {
  // JSON-RPC 2.0: a notification has no `id`. Request objects that omit `id`
  // don't expect a response — don't forward the remote's body back.
  return env.id === undefined || env.id === null;
}

export async function forwardOne(
  line: string,
  cfg: BridgeConfig,
  deps: Pick<BridgeDeps, "fetch" | "stderr">,
): Promise<string | null> {
  const trimmed = line.trim();
  if (!trimmed) return null;

  let parsed: JsonRpcIdEnvelope;
  try {
    parsed = JSON.parse(trimmed) as JsonRpcIdEnvelope;
  } catch {
    // Malformed input — per JSON-RPC, reply with a Parse error and no id.
    return rpcErrorFor(null, -32700, "Parse error: invalid JSON");
  }
  if (parsed.jsonrpc !== "2.0") {
    return rpcErrorFor(parsed.id ?? null, -32600, "Invalid Request: jsonrpc must be 2.0");
  }

  try {
    const res = await deps.fetch(remoteUrl(cfg), {
      method: "POST",
      headers: remoteHeaders(cfg),
      body: trimmed,
    });
    const text = await res.text();

    // Notifications (no id) — the remote may reply 202 with an empty body,
    // or the remote may return a response body anyway. Per JSON-RPC, we
    // must NOT write a response back to stdout for notifications.
    if (isNotification(parsed)) {
      if (!res.ok) {
        await writeErrLine(
          deps.stderr,
          `cojo-mcp: remote ${res.status} on notification ${String(parsed.method)}: ${text.slice(0, 400)}`,
        );
      }
      return null;
    }

    // Request — we need a response. If the body parses as JSON-RPC,
    // forward it verbatim. Otherwise wrap the transport failure.
    if (!text) {
      return rpcErrorFor(parsed.id, -32603, `Remote returned empty body (HTTP ${res.status})`);
    }
    try {
      // Validate JSON by parsing, then return the original text to preserve
      // the remote's shape (including any extension keys).
      JSON.parse(text);
      return text;
    } catch {
      return rpcErrorFor(parsed.id, -32603, `Remote returned non-JSON body (HTTP ${res.status})`);
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (isNotification(parsed)) {
      await writeErrLine(deps.stderr, `cojo-mcp: transport error on notification: ${message}`);
      return null;
    }
    return rpcErrorFor(parsed.id, -32603, `Transport error: ${message}`);
  }
}

/**
 * Run the bridge loop. Resolves when stdin closes or the signal aborts.
 */
export async function runBridge(cfg: BridgeConfig, deps: BridgeDeps): Promise<void> {
  const reader = deps.stdin
    .pipeThrough(new TextDecoderStream())
    .getReader();

  let carry = "";
  try {
    while (true) {
      if (deps.signal?.aborted) break;
      const { value, done } = await reader.read();
      if (done) {
        if (carry.trim()) {
          const out = await forwardOne(carry, cfg, deps);
          if (out !== null) await writeLine(deps.stdout, out);
        }
        break;
      }
      carry += value;
      let newlineIdx: number;
      while ((newlineIdx = carry.indexOf("\n")) !== -1) {
        const line = carry.slice(0, newlineIdx);
        carry = carry.slice(newlineIdx + 1);
        const out = await forwardOne(line, cfg, deps);
        if (out !== null) await writeLine(deps.stdout, out);
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}
