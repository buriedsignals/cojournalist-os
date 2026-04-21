/**
 * Probe the deployed export-select Edge Function against prod.
 *
 * Bypasses the browser + Render rebuild loop. Mints a real Supabase JWT for
 * an existing user via admin magiclink → extracts access_token → POSTs four
 * scenarios at /functions/v1/export-select and asserts each.
 *
 * Usage:
 *   set -a && source .env && source supabase-keys.txt && set +a
 *   deno run --allow-net --allow-env scripts/probe-export-select.ts
 *
 *   Optional:
 *     PROBE_USER_UUID=<uuid>   (default: Tom's UUID — owns the Hyrox scout)
 *
 * Exit 0 = all 4 cases passed. Exit 1 = any case failed.
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ??
  Deno.env.get("SUPABASE_SERVICE_KEY");

if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
  console.error("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY");
  Deno.exit(1);
}

const USER_UUID = Deno.env.get("PROBE_USER_UUID") ??
  "c6ac7e0c-35fd-48d0-9b76-7eb7acd48f2c";
const EF_URL = `${SUPABASE_URL}/functions/v1/export-select`;
const REDIRECT_TO = "http://localhost:5173/auth/callback";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const failures: string[] = [];
function check(name: string, ok: boolean, detail = ""): void {
  if (ok) {
    console.log(`  ✓ ${name}${detail ? ` — ${detail}` : ""}`);
  } else {
    console.error(`  ✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failures.push(name);
  }
}

async function mintJwt(): Promise<string> {
  const { data: u, error: ue } = await admin.auth.admin.getUserById(USER_UUID);
  if (ue || !u?.user?.email) {
    throw new Error(`getUserById failed: ${ue?.message ?? "no email"}`);
  }
  const email = u.user.email;
  const { data: link, error: le } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
    options: { redirectTo: REDIRECT_TO },
  });
  if (le || !link?.properties?.action_link) {
    throw new Error(`generateLink failed: ${le?.message ?? "no action_link"}`);
  }
  const r = await fetch(link.properties.action_link, { redirect: "manual" });
  const loc = r.headers.get("location") ?? "";
  const hashIdx = loc.indexOf("#");
  if (hashIdx === -1) {
    throw new Error(`magiclink redirect missing hash. Location: ${loc}`);
  }
  const params = new URLSearchParams(loc.slice(hashIdx + 1));
  const tok = params.get("access_token");
  if (!tok) throw new Error(`hash missing access_token: ${loc.slice(hashIdx + 1)}`);
  return tok;
}

async function call(
  body: unknown,
  jwt: string | null,
): Promise<{ status: number; json: any; text: string }> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (jwt) headers["Authorization"] = `Bearer ${jwt}`;
  const r = await fetch(EF_URL, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let json: any = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* not JSON */
  }
  return { status: r.status, json, text };
}

const SAMPLE_UNITS = [
  {
    unit_id: "u1",
    statement: "City council approved a $2.4M budget increase for road repairs in District 4.",
    entities: ["City Council", "District 4"],
    source_title: "Cityview Tribune",
    created_at: "2026-04-20T10:00:00Z",
    date: "2026-04-19",
    unit_type: "decision",
    scout_type: "civic",
  },
  {
    unit_id: "u2",
    statement: "Mayor Chen vetoed the proposed library closure in the Eastside neighborhood.",
    entities: ["Mayor Chen", "Eastside"],
    source_title: "Cityview Tribune",
    created_at: "2026-04-21T08:30:00Z",
    date: "2026-04-20",
    unit_type: "action",
    scout_type: "civic",
  },
  {
    unit_id: "u3",
    statement: "A local bakery announced a new croissant flavor.",
    entities: ["Bakery"],
    source_title: "Foodie Weekly",
    created_at: "2026-04-21T15:00:00Z",
    date: "2026-04-21",
    unit_type: "announcement",
    scout_type: "social",
  },
];

