/**
 * Preflight: UUID-preservation round-trip.
 *
 * Ship-blocker for the auth broker cutover. Verifies that the full
 * MuckRock → Supabase admin → magiclink → setSession flow round-trips a
 * fixed UUID from `admin.createUser({id})` through `admin.generateLink`
 * back out of `getUser(access_token).id` unchanged.
 *
 * All v2 Postgres rows key off `auth.users.id`. If the UUID doesn't
 * round-trip, every user's data disappears on first login after cutover.
 *
 * Usage:
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     deno run --allow-net --allow-env scripts/preflight-uuid-validation.ts
 *
 *   Optional:
 *     PREFLIGHT_UUID=<uuid>          (default 00000000-0000-0000-0000-000000000001)
 *     PREFLIGHT_EMAIL=<email>        (default preflight@cojournalist.ai)
 *     PREFLIGHT_REDIRECT_TO=<url>    (default http://localhost:5173/auth/callback)
 *
 * Exit codes:
 *   0 = all 6 steps passed
 *   1 = any step failed (see logs — do not proceed with cutover)
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ??
  Deno.env.get("SUPABASE_SERVICE_KEY");

if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
  console.error("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY");
  Deno.exit(1);
}

const FIXED_UUID = Deno.env.get("PREFLIGHT_UUID") ??
  "00000000-0000-0000-0000-000000000001";
const EMAIL = Deno.env.get("PREFLIGHT_EMAIL") ?? "preflight@cojournalist.ai";
const REDIRECT_TO = Deno.env.get("PREFLIGHT_REDIRECT_TO") ??
  "http://localhost:5173/auth/callback";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function banner() {
  console.log("=".repeat(72));
  console.log("Auth cutover preflight — UUID round-trip validation");
  console.log(`  Supabase URL  : ${SUPABASE_URL}`);
  console.log(`  Fixed UUID    : ${FIXED_UUID}`);
  console.log(`  Email         : ${EMAIL}`);
  console.log(`  redirect_to   : ${REDIRECT_TO}`);
  console.log("=".repeat(72));
}

function fail(step: string, reason: string): never {
  console.error(`\n[FAIL] Step ${step}: ${reason}`);
  console.error(
    "Preflight aborted. Do NOT proceed with cutover. See logs above.",
  );
  Deno.exit(1);
}

async function cleanupIfExists(): Promise<void> {
  try {
    await admin.auth.admin.deleteUser(FIXED_UUID);
  } catch {
    // Ignore — user may not exist.
  }
}

async function main(): Promise<void> {
  banner();

  // Pre-cleanup so step 1 always starts clean.
  await cleanupIfExists();

  // ---------------------------------------------------------------------
  // Step 1: createUser with fixed UUID → returned user.id must match
  // ---------------------------------------------------------------------
  console.log("\n[1/6] admin.createUser with fixed UUID");
  const { data: createData, error: createErr } = await admin.auth.admin
    .createUser({
      id: FIXED_UUID,
      email: EMAIL,
      email_confirm: true,
      user_metadata: { preflight: true },
    });

  if (createErr) {
    fail("1", `createUser error: ${createErr.message}`);
  }
  if (!createData?.user) {
    fail("1", "createUser returned no user");
  }
  if (createData.user.id !== FIXED_UUID) {
    fail(
      "1",
      `UUID was rewritten by Supabase: requested ${FIXED_UUID}, got ${createData.user.id}`,
    );
  }
  console.log(`      ✓ user.id = ${createData.user.id} (matches)`);

  // ---------------------------------------------------------------------
  // Step 2: generateLink({type:'magiclink'}) → action_link returned
  // ---------------------------------------------------------------------
  console.log("\n[2/6] admin.generateLink (type: magiclink)");
  const { data: linkData, error: linkErr } = await admin.auth.admin
    .generateLink({
      type: "magiclink",
      email: EMAIL,
      options: { redirectTo: REDIRECT_TO },
    });

  if (linkErr) {
    fail("2", `generateLink error: ${linkErr.message}`);
  }
  const actionLink = linkData?.properties?.action_link;
  if (!actionLink) {
    fail("2", "generateLink response missing properties.action_link");
  }
  try {
    new URL(actionLink);
  } catch {
    fail("2", `action_link not a valid URL: ${actionLink}`);
  }
  console.log(`      ✓ action_link returned (${actionLink.length} chars)`);

  // ---------------------------------------------------------------------
  // Step 3: GET action_link with redirect: manual → Location header has
  //         the redirect_to target with hash fragment containing tokens
  // ---------------------------------------------------------------------
  console.log("\n[3/6] Follow action_link → expect 302 with hash tokens");
  const response = await fetch(actionLink!, { redirect: "manual" });
  if (response.status < 300 || response.status >= 400) {
    fail(
      "3",
      `expected 3xx from action_link, got ${response.status}. Body: ${await response
        .text()}`,
    );
  }
  const location = response.headers.get("location");
  if (!location) {
    fail("3", "Response had no Location header");
  }
  console.log(
    `      ✓ got ${response.status} → Location (${location!.length} chars)`,
  );

  // ---------------------------------------------------------------------
  // Step 4: Extract access_token from hash fragment in Location header
  // ---------------------------------------------------------------------
  console.log("\n[4/6] Extract access_token + refresh_token from hash");
  const hashIdx = location!.indexOf("#");
  if (hashIdx === -1) {
    fail(
      "4",
      `Location had no hash fragment. Full Location: ${location}. If this contains "error" the email template may need configuring, or the token type may need to be "recovery" instead of "magiclink".`,
    );
  }
  const hashParams = new URLSearchParams(location!.slice(hashIdx + 1));
  const accessToken = hashParams.get("access_token");
  const refreshToken = hashParams.get("refresh_token");
  if (!accessToken) {
    fail("4", `hash fragment has no access_token. hash: ${location!.slice(hashIdx + 1)}`);
  }
  if (!refreshToken) {
    fail("4", `hash fragment has no refresh_token. hash: ${location!.slice(hashIdx + 1)}`);
  }
  console.log(
    `      ✓ access_token (${accessToken!.length} chars), refresh_token (${refreshToken!.length} chars)`,
  );

  // ---------------------------------------------------------------------
  // Step 5: getUser(access_token).id MUST equal FIXED_UUID
  // ---------------------------------------------------------------------
  console.log("\n[5/6] getUser(access_token) → verify user.id round-trips");
  const { data: userData, error: userErr } = await admin.auth.getUser(
    accessToken!,
  );
  if (userErr) {
    fail("5", `getUser error: ${userErr.message}`);
  }
  if (!userData?.user) {
    fail("5", "getUser returned no user");
  }
  if (userData.user.id !== FIXED_UUID) {
    fail(
      "5",
      `UUID mismatch after round-trip: expected ${FIXED_UUID}, got ${userData.user.id}`,
    );
  }
  console.log(`      ✓ user.id = ${userData.user.id} (round-trip clean)`);

  // ---------------------------------------------------------------------
  // Step 6: Cleanup — delete the preflight user
  // ---------------------------------------------------------------------
  console.log("\n[6/6] Cleanup");
  const { error: deleteErr } = await admin.auth.admin.deleteUser(FIXED_UUID);
  if (deleteErr) {
    console.warn(
      `      ⚠ deleteUser failed (not fatal): ${deleteErr.message}. Manual cleanup may be needed.`,
    );
  } else {
    console.log(`      ✓ deleted preflight user ${FIXED_UUID}`);
  }

  console.log("\n" + "=".repeat(72));
  console.log("PREFLIGHT PASSED — UUID round-trips cleanly. Safe to cut over.");
  console.log("=".repeat(72));
}

await main();
