/**
 * Civic Scout (type "civic") end-to-end benchmark + audit.
 *
 * Port of backend/scripts/benchmark_civic.py. civic-execute enqueues PDFs +
 * docs; civic-extract-worker drains them. Audit mode exercises 10 civic URLs,
 * validates extracted promise count, language, date relevance, writes an
 * audit report to scripts/reports/civic-audit-*.md.
 *
 *   set -a; source .env; set +a
 *   deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts
 *   deno run --allow-env --allow-net --allow-read=. scripts/benchmark-civic.ts --url https://council.example/minutes
 *   deno run --allow-env --allow-net --allow-read=. --allow-write=scripts/reports scripts/benchmark-civic.ts --audit
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
  url: string;
  language: string;
  criteria: string | null;
}

// Zurich Gemeinderat index page lists council protocols in German with rich
// "protokoll" / "geschäfte" link text — exercises the multilingual
// MEETING_KEYWORDS match path and reliably produces extractable promises.
// The Oakland URL it replaced often queued PDFs that contain agendas but no
// explicit commitments, yielding queued>0 / promises=0 (pipeline fine, data
// thin — not a useful smoke-test signal).
const DEFAULT_URL =
  "https://www.gemeinderat-zuerich.ch/protokolle";

const AUDIT: Scenario[] = [
  {
    name: "Basel: Grosser Rat (DE)",
    url: "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
    language: "de",
    criteria: null,
  },
  {
    name: "Basel: Grosser Rat + Wohnungspolitik (DE)",
    url: "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
    language: "de",
    criteria: "Wohnungspolitik",
  },
  {
    name: "Zurich: Gemeinderat (DE)",
    url: "https://www.gemeinderat-zuerich.ch/protokolle",
    language: "de",
    criteria: null,
  },
  {
    name: "Lausanne: Conseil communal (FR)",
    url: "https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html",
    language: "fr",
    criteria: null,
  },
  {
    name: "Bern: Stadtrat + Klimaschutz (DE)",
    url: "https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen",
    language: "de",
    criteria: "Klimaschutz",
  },
  {
    name: "Bozeman: City Commission (EN)",
    url: "https://www.bozeman.net/departments/city-commission",
    language: "en",
    criteria: null,
  },
  {
    name: "Bozeman: City Commission + housing (EN)",
    url: "https://www.bozeman.net/departments/city-commission",
    language: "en",
    criteria: "housing policy",
  },
  {
    name: "Madison WI: Common Council (EN)",
    url: "https://www.cityofmadison.com/council",
    language: "en",
    criteria: null,
  },
  {
    name: "Zermatt: Gemeinde (DE)",
    url: "https://gemeinde.zermatt.ch",
    language: "de",
    criteria: null,
  },
  {
    name: "Zermatt: Gemeinde + Infrastruktur (DE)",
    url: "https://gemeinde.zermatt.ch",
    language: "de",
    criteria: "Infrastruktur",
  },
];

interface Args {
  urls: string[];
  audit: boolean;
  maxDrain: number;
}

function parseArgs(): Args {
  const urls: string[] = [];
  let audit = false;
  let maxDrain = 10;
  for (let i = 0; i < Deno.args.length; i++) {
    const a = Deno.args[i];
    if (a === "--url") urls.push(Deno.args[++i]);
    else if (a === "--audit") audit = true;
    else if (a === "--max-drain") maxDrain = parseInt(Deno.args[++i], 10) || maxDrain;
  }
  return { urls: urls.length > 0 ? urls : [DEFAULT_URL], audit, maxDrain };
}

async function runCivic(
  ctx: BenchCtx,
  sc: Scenario,
  maxDrain: number,
  opts: { verbose?: boolean } = {},
): Promise<AuditRecord> {
  const suffix = crypto.randomUUID().slice(0, 8);
  const scoutName = `bench-civic-${suffix}`;
  let scoutId: string | null = null;
  const startMs = performance.now();

  const record: AuditRecord = {
    permutation: sc.name,
    category: "civic",
    source_mode: "reliable",
    scope: "location",
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
    let domain = "";
    try {
      domain = new URL(sc.url).hostname;
    } catch {
      /* leave blank */
    }
    const scout = await pgInsert<{ id: string }>(ctx, "scouts", {
      user_id: ctx.userId,
      name: scoutName,
      type: "civic",
      root_domain: domain,
      tracked_urls: [sc.url],
      criteria: sc.criteria,
      preferred_language: sc.language,
      regularity: "weekly",
      schedule_cron: "0 8 * * MON",
      is_active: false,
    });
    scoutId = scout.id;
    if (opts.verbose) ok("scout created", scoutId);

    // Phase 1: enqueue
    const enqueueRes = await svcFetch(ctx, "/functions/v1/civic-execute", {
      scout_id: scoutId,
    });
    if (enqueueRes.status >= 400) {
      record.error = `civic-execute HTTP ${enqueueRes.status}: ${enqueueRes.text.slice(0, 200)}`;
      return record;
    }
    const enqueuePayload = enqueueRes.json as { queued?: number };
    record.queries_generated = enqueuePayload?.queued ?? 0;
    record.raw_results = enqueuePayload?.queued ?? 0;

    if (!record.raw_results) {
      // no new documents — skip the drain loop
      record.processing_time_ms = Math.round(performance.now() - startMs);
      return record;
    }

    // Phase 2: drain the queue
    for (let i = 0; i < maxDrain; i++) {
      const drainRes = await svcFetch(ctx, "/functions/v1/civic-extract-worker", {});
      if (drainRes.status >= 400) {
        record.error = `civic-extract-worker HTTP ${drainRes.status}`;
        break;
      }
      const p = drainRes.json as {
        status?: string;
        promises_extracted?: number;
      };
      if (p.status === "idle") break;
      record.final_articles += p.promises_extracted ?? 0;
    }
    record.processing_time_ms = Math.round(performance.now() - startMs);

    // Pull inserted promises to feed quality pipeline
    const promises = await fetchPromises(ctx, scoutId);
    record.articles = promises.map<Article>((p) => ({
      title: p.promise_text ?? "Untitled",
      url: p.source_url ?? "",
      source: p.source_title ?? undefined,
      date: p.meeting_date,
      summary: p.context ?? null,
    }));
    record.summary = promises
      .slice(0, 5)
      .map((p) => `- **${p.promise_text}** ([source](${p.source_url}))`)
      .join("\n");

    record.quality_checks = runQualityChecks(
      {
        summary: record.summary,
        articles: record.articles,
        category: "government",
      },
      sc.language,
      "reliable",
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

async function fetchPromises(
  ctx: BenchCtx,
  scoutId: string,
): Promise<Array<{
  promise_text: string | null;
  context: string | null;
  source_url: string | null;
  source_title: string | null;
  meeting_date: string | null;
}>> {
  const qs = new URLSearchParams();
  qs.set("select", "promise_text,context,source_url,source_title,meeting_date");
  qs.set("scout_id", `eq.${scoutId}`);
  qs.set("order", "created_at.desc");
  qs.set("limit", "50");
  const res = await fetch(`${ctx.supabaseUrl}/rest/v1/promises?${qs}`, {
    headers: {
      apikey: ctx.serviceKey,
      Authorization: `Bearer ${ctx.serviceKey}`,
    },
  });
  if (!res.ok) return [];
  return await res.json();
}

function printRecord(r: AuditRecord): void {
  // Pass/fail cascade:
  //   ERROR — HTTP failure somewhere in the pipeline
  //   FAIL — queued 0 documents (pipeline found no civic PDFs to parse)
  //   WARN — queued something but extraction yielded 0 promises (LLM saw no
  //          commitments, or ≤1 promise — pipeline healthy, data thin)
  //   OK   — ≥ 2 promises extracted
  const queued = r.queries_generated ?? 0;
  const promises = r.final_articles;
  const status = r.error
    ? "ERROR"
    : queued === 0
    ? "FAIL"
    : promises === 0
    ? "WARN (no extractable promises)"
    : promises <= 1
    ? `WARN (${promises})`
    : "OK";
  console.log(
    `  [${status}] ${r.permutation} | queued=${r.queries_generated} | ` +
      `promises=${r.final_articles} | ${dur(r.processing_time_ms)}`,
  );
  if (r.error) fail("error", r.error);
  for (const c of r.quality_checks) {
    const tag = c.status === "PASS" ? "  \u2713" : c.status === "FAIL" ? "  \u2717" : "  !";
    console.log(`    ${tag} ${c.check}: ${c.detail}`);
  }
}

async function runAudit(ctx: BenchCtx, maxDrain: number): Promise<void> {
  console.log(`Civic audit: ${AUDIT.length} permutations against ${ctx.ownerEmail}\n`);
  const records: AuditRecord[] = [];
  for (const sc of AUDIT) {
    hr(sc.name);
    const r = await runCivic(ctx, sc, maxDrain);
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
  const path = `${outDir}/civic-audit-${stamp}.md`;
  await Deno.writeTextFile(path, md);
  console.log(`\nReport written: ${path}`);
}

// ---------------------------------------------------------------------------

const { urls, audit, maxDrain } = parseArgs();
const ctx = await getCtx();
console.log(
  `Running Civic Scout benchmark as ${ctx.ownerEmail} (user_id=${ctx.userId})`,
);

if (audit) {
  await runAudit(ctx, maxDrain);
} else {
  for (const url of urls) {
    hr(`Civic Scout: ${url}`);
    const r = await runCivic(
      ctx,
      { name: url, url, language: "en", criteria: null },
      maxDrain,
      { verbose: true },
    );
    printRecord(r);
  }
}