async function main() {
  console.log("=".repeat(72));
  console.log(`Probing: ${EF_URL}`);
  console.log(`User UUID: ${USER_UUID}`);
  console.log("=".repeat(72));

  console.log("\n[mint] generating JWT for probe user");
  const jwt = await mintJwt();
  console.log(`  ✓ access_token (${jwt.length} chars)`);

  // ---------------------------------------------------------------------
  // Case 1: Happy path
  // ---------------------------------------------------------------------
  console.log("\n[1/4] Happy path — 3 units + journalism brief");
  const r1 = await call(
    {
      units: SAMPLE_UNITS,
      prompt: "I'm writing about civic accountability in city government this week.",
      location: null,
      topic: null,
    },
    jwt,
  );
  check("status 200", r1.status === 200, `got ${r1.status}`);
  check("response is JSON", r1.json !== null, r1.text.slice(0, 200));
  if (r1.json) {
    const ids = r1.json.selected_unit_ids;
    check(
      "selected_unit_ids is array",
      Array.isArray(ids),
      JSON.stringify(ids),
    );
    if (Array.isArray(ids)) {
      const validSet = new Set(SAMPLE_UNITS.map((u) => u.unit_id));
      const allValid = ids.every((id: string) => validSet.has(id));
      check("selected ids ⊆ input ids", allValid, ids.join(","));
      check("at least 1 selected", ids.length > 0, `selected ${ids.length}`);
      // Heuristic: u3 (bakery) should NOT be in a civic-accountability brief.
      const u3InResult = ids.includes("u3");
      check(
        "off-topic u3 (bakery) excluded",
        !u3InResult,
        u3InResult ? "MODEL INCLUDED IT — soft-fail, model judgment" : "ok",
      );
    }
    check(
      "selection_summary is non-empty string",
      typeof r1.json.selection_summary === "string" &&
        r1.json.selection_summary.length > 0,
      r1.json.selection_summary?.slice(0, 100),
    );
    console.log(`\n  selected_unit_ids: ${JSON.stringify(r1.json.selected_unit_ids)}`);
    console.log(`  selection_summary: ${r1.json.selection_summary}`);
  }

  // ---------------------------------------------------------------------
  // Case 2: Empty units
  // ---------------------------------------------------------------------
  console.log("\n[2/4] Empty units array");
  const r2 = await call({ units: [], prompt: "anything" }, jwt);
  check("status 200", r2.status === 200, `got ${r2.status}`);
  check(
    "selected_unit_ids = []",
    Array.isArray(r2.json?.selected_unit_ids) &&
      r2.json.selected_unit_ids.length === 0,
    JSON.stringify(r2.json?.selected_unit_ids),
  );
  check(
    "selection_summary mentions no candidates",
    typeof r2.json?.selection_summary === "string" &&
      /no candidate/i.test(r2.json.selection_summary),
    r2.json?.selection_summary,
  );

  // ---------------------------------------------------------------------
  // Case 3: Missing prompt → 400
  // ---------------------------------------------------------------------
  console.log("\n[3/4] Missing prompt → 400 ValidationError");
  const r3 = await call({ units: SAMPLE_UNITS, prompt: "" }, jwt);
  check("status 400", r3.status === 400, `got ${r3.status}`);
  check(
    "error message mentions prompt",
    typeof r3.json?.error === "string" && /prompt/i.test(r3.json.error),
    r3.json?.error,
  );

  // ---------------------------------------------------------------------
  // Case 4: No auth → 401
  // ---------------------------------------------------------------------
  console.log("\n[4/4] No Authorization header → 401");
  const r4 = await call({ units: SAMPLE_UNITS, prompt: "x" }, null);
  check("status 401", r4.status === 401, `got ${r4.status}`);

  // ---------------------------------------------------------------------
  console.log("\n" + "=".repeat(72));
  if (failures.length === 0) {
    console.log("ALL 4 CASES PASSED — export-select EF is live and correct.");
    console.log("=".repeat(72));
    Deno.exit(0);
  } else {
    console.error(`${failures.length} CHECK(S) FAILED:`);
    for (const f of failures) console.error(`  - ${f}`);
    console.log("=".repeat(72));
    Deno.exit(1);
  }
}

await main();
