import {
  buildLocalPostLoginHandoffUrl,
  parseAllowedPostLoginRedirect,
  resolvePostLoginRedirect,
} from "./redirects.ts";

Deno.test("parseAllowedPostLoginRedirect accepts localhost auth callback", () => {
  const redirect = parseAllowedPostLoginRedirect("http://localhost:5173/auth/callback");
  if (redirect !== "http://localhost:5173/auth/callback") {
    throw new Error(`expected localhost callback, got ${redirect ?? "undefined"}`);
  }
});

Deno.test("parseAllowedPostLoginRedirect rejects non-local hosts", () => {
  const redirect = parseAllowedPostLoginRedirect("https://cojournalist.ai/auth/callback");
  if (redirect !== undefined) {
    throw new Error(`expected redirect to be rejected, got ${redirect}`);
  }
});

Deno.test("resolvePostLoginRedirect prefers MCP callback over local redirect", () => {
  const redirect = resolvePostLoginRedirect("http://localhost:5173/auth/callback", {
    mcp_callback: "https://example.supabase.co/functions/v1/mcp-server/callback",
    mcp_state: "signed-state",
    post_login_redirect: "http://localhost:5173/auth/callback",
  });
  if (
    redirect !==
      "https://example.supabase.co/functions/v1/mcp-server/callback?mcp_state=signed-state"
  ) {
    throw new Error(`unexpected redirect ${redirect}`);
  }
});

Deno.test("resolvePostLoginRedirect falls back when no override is present", () => {
  const redirect = resolvePostLoginRedirect("https://www.cojournalist.ai/auth/callback", {});
  if (redirect !== "https://www.cojournalist.ai/auth/callback") {
    throw new Error(`expected fallback redirect, got ${redirect}`);
  }
});

Deno.test("buildLocalPostLoginHandoffUrl rewrites the Supabase redirect onto localhost", () => {
  const handoff = buildLocalPostLoginHandoffUrl(
    "http://localhost:5173/auth/callback",
    "https://www.cojournalist.ai/auth/callback#access_token=abc&refresh_token=def",
  );
  if (handoff !== "http://localhost:5173/auth/callback#access_token=abc&refresh_token=def") {
    throw new Error(`unexpected handoff ${handoff ?? "undefined"}`);
  }
});

Deno.test("buildLocalPostLoginHandoffUrl rejects action redirects without tokens", () => {
  const handoff = buildLocalPostLoginHandoffUrl(
    "http://localhost:5173/auth/callback",
    "https://www.cojournalist.ai/auth/callback",
  );
  if (handoff !== undefined) {
    throw new Error(`expected missing-hash redirect to be rejected, got ${handoff}`);
  }
});
