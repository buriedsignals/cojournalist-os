/**
 * admin-report Edge Function — revenue reporting for MuckRock pilot invoicing.
 *
 * Ports the admin surface from the legacy FastAPI backend
 * (backend/app/routers/admin.py + services/admin_report_service.py).
 * Gated by ADMIN_EMAILS — only users whose JWT email matches an entry can
 * hit any route.
 *
 * Routes:
 *   GET  /admin-report/metrics
 *   POST /admin-report/report/monthly?year=Y&month=M
 *   POST /admin-report/report/send-email?year=Y&month=M
 *   GET  /admin-report/usage?start_date=...&end_date=...[&org_id=..|&user_id=..]
 *
 * Response shapes match the legacy Pydantic schemas in
 * backend/app/schemas/admin.py so the SvelteKit /admin page can call either
 * surface unchanged.
 */

import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { getServiceClient, SupabaseClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { AuthError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

const RATE_PER_CREDIT = 0.035;
const CREDIT_CAP_PER_ORG = 3000;

interface OrgInfo {
  org_id: string;
  org_name: string;
  balance: number;
  monthly_cap: number;
  seated_count: number;
  tier: string;
}

interface MetricsResponse {
  users_by_tier: Record<string, number>;
  total_users: number;
  orgs: OrgInfo[];
  scouts_by_type: Record<string, number>;
  total_scouts: number;
}

interface OrgUsageSummary {
  org_id: string;
  org_name: string;
  total_credits: number;
  capped_credits: number;
  revenue: number;
  by_operation: Record<string, number>;
}

interface IndividualUsageSummary {
  user_id: string;
  total_credits: number;
  by_operation: Record<string, number>;
}

interface MonthlyReport {
  year: number;
  month: number;
  orgs: OrgUsageSummary[];
  individuals: IndividualUsageSummary[];
  total_org_credits: number;
  total_org_capped_credits: number;
  total_org_revenue: number;
  total_individual_credits: number;
  users_by_tier: Record<string, number>;
  active_scouts_by_type: Record<string, number>;
  rate_per_credit: number;
  credit_cap_per_org: number;
}

interface UsageRecord {
  user_id: string;
  org_id: string;
  amount: number;
  operation: string;
  scout_name: string;
  scout_type: string;
  timestamp: string;
}

interface UsageResponse {
  records: UsageRecord[];
  total_credits: number;
  by_operation: Record<string, number>;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
    requireAdmin(user);
  } catch (e) {
    return jsonFromError(e, req);
  }

  const url = new URL(req.url);
  const path = url.pathname.replace(/^.*\/admin-report/, "") || "/";
  const svc = getServiceClient();
  const isRead = req.method === "GET" || req.method === "HEAD";

  try {
    if (path === "/metrics" && isRead) {
      return jsonOk(await buildMetrics(svc), 200, req);
    }
    if (path === "/report/monthly" && req.method === "POST") {
      const year = parseIntParam(url.searchParams.get("year"), 2024, 2030);
      const month = parseIntParam(url.searchParams.get("month"), 1, 12);
      if (year == null || month == null) {
        return jsonError("year/month required", 400, undefined, req);
      }
      return jsonOk(await buildMonthlyReport(svc, year, month), 200, req);
    }
    if (path === "/report/send-email" && req.method === "POST") {
      const year = parseIntParam(url.searchParams.get("year"), 2024, 2030);
      const month = parseIntParam(url.searchParams.get("month"), 1, 12);
      if (year == null || month == null) {
        return jsonError("year/month required", 400, undefined, req);
      }
      const report = await buildMonthlyReport(svc, year, month);
      return jsonOk(await sendReportEmail(report), 200, req);
    }
    if (path === "/usage" && isRead) {
      const start = url.searchParams.get("start_date");
      const end = url.searchParams.get("end_date");
      if (!isDate(start) || !isDate(end)) {
        return jsonError("start_date and end_date required (YYYY-MM-DD)", 400, undefined, req);
      }
      return jsonOk(
        await buildUsage(svc, start!, end!, {
          orgId: url.searchParams.get("org_id"),
          userId: url.searchParams.get("user_id"),
        }),
        200,
        req,
      );
    }
    return jsonError("not found", 404, undefined, req);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "admin-report",
      event: "unhandled",
      path,
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e, req);
  }
});

// ---------------------------------------------------------------------------

function requireAdmin(user: AuthedUser): void {
  const raw = Deno.env.get("ADMIN_EMAILS") ?? "";
  const admins = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  if (admins.length === 0) {
    throw new AuthError("admin access not configured");
  }
  if (!user.email || !admins.includes(user.email.toLowerCase())) {
    throw new AuthError("admin access denied");
  }
}

