export interface AuthStateRedirectPayload {
  mcp_callback?: string;
  mcp_state?: string;
  post_login_redirect?: string;
}

const LOCALHOST_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const LOCALHOST_CALLBACK_PATH = "/auth/callback";

export function parseAllowedPostLoginRedirect(raw: string | null): string | undefined {
  if (!raw) return undefined;

  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return undefined;
  }

  if (!LOCALHOST_HOSTS.has(parsed.hostname)) return undefined;
  if (parsed.pathname !== LOCALHOST_CALLBACK_PATH) return undefined;
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return undefined;

  return parsed.toString();
}

export function resolvePostLoginRedirect(
  fallbackRedirect: string,
  statePayload: AuthStateRedirectPayload,
): string {
  if (statePayload.mcp_callback) {
    const callback = new URL(statePayload.mcp_callback);
    if (statePayload.mcp_state) {
      callback.searchParams.set("mcp_state", statePayload.mcp_state);
    }
    return callback.toString();
  }

  return statePayload.post_login_redirect ?? fallbackRedirect;
}

export function buildLocalPostLoginHandoffUrl(
  postLoginRedirect: string,
  actionLocation: string,
): string | undefined {
  let target: URL;
  let source: URL;
  try {
    target = new URL(postLoginRedirect);
    source = new URL(actionLocation);
  } catch {
    return undefined;
  }

  if (!LOCALHOST_HOSTS.has(target.hostname)) return undefined;
  if (target.pathname !== LOCALHOST_CALLBACK_PATH) return undefined;
  if (!source.hash) return undefined;

  target.search = source.search;
  target.hash = source.hash;
  return target.toString();
}
