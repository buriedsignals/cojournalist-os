/**
 * newsletter-subscribe Edge Function — public proxy for the Buried Signals
 * newsletter signup. Mirrors the working pattern in
 * tools/osint-navigator/app/api/routes.py (`_subscribe_buried_signals`).
 *
 * Route:
 *   POST /newsletter-subscribe   { email, newsletters: ["buried_signals"] }
 *
 * Forwards to https://buriedsignals.com/api/subscribe (which handles the
 * actual list management). Public endpoint — no auth — because /login renders
 * the form pre-authentication.
 */

import { handleCors } from "../_shared/cors.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { logEvent } from "../_shared/log.ts";

interface SubscribeBody {
  email?: unknown;
  newsletters?: unknown;
}

const VALID_NEWSLETTERS = new Set(["buried_signals"]);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405, undefined, req);
  }

  let body: SubscribeBody;
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid JSON body", 400, undefined, req);
  }

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const newsletters = Array.isArray(body.newsletters)
    ? body.newsletters.filter((n): n is string => typeof n === "string")
    : [];

  if (!email || !EMAIL_RE.test(email)) {
    return jsonError("invalid email", 400, undefined, req);
  }
  if (newsletters.length === 0) {
    return jsonError("at least one newsletter must be selected", 400, undefined, req);
  }
  const invalid = newsletters.filter((n) => !VALID_NEWSLETTERS.has(n));
  if (invalid.length > 0) {
    return jsonError(`invalid newsletter(s): ${invalid.join(", ")}`, 400, undefined, req);
  }

  try {
    const upstream = await fetch("https://buriedsignals.com/api/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent": "cojournalist/1.0",
      },
      body: JSON.stringify({ email }),
      signal: AbortSignal.timeout(10_000),
    });

    if (upstream.ok) {
      logEvent({ level: "info", fn: "newsletter-subscribe", event: "subscribed", msg: email });
      return jsonOk({ subscribed: ["buried_signals"] }, 200, req);
    }

    const upstreamText = await upstream.text().catch(() => "");
    logEvent({
      level: "error",
      fn: "newsletter-subscribe",
      event: "upstream_failed",
      msg: `${upstream.status}: ${upstreamText.slice(0, 200)}`,
    });
    return jsonError(
      "Could not subscribe. Please try again later.",
      502,
      "upstream_failed",
      req,
    );
  } catch (e) {
    return jsonFromError(e, req);
  }
});