function parseIntParam(raw: string | null, min: number, max: number): number | null {
  if (!raw) return null;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < min || n > max) return null;
  return n;
}

function isDate(raw: string | null): raw is string {
  return typeof raw === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw);
}

async function buildMetrics(svc: SupabaseClient): Promise<MetricsResponse> {
  const [prefsRes, orgsRes, scoutsRes] = await Promise.all([
    svc.from("user_preferences").select("tier"),
    svc
      .from("orgs")
      .select("id, name, credit_accounts(tier, monthly_cap, balance, seated_count)")
      .eq("is_individual", false),
    svc.from("scouts").select("type"),
  ]);

  if (prefsRes.error) throw new Error(prefsRes.error.message);
  if (orgsRes.error) throw new Error(orgsRes.error.message);
  if (scoutsRes.error) throw new Error(scoutsRes.error.message);

  const usersByTier: Record<string, number> = {};
  for (const row of prefsRes.data ?? []) {
    const tier = (row as { tier: string | null }).tier ?? "free";
    usersByTier[tier] = (usersByTier[tier] ?? 0) + 1;
  }

  const scoutsByType: Record<string, number> = {};
  for (const row of scoutsRes.data ?? []) {
    const type = (row as { type: string | null }).type ?? "unknown";
    scoutsByType[type] = (scoutsByType[type] ?? 0) + 1;
  }

  const orgs: OrgInfo[] = (orgsRes.data ?? []).map((row) => {
    const org = row as {
      id: string;
      name: string | null;
      credit_accounts:
        | Array<{ tier: string | null; monthly_cap: number | null; balance: number | null; seated_count: number | null }>
        | null;
    };
    const credit = org.credit_accounts?.[0] ?? null;
    return {
      org_id: org.id,
      org_name: org.name ?? "",
      balance: credit?.balance ?? 0,
      monthly_cap: credit?.monthly_cap ?? 0,
      seated_count: credit?.seated_count ?? 0,
      tier: credit?.tier ?? "",
    };
  });

  return {
    users_by_tier: usersByTier,
    total_users: (prefsRes.data ?? []).length,
    orgs,
    scouts_by_type: scoutsByType,
    total_scouts: (scoutsRes.data ?? []).length,
  };
}

interface UsageRow {
  user_id: string | null;
  org_id: string | null;
  scout_id: string | null;
  scout_type: string | null;
  operation: string;
  cost: number;
  created_at: string;
}

function monthBounds(year: number, month: number): { start: string; endExclusive: string } {
  const start = `${year}-${String(month).padStart(2, "0")}-01`;
  const endDate = new Date(Date.UTC(year, month, 1));
  const endExclusive = endDate.toISOString().slice(0, 10);
  return { start, endExclusive };
}

async function fetchUsageRows(
  svc: SupabaseClient,
  startInclusive: string,
  endExclusive: string,
): Promise<UsageRow[]> {
  const out: UsageRow[] = [];
  const pageSize = 1000;
  let offset = 0;
  while (true) {
    const { data, error } = await svc
      .from("usage_records")
      .select("user_id, org_id, scout_id, scout_type, operation, cost, created_at")
      .gte("created_at", startInclusive)
      .lt("created_at", endExclusive)
      .order("created_at", { ascending: true })
      .range(offset, offset + pageSize - 1);
    if (error) throw new Error(error.message);
    const rows = (data ?? []) as UsageRow[];
    out.push(...rows);
    if (rows.length < pageSize) break;
    offset += pageSize;
  }
  return out;
}

