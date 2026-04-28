import {
  assert,
  assertEquals,
  assertMatch,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const enabled = Deno.env.get("COJO_SELFHOST_RUNTIME_SMOKE") === "1";

function envAny(...names: string[]): string {
  for (const name of names) {
    const value = Deno.env.get(name);
    if (value) return value;
  }
  throw new Error(`Missing env var. Tried: ${names.join(", ")}`);
}

function assertLocalTarget(url: string) {
  if (Deno.env.get("COJO_ALLOW_REMOTE_SELFHOST_SMOKE") === "1") return;

  const hostname = new URL(url).hostname;
  if (
    hostname !== "127.0.0.1" &&
    hostname !== "localhost" &&
    hostname !== "::1"
  ) {
    throw new Error(
      `Refusing to run self-host smoke against non-local Supabase URL: ${url}`,
    );
  }
}

function functionUrl(supabaseUrl: string, name: string, path = ""): string {
  return `${supabaseUrl.replace(/\/$/, "")}/functions/v1/${name}${path}`;
}

function authHeaders(token: string): HeadersInit {
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function responseBody(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

Deno.test({
  name:
    "selfhost runtime: allowlist auth and scout CRUD work against local Supabase",
  ignore: !enabled,
  async fn() {
    const supabaseUrl = envAny("SUPABASE_URL", "API_URL");
    const anonKey = envAny("SUPABASE_ANON_KEY", "ANON_KEY", "PUBLISHABLE_KEY");
    const serviceRoleKey = envAny(
      "SUPABASE_SERVICE_ROLE_KEY",
      "SERVICE_ROLE_KEY",
      "SECRET_KEY",
    );
    assertLocalTarget(supabaseUrl);

    const service = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const anon = createClient(supabaseUrl, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });

    const suffix = crypto.randomUUID().slice(0, 8).toLowerCase();
    const allowedDomain = `smoke-${suffix}.example.com`;
    const allowedEmail = `allowed-${suffix}@${allowedDomain}`;
    const blockedEmail = `blocked-${suffix}@blocked-${suffix}.example.net`;
    const password = `Smoke-${crypto.randomUUID()}`;
    let allowedUserId = "";
    let blockedUserId = "";
    let scoutId = "";

    try {
      const { error: allowlistError } = await service
        .from("signup_email_allowlist")
        .upsert([
          {
            kind: "domain",
            value: allowedDomain,
            reason: "selfhost runtime smoke",
          },
          {
            kind: "email",
            value: allowedEmail,
            reason: "selfhost runtime smoke",
          },
        ], { onConflict: "kind,value" });
      if (allowlistError) {
        throw new Error(
          `failed to seed signup allowlist: ${allowlistError.message}`,
        );
      }

      const { data: allowedData, error: allowedError } = await anon.auth.signUp(
        {
          email: allowedEmail,
          password,
        },
      );
      if (allowedError) {
        throw new Error(`allowed signup failed: ${allowedError.message}`);
      }
      allowedUserId = allowedData.user?.id ?? "";
      assert(allowedUserId.length > 0, "allowed signup returned no user id");

      const { data: blockedData, error: blockedError } = await anon.auth.signUp(
        {
          email: blockedEmail,
          password: `Blocked-${crypto.randomUUID()}`,
        },
      );
      blockedUserId = blockedData.user?.id ?? "";
      assert(
        blockedError,
        "blocked signup should fail when allowlist is seeded",
      );
      assertMatch(blockedError.message, /not allowed|allowed newsroom/i);

      const { error: creditsError } = await service
        .from("credit_accounts")
        .upsert({
          user_id: allowedUserId,
          tier: "free",
          monthly_cap: 100,
          balance: 100,
          entitlement_source: "selfhost-smoke",
        }, { onConflict: "user_id" });
      if (creditsError) {
        throw new Error(
          `failed to seed credit account: ${creditsError.message}`,
        );
      }

      let token = allowedData.session?.access_token ?? "";
      if (!token) {
        const { data: signInData, error: signInError } = await anon.auth
          .signInWithPassword({
            email: allowedEmail,
            password,
          });
        if (signInError) {
          throw new Error(`allowed sign-in failed: ${signInError.message}`);
        }
        token = signInData.session?.access_token ?? "";
      }
      assert(token.length > 0, "expected allowed user access token");

      const unauthenticated = await fetch(functionUrl(supabaseUrl, "scouts"));
      await unauthenticated.body?.cancel();
      assertEquals(unauthenticated.status, 401);

      const createResponse = await fetch(functionUrl(supabaseUrl, "scouts"), {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          name: `Self-host Smoke ${suffix}`,
          type: "web",
          url: "https://example.com",
          topic: "selfhost",
          description: "Local self-host smoke test scout.",
        }),
      });
      const createText = await responseBody(createResponse);
      assertEquals(createResponse.status, 201, createText);
      const scout = JSON.parse(createText);
      scoutId = scout.id;
      assert(scoutId.length > 0, "scout create returned no id");
      assertEquals(scout.type, "web");
      assertEquals(scout.url, "https://example.com");

      const listResponse = await fetch(functionUrl(supabaseUrl, "scouts"), {
        headers: authHeaders(token),
      });
      const listText = await responseBody(listResponse);
      assertEquals(listResponse.status, 200, listText);
      const listed = JSON.parse(listText);
      assert(
        listed.items?.some((item: { id?: string }) => item.id === scoutId),
        "created scout should appear in list response",
      );

      const deleteResponse = await fetch(
        functionUrl(supabaseUrl, "scouts", `/${scoutId}`),
        { method: "DELETE", headers: authHeaders(token) },
      );
      await deleteResponse.body?.cancel();
      assertEquals(deleteResponse.status, 204);
      scoutId = "";
    } finally {
      if (scoutId) {
        // The user cleanup below removes dependent rows in local test runs, but
        // delete the scout first when the function round-trip failed mid-test.
        try {
          const { error } = await service.from("scouts").delete().eq(
            "id",
            scoutId,
          );
          if (error) console.warn(`scout cleanup failed: ${error.message}`);
        } catch (error) {
          console.warn(`scout cleanup failed: ${error}`);
        }
      }

      for (const userId of [allowedUserId, blockedUserId].filter(Boolean)) {
        try {
          await service.auth.admin.deleteUser(userId);
        } catch {
          // Local Supabase can expose service keys that are accepted by REST but
          // rejected by the auth-admin helper path. Smoke users are unique.
        }
      }
    }
  },
});
