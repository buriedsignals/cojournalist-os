/**
 * admin-report Edge Function — revenue reporting for MuckRock pilot invoicing.
 *
 * Ports the admin endpoints from the legacy FastAPI backend
 * (backend/app/routers/admin.py + services/admin_report_service.py). Guarded
 * by ADMIN_EMAILS — only users whose JWT email matches a comma-separated
 * entry can hit any route.
 *
 * Routes:
 *   GET  /admin-report/metrics                      — current snapshot
 *   POST /admin-report/report/monthly?year=Y&month=M — invoice JSON
 *   POST /admin-report/report/send-email?year=Y&month=M — email via Resend
 *   GET  /admin-report/usage?start_date=...&end_date=...[&org_id=..][&user_id=..]
 *
 * All responses are JSON. The legacy `GET /admin/` browser dashboard isn't
 * ported — the frontend in frontend/src/routes/admin/ renders its own UI from
 * the JSON responses.
 */

import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { getServiceClient, SupabaseClient } from "../_shared/supabase.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { AuthError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

interface MetricsResponse {
  total_users: number;
  users_by_tier: Record<string, number>;
  orgs: Array<{ id: string; name: string; seated_count: number; monthly_cap: number; balance: number }>;
  total_scouts: number;
  scouts_by_type: Record<string, number>;
}

