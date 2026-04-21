/**
 * Beat Scout (type "pulse") end-to-end benchmark + audit.
 *
 * Port of backend/scripts/benchmark_pulse.py.
 *
 * Modes:
 *   Quick (default)   : 2 scenarios, HTTP + unit counts, wall-clock.
 *   --full            : 4 scenarios (+ AI policy, Oakland niche).
 *   --audit           : 6 permutations x reliable/niche modes, quality checks,
 *                       flaw detection, markdown report under scripts/reports/.
 *
 *   set -a; source .env; set +a
 *   deno run --allow-env --allow-net --allow-read=. --allow-write=scripts/reports \
 *     scripts/benchmark-beat.ts             # quick
 *   deno run --allow-env --allow-net --allow-read=. --allow-write=scripts/reports \
 *     scripts/benchmark-beat.ts --full
 *   deno run --allow-env --allow-net --allow-read=. --allow-write=scripts/reports \
 *     scripts/benchmark-beat.ts --audit
 */

import {
  BenchCtx,
  dur,
  fail,
  getCtx,
  hr,
  ok,
  pgDelete,
  pgInsert,
  pgSelectOne,
  svcFetch,
} from "./_bench_shared.ts";
import {
  Article,
  AuditRecord,
  detectFlaws,
  runQualityChecks,
  writeReport,
} from "./_bench_quality.ts";

interface Scenario {
  name: string;
  location: { displayName: string; country: string; locationType: string } | null;
  topic: string | null;
  criteria: string;
  sourceMode: "reliable" | "niche";
  prioritySources: string[];
  language: string;
  category: "news" | "government" | "analysis";
  scope: "location" | "topic";
}

const QUICK: Scenario[] = [
  {
    name: "Zurich / climate beat",
    location: { displayName: "Zurich, Switzerland", country: "CH", locationType: "city" },
    topic: null,
    criteria: "climate action, public transit, emissions policy",
    sourceMode: "reliable",
    language: "de",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.nzz.ch/schweiz",
      "https://www.tagesanzeiger.ch/zuerich",
      "https://www.srf.ch/news/schweiz",
    ],
  },
  {
    name: "UK housing beat",
    location: null,
    topic: "UK housing policy",
    criteria: "new housing starts, planning reform, rent controls",
    sourceMode: "reliable",
    language: "en",
    category: "news",
    scope: "topic",
    prioritySources: [
      "https://www.theguardian.com/society/housing",
      "https://www.bbc.co.uk/news/business-61327990",
      "https://www.politicshome.com/news",
    ],
  },
];

const EXTRA: Scenario[] = [
  {
    name: "Oakland / transit (niche)",
    location: { displayName: "Oakland, US", country: "US", locationType: "city" },
    topic: null,
    criteria: "transit budget, BART, AC Transit",
    sourceMode: "niche",
    language: "en",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.oaklandside.org/",
      "https://oaklandnorth.net/",
    ],
  },
  {
    name: "AI policy beat",
    location: null,
    topic: "AI regulation and policy",
    criteria: "AI regulation, export controls, safety frameworks",
    sourceMode: "reliable",
    language: "en",
    category: "news",
    scope: "topic",
    prioritySources: [
      "https://www.politico.com/news/technology",
      "https://www.ft.com/technology",
      "https://www.theverge.com/ai-artificial-intelligence",
    ],
  },
];