async function buildMonthlyReport(
  svc: SupabaseClient,
  year: number,
  month: number,
): Promise<MonthlyReport> {
  const { start, endExclusive } = monthBounds(year, month);
  const rows = await fetchUsageRows(svc, start, endExclusive);

  // Per-org aggregation
  const orgAgg = new Map<string, { total: number; byOp: Record<string, number> }>();
  const userAgg = new Map<string, { total: number; byOp: Record<string, number> }>();
  for (const row of rows) {
    if (row.org_id) {
      const bucket = orgAgg.get(row.org_id) ?? { total: 0, byOp: {} };
      bucket.total += row.cost;
      bucket.byOp[row.operation] = (bucket.byOp[row.operation] ?? 0) + row.cost;
      orgAgg.set(row.org_id, bucket);
    } else if (row.user_id) {
      const bucket = userAgg.get(row.user_id) ?? { total: 0, byOp: {} };
      bucket.total += row.cost;
      bucket.byOp[row.operation] = (bucket.byOp[row.operation] ?? 0) + row.cost;
      userAgg.set(row.user_id, bucket);
    }
  }

  // Resolve org names
  const orgIds = [...orgAgg.keys()];
  let orgNames: Record<string, string> = {};
  if (orgIds.length > 0) {
    const { data, error } = await svc.from("orgs").select("id, name").in("id", orgIds);
    if (error) throw new Error(error.message);
    orgNames = Object.fromEntries(
      (data ?? []).map((row) => [
        (row as { id: string }).id,
        (row as { name: string | null }).name ?? "",
      ]),
    );
  }

  const orgSummaries: OrgUsageSummary[] = orgIds
    .map((id) => {
      const bucket = orgAgg.get(id)!;
      const capped = Math.min(bucket.total, CREDIT_CAP_PER_ORG);
      const revenue = Math.round(capped * RATE_PER_CREDIT * 100) / 100;
      return {
        org_id: id,
        org_name: orgNames[id] ?? "",
        total_credits: bucket.total,
        capped_credits: capped,
        revenue,
        by_operation: bucket.byOp,
      };
    })
    .sort((a, b) => b.total_credits - a.total_credits);

  const individuals: IndividualUsageSummary[] = [...userAgg.entries()]
    .map(([user_id, bucket]) => ({
      user_id,
      total_credits: bucket.total,
      by_operation: bucket.byOp,
    }))
    .sort((a, b) => b.total_credits - a.total_credits);

  const totalOrgCredits = orgSummaries.reduce((acc, o) => acc + o.total_credits, 0);
  const totalOrgCapped = orgSummaries.reduce((acc, o) => acc + o.capped_credits, 0);
  const totalOrgRevenue =
    Math.round(orgSummaries.reduce((acc, o) => acc + o.revenue, 0) * 100) / 100;
  const totalIndividualCredits = individuals.reduce((acc, i) => acc + i.total_credits, 0);

  // Snapshot tier + scout counts (same queries as /metrics)
  const [prefsRes, scoutsRes] = await Promise.all([
    svc.from("user_preferences").select("tier"),
    svc.from("scouts").select("type"),
  ]);
  if (prefsRes.error) throw new Error(prefsRes.error.message);
  if (scoutsRes.error) throw new Error(scoutsRes.error.message);

  const usersByTier: Record<string, number> = {};
  for (const row of prefsRes.data ?? []) {
    const tier = (row as { tier: string | null }).tier ?? "free";
    usersByTier[tier] = (usersByTier[tier] ?? 0) + 1;
  }
  const scoutsByType: Record<string, number> = {};
  for (const row of scoutsRes.data ?? []) {
    const type = (row as { type: string | null }).type ?? "unknown";
    scoutsByType[type] = (scoutsByType[type] ?? 0) + 1;
  }

  return {
    year,
    month,
    orgs: orgSummaries,
    individuals,
    total_org_credits: totalOrgCredits,
    total_org_capped_credits: totalOrgCapped,
    total_org_revenue: totalOrgRevenue,
    total_individual_credits: totalIndividualCredits,
    users_by_tier: usersByTier,
    active_scouts_by_type: scoutsByType,
    rate_per_credit: RATE_PER_CREDIT,
    credit_cap_per_org: CREDIT_CAP_PER_ORG,
  };
}

async function buildUsage(
  svc: SupabaseClient,
  startDate: string,
  endDate: string,
  filters: { orgId: string | null; userId: string | null },
): Promise<UsageResponse> {
  let query = svc
    .from("usage_records")
    .select("id, user_id, org_id, scout_id, scout_type, operation, cost, created_at")
    .gte("created_at", startDate)
    .lte("created_at", `${endDate}T23:59:59Z`);
  if (filters.orgId) query = query.eq("org_id", filters.orgId);
  if (filters.userId) query = query.eq("user_id", filters.userId);

  const { data, error } = await query.order("created_at", { ascending: false }).limit(1000);
  if (error) throw new Error(error.message);
  const rows = (data ?? []) as Array<
    UsageRow & { id: string }
  >;

  const records: UsageRecord[] = rows.map((row) => ({
    user_id: row.user_id ?? "",
    org_id: row.org_id ?? "",
    amount: row.cost,
    operation: row.operation,
    scout_name: row.scout_id ?? "",
    scout_type: row.scout_type ?? "",
    timestamp: row.created_at,
  }));
  const total = records.reduce((acc, r) => acc + r.amount, 0);
  const byOp: Record<string, number> = {};
  for (const r of records) {
    byOp[r.operation] = (byOp[r.operation] ?? 0) + r.amount;
  }
  return { records, total_credits: total, by_operation: byOp };
}