interface MonthlyReportResponse {
  year: number;
  month: number;
  period_start: string;
  period_end: string;
  total_cost: number;
  operations: Record<string, { count: number; cost: number }>;
  scouts_by_type: Record<string, { count: number; cost: number }>;
  unique_users: number;
  unique_orgs: number;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  try {
    requireAdmin(user);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  const path = url.pathname.replace(/^.*\/admin-report/, "") || "/";
  const svc = getServiceClient();

  try {
    if (path === "/metrics" && req.method === "GET") {
      return jsonOk(await buildMetrics(svc));
    }
    if (path === "/report/monthly" && req.method === "POST") {
      const year = parseIntParam(url.searchParams.get("year"), 2024, 2030);
      const month = parseIntParam(url.searchParams.get("month"), 1, 12);
      if (year == null || month == null) {
        return jsonError("year/month required", 400);
      }
      return jsonOk(await buildMonthlyReport(svc, year, month));
    }
    if (path === "/report/send-email" && req.method === "POST") {
      const year = parseIntParam(url.searchParams.get("year"), 2024, 2030);
      const month = parseIntParam(url.searchParams.get("month"), 1, 12);
      if (year == null || month == null) {
        return jsonError("year/month required", 400);
      }
      const report = await buildMonthlyReport(svc, year, month);
      return jsonOk(await sendReportEmail(user, report));
    }
    if (path === "/usage" && req.method === "GET") {
      const start = url.searchParams.get("start_date");
      const end = url.searchParams.get("end_date");
      if (!isDate(start) || !isDate(end)) {
        return jsonError("start_date and end_date required (YYYY-MM-DD)", 400);
      }
      return jsonOk(await buildUsage(svc, start!, end!, {
        orgId: url.searchParams.get("org_id"),
        userId: url.searchParams.get("user_id"),
      }));
    }
    return jsonError("not found", 404);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "admin-report",
      event: "unhandled",
      path,
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
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
  const [usersRes, orgsRes, scoutsRes] = await Promise.all([
    svc.from("user_preferences").select("tier"),
    svc
      .from("orgs")
      .select("id, name, credit_accounts!inner(seated_count, monthly_cap, balance)")
      .eq("is_individual", false),
    svc.from("scouts").select("type"),
  ]);

  if (usersRes.error) throw new Error(usersRes.error.message);
  if (orgsRes.error) throw new Error(orgsRes.error.message);
  if (scoutsRes.error) throw new Error(scoutsRes.error.message);

  const usersByTier: Record<string, number> = {};
  for (const row of usersRes.data ?? []) {
    const tier = (row as { tier: string | null }).tier ?? "free";
    usersByTier[tier] = (usersByTier[tier] ?? 0) + 1;
  }

  const scoutsByType: Record<string, number> = {};
  for (const row of scoutsRes.data ?? []) {
    const type = (row as { type: string | null }).type ?? "unknown";
    scoutsByType[type] = (scoutsByType[type] ?? 0) + 1;
  }

  const orgs = (orgsRes.data ?? []).map((row) => {
    const org = row as {
      id: string;
      name: string;
      credit_accounts: Array<{ seated_count: number; monthly_cap: number; balance: number }>;
    };
    const credit = org.credit_accounts?.[0] ?? { seated_count: 0, monthly_cap: 0, balance: 0 };
    return {
      id: org.id,
      name: org.name,
      seated_count: credit.seated_count ?? 0,
      monthly_cap: credit.monthly_cap ?? 0,
      balance: credit.balance ?? 0,
    };
  });

  return {
    total_users: (usersRes.data ?? []).length,
    users_by_tier: usersByTier,
    orgs,
    total_scouts: (scoutsRes.data ?? []).length,
    scouts_by_type: scoutsByType,
  };
}

async function buildMonthlyReport(
  svc: SupabaseClient,
  year: number,
  month: number,
): Promise<MonthlyReportResponse> {
  const start = `${year}-${String(month).padStart(2, "0")}-01`;
  const endDate = new Date(Date.UTC(year, month, 1));
  const end = endDate.toISOString().slice(0, 10);

  const { data, error } = await svc
    .from("usage_records")
    .select("user_id, org_id, scout_type, operation, cost")
    .gte("created_at", start)
    .lt("created_at", end);
  if (error) throw new Error(error.message);
  const rows = (data ?? []) as Array<{
    user_id: string;
    org_id: string | null;
    scout_type: string | null;
    operation: string;
    cost: number;
  }>;

  const operations: Record<string, { count: number; cost: number }> = {};
  const scoutsByType: Record<string, { count: number; cost: number }> = {};
  const users = new Set<string>();
  const orgs = new Set<string>();
  let totalCost = 0;

  for (const row of rows) {
    totalCost += row.cost;
    users.add(row.user_id);
    if (row.org_id) orgs.add(row.org_id);
    const op = operations[row.operation] ?? { count: 0, cost: 0 };
    op.count += 1;
    op.cost += row.cost;
    operations[row.operation] = op;
    const type = row.scout_type ?? "unknown";
    const st = scoutsByType[type] ?? { count: 0, cost: 0 };
    st.count += 1;
    st.cost += row.cost;
    scoutsByType[type] = st;
  }

  return {
    year,
    month,
    period_start: start,
    period_end: end,
    total_cost: totalCost,
    operations,
    scouts_by_type: scoutsByType,
    unique_users: users.size,
    unique_orgs: orgs.size,
  };
}

async function buildUsage(
  svc: SupabaseClient,
  startDate: string,
  endDate: string,
  filters: { orgId: string | null; userId: string | null },
): Promise<{ records: unknown[]; count: number; total_cost: number }> {
  let query = svc
    .from("usage_records")
    .select("id, user_id, org_id, scout_id, scout_type, operation, cost, created_at")
    .gte("created_at", startDate)
    .lte("created_at", `${endDate}T23:59:59Z`);
  if (filters.orgId) query = query.eq("org_id", filters.orgId);
  if (filters.userId) query = query.eq("user_id", filters.userId);

  const { data, error } = await query.order("created_at", { ascending: false }).limit(1000);
  if (error) throw new Error(error.message);
  const records = data ?? [];
  const totalCost = records.reduce((acc, r) => acc + ((r as { cost: number }).cost ?? 0), 0);
  return { records, count: records.length, total_cost: totalCost };
}

async function sendReportEmail(
  _user: AuthedUser,
  report: MonthlyReportResponse,
): Promise<{ status: string; recipients: string[] }> {
  const resendKey = Deno.env.get("RESEND_API_KEY");
  if (!resendKey) {
    throw new Error("RESEND_API_KEY not configured");
  }
  const admins = (Deno.env.get("ADMIN_EMAILS") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (admins.length === 0) {
    throw new Error("ADMIN_EMAILS not configured");
  }

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

function buildReportHtml(report: MonthlyReportResponse, monthName: string): string {
  const opsRows = Object.entries(report.operations)
    .sort((a, b) => b[1].cost - a[1].cost)
    .map(([op, data]) =>
      `<tr><td>${escapeHtml(op)}</td><td align="right">${data.count}</td><td align="right">${data.cost}</td></tr>`
    )
    .join("");
  const typeRows = Object.entries(report.scouts_by_type)
    .sort((a, b) => b[1].cost - a[1].cost)
    .map(([type, data]) =>
      `<tr><td>${escapeHtml(type)}</td><td align="right">${data.count}</td><td align="right">${data.cost}</td></tr>`
    )
    .join("");
  return `
    <div style="font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 24px;">
      <h1 style="margin:0 0 8px 0;">coJournalist Revenue — ${monthName} ${report.year}</h1>
      <p style="color:#555; margin:0 0 16px 0;">${report.period_start} → ${report.period_end}</p>
      <p><strong>Total credits billed:</strong> ${report.total_cost.toLocaleString()}</p>
      <p><strong>Unique users:</strong> ${report.unique_users} — <strong>Unique orgs:</strong> ${report.unique_orgs}</p>
      <h2>By operation</h2>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">
        <thead><tr><th align="left">Operation</th><th align="right">Count</th><th align="right">Credits</th></tr></thead>
        <tbody>${opsRows}</tbody>
      </table>
      <h2>By scout type</h2>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">
        <thead><tr><th align="left">Type</th><th align="right">Count</th><th align="right">Credits</th></tr></thead>
        <tbody>${typeRows}</tbody>
      </table>
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