// Audit mirrors prod AUDIT_PERMUTATIONS: niche small-town + reliable metro +
// topic-only. One scenario per DB row; unlike prod we don't run news+gov in
// parallel because the Supabase beat pipeline is a single category per scout.
const AUDIT: Scenario[] = [
  {
    name: "niche: Bozeman",
    location: { displayName: "Bozeman, Montana", country: "US", locationType: "city" },
    topic: null,
    criteria: "local news, city council, transit",
    sourceMode: "niche",
    language: "en",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.bozemandailychronicle.com/",
      "https://www.kbzk.com/",
    ],
  },
  {
    name: "niche: Flagstaff",
    location: { displayName: "Flagstaff, Arizona", country: "US", locationType: "city" },
    topic: null,
    criteria: "city council, zoning, water",
    sourceMode: "niche",
    language: "en",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.azdailysun.com/",
      "https://knau.org/",
    ],
  },
  {
    name: "reliable: Zurich",
    location: { displayName: "Zurich, Switzerland", country: "CH", locationType: "city" },
    topic: null,
    criteria: "climate, transit, housing",
    sourceMode: "reliable",
    language: "de",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.nzz.ch/schweiz",
      "https://www.tagesanzeiger.ch/zuerich",
      "https://www.srf.ch/news/schweiz",
    ],
  },
  {
    name: "reliable: London",
    location: { displayName: "London, United Kingdom", country: "GB", locationType: "city" },
    topic: null,
    criteria: "housing, transit, planning",
    sourceMode: "reliable",
    language: "en",
    category: "news",
    scope: "location",
    prioritySources: [
      "https://www.theguardian.com/uk/london",
      "https://www.bbc.co.uk/news/uk-england-london",
      "https://www.standard.co.uk/",
    ],
  },
  {
    name: "topic: AI regulation (en)",
    location: null,
    topic: "AI regulation and policy",
    criteria: "AI regulation, export controls, safety frameworks",
    sourceMode: "reliable",
    language: "en",
    category: "news",
    scope: "topic",
    prioritySources: [
      "https://www.politico.com/news/technology",
      "https://www.ft.com/technology",
    ],
  },
  {
    name: "topic: Mietpreisbremse (de)",
    location: null,
    topic: "Mietpreisbremse",
    criteria: "Mietpreisbremse, Wohnungsmarkt, Berlin Mieten",
    sourceMode: "reliable",
    language: "de",
    category: "news",
    scope: "topic",
    prioritySources: [
      "https://www.zeit.de/",
      "https://www.spiegel.de/",
    ],
  },
];

async function runScenario(
  ctx: BenchCtx,
  sc: Scenario,
  opts: { verbose?: boolean } = {},
): Promise<AuditRecord> {
  const suffix = crypto.randomUUID().slice(0, 8);
  const scoutName = `bench-beat-${suffix}`;
  let scoutId: string | null = null;
  const startMs = performance.now();

  const record: AuditRecord = {
    permutation: sc.name,
    category: sc.category,
    source_mode: sc.sourceMode,
    scope: sc.scope,
    queries_generated: 0,
    raw_results: 0,
    final_articles: 0,
    articles: [],
    summary: "",
    processing_time_ms: 0,
    error: null,
    quality_checks: [],
  };

  try {
    const scout = await pgInsert<{ id: string }>(ctx, "scouts", {
      user_id: ctx.userId,
      name: scoutName,
      type: "pulse",
      criteria: sc.criteria,
      topic: sc.topic,
      location: sc.location,
      preferred_language: sc.language,
      regularity: "daily",
      schedule_cron: "0 8 * * *",
      source_mode: sc.sourceMode,
      is_active: false,
      priority_sources: sc.prioritySources,
    });
    scoutId = scout.id;
    if (opts.verbose) ok("scout created", scoutId);

    const res = await svcFetch(ctx, "/functions/v1/scout-beat-execute", {
      scout_id: scoutId,
    });
    record.processing_time_ms = Math.round(performance.now() - startMs);

    if (res.status >= 400) {
      record.error = `HTTP ${res.status}: ${res.text.slice(0, 300)}`;
      return record;
    }
    const payload = res.json as {
      sources_scraped?: number;
      sources_failed?: number;
      articles_count?: number;
    };
    record.queries_generated = (payload?.sources_scraped ?? 0) +
      (payload?.sources_failed ?? 0);
    record.raw_results = payload?.sources_scraped ?? 0;
    record.final_articles = payload?.articles_count ?? 0;

    // Pull inserted units to feed the quality pipeline
    const units = await fetchUnits(ctx, scoutId);
    record.articles = units.map<Article>((u) => ({
      title: u.source_title ?? u.source_url ?? "Untitled",
      url: u.source_url ?? "",
      source: u.source_domain ?? "",
      date: u.occurred_at,
      summary: u.statement ?? null,
    }));
    // Build a bullet summary from the first N statements (mirrors email summary)
    record.summary = units
      .slice(0, 5)
      .map((u) => `- ${u.statement ?? ""}`)
      .filter((s) => s.length > 2)
      .join("\n");

    record.quality_checks = runQualityChecks(
      { summary: record.summary, articles: record.articles, category: sc.category },
      sc.language,
      sc.sourceMode,
      sc.prioritySources,
    );
  } catch (e) {
    record.error = e instanceof Error ? e.message : String(e);
  } finally {
    if (scoutId) {
      await pgDelete(ctx, "scouts", { id: scoutId }).catch(() => {});
    }
  }
  return record;
}