async function sendReportEmail(
  report: MonthlyReport,
): Promise<{ status: string; recipients: string[] }> {
  const resendKey = Deno.env.get("RESEND_API_KEY");
  if (!resendKey) throw new Error("RESEND_API_KEY not configured");

  const admins = (Deno.env.get("ADMIN_EMAILS") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (admins.length === 0) throw new Error("ADMIN_EMAILS not configured");

  const monthName = new Date(Date.UTC(report.year, report.month - 1, 1))
    .toLocaleString("en-US", { month: "long", timeZone: "UTC" });
  const subject = `coJournalist Revenue Report — ${monthName} ${report.year}`;
  const html = buildReportHtml(report, monthName);

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${resendKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: "coJournalist <noreply@cojournalist.ai>",
      to: admins,
      subject,
      html,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`resend failed: ${res.status} ${text.slice(0, 300)}`);
  }
  await res.body?.cancel();
  return { status: "sent", recipients: admins };
}

function buildReportHtml(report: MonthlyReport, monthName: string): string {
  const orgRows = report.orgs
    .map((org) => {
      const ops = Object.entries(org.by_operation)
        .map(([k, v]) => `${escapeHtml(k)}: ${v}`)
        .join(", ") || "—";
      return `
        <tr>
          <td style="padding: 8px; border-bottom: 1px solid #eee;">${escapeHtml(org.org_name || org.org_id.slice(0, 8))}</td>
          <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${org.total_credits.toLocaleString()}</td>
          <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${org.capped_credits.toLocaleString()}</td>
          <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">$${org.revenue.toFixed(2)}</td>
          <td style="padding: 8px; border-bottom: 1px solid #eee; font-size: 12px;">${ops}</td>
        </tr>`;
    })
    .join("");

  const tiers = report.users_by_tier;
  const scouts = report.active_scouts_by_type;
  const scoutPills = Object.entries(scouts)
    .map(([k, v]) => `${escapeHtml(k)}: ${v}`)
    .join(" · ") || "None";

  return `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 700px; margin: 0 auto;">
      <h1 style="color: #1a1a1a; font-size: 24px;">coJournalist Revenue Report</h1>
      <p style="color: #666; font-size: 14px;">${monthName} ${report.year}</p>

      <h2 style="color: #1a1a1a; font-size: 18px; margin-top: 32px;">Organization Credit Usage</h2>
      <table style="width: 100%; border-collapse: collapse;">
        <thead>
          <tr style="background: #f5f5f5;">
            <th style="padding: 8px; text-align: left;">Organization</th>
            <th style="padding: 8px; text-align: right;">Credits Used</th>
            <th style="padding: 8px; text-align: right;">Billable (capped)</th>
            <th style="padding: 8px; text-align: right;">Revenue</th>
            <th style="padding: 8px; text-align: left;">Breakdown</th>
          </tr>
        </thead>
        <tbody>${orgRows || `<tr><td colspan="5" style="padding:8px; color:#888;">No org usage this month</td></tr>`}</tbody>
        <tfoot>
          <tr style="font-weight: bold; border-top: 2px solid #333;">
            <td style="padding: 8px;">Total</td>
            <td style="padding: 8px; text-align: right;">${report.total_org_credits.toLocaleString()}</td>
            <td style="padding: 8px; text-align: right;">${report.total_org_capped_credits.toLocaleString()}</td>
            <td style="padding: 8px; text-align: right;">$${report.total_org_revenue.toFixed(2)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>

      <p style="color: #666; font-size: 12px; margin-top: 8px;">
        Rate: $${report.rate_per_credit}/credit · Cap: ${report.credit_cap_per_org.toLocaleString()} credits/org/month
      </p>

      <h2 style="color: #1a1a1a; font-size: 18px; margin-top: 32px;">Business Metrics</h2>
      <table style="border-collapse: collapse;">
        <tr><td style="padding: 4px 16px 4px 0; color: #666;">Users by tier:</td>
            <td>Free: ${tiers.free ?? 0} · Pro: ${tiers.pro ?? 0} · Team: ${tiers.team ?? 0}</td></tr>
        <tr><td style="padding: 4px 16px 4px 0; color: #666;">Active orgs:</td>
            <td>${report.orgs.length}</td></tr>
        <tr><td style="padding: 4px 16px 4px 0; color: #666;">Active scouts:</td>
            <td>${scoutPills}</td></tr>
      </table>

      <p style="color: #999; font-size: 11px; margin-top: 32px;">
        Generated ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC · coJournalist Admin
      </p>
    </div>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