async function fetchUnits(
  ctx: BenchCtx,
  scoutId: string,
): Promise<Array<{
  source_url: string | null;
  source_title: string | null;
  source_domain: string | null;
  statement: string | null;
  occurred_at: string | null;
}>> {
  const qs = new URLSearchParams();
  qs.set("select", "source_url,source_title,source_domain,statement,occurred_at");
  qs.set("scout_id", `eq.${scoutId}`);
  qs.set("order", "extracted_at.desc");
  qs.set("limit", "50");
  const res = await fetch(`${ctx.supabaseUrl}/rest/v1/information_units?${qs}`, {
    headers: {
      apikey: ctx.serviceKey,
      Authorization: `Bearer ${ctx.serviceKey}`,
    },
  });
  if (!res.ok) return [];
  return await res.json();
}

function printRecord(r: AuditRecord): void {
  const status = r.error
    ? "ERROR"
    : r.final_articles === 0
    ? "FAIL"
    : r.final_articles <= 1
    ? `WARN (${r.final_articles})`
    : "OK";
  console.log(
    `  [${status}] ${r.permutation} | ${r.source_mode} | units=${r.final_articles} | ` +
      `sources=${r.raw_results} | ${dur(r.processing_time_ms)}`,
  );
  if (r.error) fail("error", r.error);
  for (const c of r.quality_checks) {
    const tag = c.status === "PASS" ? "  \u2713" : c.status === "FAIL" ? "  \u2717" : "  !";
    console.log(`    ${tag} ${c.check}: ${c.detail}`);
  }
}

async function runQuick(ctx: BenchCtx, scenarios: Scenario[]): Promise<void> {
  for (const sc of scenarios) {
    hr(sc.name);
    const record = await runScenario(ctx, sc, { verbose: true });
    printRecord(record);
  }
}

async function runAudit(ctx: BenchCtx): Promise<void> {
  console.log(`Audit: ${AUDIT.length} permutations against ${ctx.ownerEmail}\n`);
  const records: AuditRecord[] = [];
  for (const sc of AUDIT) {
    hr(sc.name);
    const r = await runScenario(ctx, sc);
    records.push(r);
    printRecord(r);
  }

  hr("Flaw detection");
  const flaws = detectFlaws(records);
  if (flaws.length === 0) console.log("  No flaws detected \u2713");
  else for (const f of flaws) console.log(`  \u2717 ${f}`);

  const md = writeReport(records, flaws, AUDIT.length);
  const outDir = `${Deno.cwd()}/scripts/reports`;
  try {
    await Deno.mkdir(outDir, { recursive: true });
  } catch { /* exists */ }
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const path = `${outDir}/beat-audit-${stamp}.md`;
  await Deno.writeTextFile(path, md);
  console.log(`\nReport written: ${path}`);
}

// ---------------------------------------------------------------------------

const args = new Set(Deno.args);
const ctx = await getCtx();
console.log(
  `Running Beat Scout benchmark as ${ctx.ownerEmail} (user_id=${ctx.userId})`,
);

if (args.has("--audit")) {
  await runAudit(ctx);
} else if (args.has("--full")) {
  await runQuick(ctx, [...QUICK, ...EXTRA]);
} else {
  await runQuick(ctx, QUICK);
}
