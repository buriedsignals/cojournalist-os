/**
 * scouts Edge Function — CRUD + lifecycle for scouts.
 *
 * Routes:
 *   GET    /scouts              list caller's scouts (paginated)
 *   POST   /scouts              create scout
 *   GET    /scouts/:id          fetch a single scout
 *   PATCH  /scouts/:id          update scout
 *   DELETE /scouts/:id          delete scout + unschedule cron
 *   POST   /scouts/:id/run      trigger on-demand run (202 + run_id)
 *   POST   /scouts/:id/pause    set is_active=false + unschedule cron
 *   POST   /scouts/:id/resume   set is_active=true + (re)schedule cron
 *
 * Scout queries run through getUserClient(user.token) so RLS scopes them to
 * the caller. The scheduling/trigger RPCs are SECURITY DEFINER and invoked
 * via getServiceClient() because they touch cron.job and vault secrets.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { getServiceClient, getUserClient } from "../_shared/supabase.ts";
import {
  jsonError,
  jsonFromError,
  jsonOk,
  jsonPaginated,
} from "../_shared/responses.ts";
import {
  ConflictError,
  NotFoundError,
  ValidationError,
} from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { shapeScoutResponse } from "../_shared/db.ts";
import { normalizeSocialHandle } from "../_shared/social_profiles.ts";
import {
  doubleProbe,
  firecrawlChangeTrackingScrape,
  firecrawlScrape,
} from "../_shared/firecrawl.ts";
import { geminiExtract } from "../_shared/gemini.ts";
import { ensureWebBaseline } from "../_shared/web_scout_baseline.ts";
import templates from "../scout-templates/templates.json" with { type: "json" };

interface ScoutTemplate {
  slug: string;
  name: string;
  type: string;
  description: string;
  defaults: Record<string, unknown>;
  fields: Array<{
    key: string;
    label: string;
    required?: boolean;
    multiline?: boolean;
  }>;
  example_fill?: Record<string, unknown>;
}

const TEMPLATES = templates as ScoutTemplate[];

// Fields that are stored as TEXT[] in the scouts table. When the client sends
// these as a newline-separated string (e.g. via a <textarea>), split + trim.
const ARRAY_FIELDS = new Set(["tracked_urls", "priority_sources"]);

const FromTemplateSchema = z.object({
  template_slug: z.string(),
  name: z.string().min(1).max(200),
  fields: z.record(z.unknown()).default({}),
  project_id: z.string().uuid().nullable().optional(),
});

const ScoutType = z.enum(["web", "beat", "social", "civic"]);
const Regularity = z.enum(["daily", "weekly", "monthly"]);
const TimeStr = z.string().regex(/^\d{1,2}:\d{2}$/);
const SocialPlatform = z.enum(["instagram", "x", "facebook", "tiktok"]);
const SocialMonitorMode = z.enum(["summarize", "criteria"]);
const BaselinePostSchema = z.record(z.unknown());
const InitialPromiseSchema = z.object({
  promise_text: z.string().min(1).max(4000),
  context: z.string().max(8000).default(""),
  source_url: z.string().url().max(2000),
  source_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  date_confidence: z.enum(["high", "medium", "low"]),
  criteria_match: z.boolean(),
});

const CreateSchema = z
  .object({
    name: z.string().min(1).max(200),
    type: ScoutType,
    criteria: z.string().max(4000).optional(),
    topic: z.string().max(200).optional(),
    url: z.string().url().max(2000).optional(),
    location: z.record(z.unknown()).optional(),
    source_mode: z.enum(["reliable", "niche"]).optional(),
    excluded_domains: z.array(z.string().max(253)).max(100).optional(),
    regularity: Regularity.optional(),
    schedule_cron: z.string().min(1).max(200).optional(),
    // Legacy schedule fields — server synthesises schedule_cron from these
    // when schedule_cron isn't provided.
    day_number: z.number().int().min(0).max(31).optional(),
    time: TimeStr.optional(),
    provider: z.string().max(100).optional(),
    project_id: z.string().uuid().optional(),
    priority_sources: z.array(z.string().max(500)).max(100).optional(),
    platform: SocialPlatform.optional(),
    profile_handle: z.string().min(1).max(200).optional(),
    monitor_mode: SocialMonitorMode.optional(),
    track_removals: z.boolean().optional(),
    baseline_posts: z.array(BaselinePostSchema).max(100).optional(),
    root_domain: z.string().min(1).max(300).optional(),
    tracked_urls: z.array(z.string().url().max(2000)).min(1).max(20).optional(),
    initial_promises: z.array(InitialPromiseSchema).max(100).optional(),
  })
  .superRefine((v, ctx) => {
    if (v.type === "social") {
      if (!v.platform) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["platform"],
          message: "required for social scouts",
        });
      }
      if (!v.profile_handle?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["profile_handle"],
          message: "required for social scouts",
        });
      }
      if (v.monitor_mode === "criteria" && !v.criteria?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["criteria"],
          message: "required when monitor_mode is criteria",
        });
      }
    }
    if (v.type === "civic") {
      if (!v.root_domain?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["root_domain"],
          message: "required for civic scouts",
        });
      }
      if (!v.tracked_urls?.length) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["tracked_urls"],
          message: "required for civic scouts",
        });
      }
    }
  })
  .refine(
    (v) => v.type !== "civic" || v.regularity === undefined || v.regularity !== "daily",
    { message: "civic scouts support weekly or monthly schedules only", path: ["regularity"] },
  );

const UpdateSchema = z
  .object({
    name: z.string().min(1).max(200).optional(),
    type: ScoutType.optional(),
    criteria: z.string().max(4000).nullable().optional(),
    topic: z.string().max(200).nullable().optional(),
    url: z.string().url().max(2000).nullable().optional(),
    location: z.record(z.unknown()).nullable().optional(),
    source_mode: z.enum(["reliable", "niche"]).nullable().optional(),
    excluded_domains: z.array(z.string().max(253)).max(100).nullable().optional(),
    regularity: Regularity.nullable().optional(),
    schedule_cron: z.string().min(1).max(200).nullable().optional(),
    day_number: z.number().int().min(0).max(31).optional(),
    time: TimeStr.optional(),
    provider: z.string().max(100).nullable().optional(),
    project_id: z.string().uuid().nullable().optional(),
    priority_sources: z.array(z.string().max(500)).max(100).nullable().optional(),
    is_active: z.boolean().optional(),
    platform: SocialPlatform.nullable().optional(),
    profile_handle: z.string().max(200).nullable().optional(),
    monitor_mode: SocialMonitorMode.nullable().optional(),
    track_removals: z.boolean().optional(),
    root_domain: z.string().max(300).nullable().optional(),
    tracked_urls: z.array(z.string().url().max(2000)).max(20).nullable().optional(),
  })
  .refine(
    (v) => v.type !== "civic" || v.regularity == null || v.regularity !== "daily",
    { message: "civic scouts support weekly or monthly schedules only", path: ["regularity"] },
  );

/** Derive a cron expression from the legacy (regularity, day_number, time)
 *  triple the UI's "Set Up Page Scout" modal still sends. day_number is
 *  1=Mon..7=Sun for weekly, 1..31 for monthly, ignored for daily.
 *  Returns null if inputs are insufficient. */
function cronFromParts(
  regularity: string | undefined,
  day: number | undefined,
  time: string | undefined,
): string | null {
  if (!regularity || !time) return null;
  const [hh, mm] = time.split(":").map((s) => parseInt(s, 10));
  if (Number.isNaN(hh) || Number.isNaN(mm)) return null;
  switch (regularity) {
    case "daily":
      return `${mm} ${hh} * * *`;
    case "weekly": {
      // day_number 1=Mon..7=Sun → cron 0=Sun..6=Sat (so 7→0).
      const d = day ?? 1;
      const cronDay = d === 7 ? 0 : d;
      return `${mm} ${hh} * * ${cronDay}`;
    }
    case "monthly":
      return `${mm} ${hh} ${day ?? 1} * *`;
    default:
      return null;
  }
}

Deno.serve(async (req): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  const url = new URL(req.url);
  // Trim the "/scouts" prefix Kong leaves on the path. "/scouts" -> "",
  // "/scouts/<id>" -> "/<id>", "/scouts/<id>/run" -> "/<id>/run".
  const path = url.pathname.replace(/^.*\/scouts/, "") || "/";
  const idMatch = path.match(/^\/([0-9a-f-]{36})$/i);
  const idActionMatch = path.match(/^\/([0-9a-f-]{36})\/(run|pause|resume)$/i);
  const isRead = req.method === "GET" || req.method === "HEAD";

  try {
    if (path === "/" && isRead) {
      return await listScouts(req, user);
    }
    if (path === "/" && req.method === "POST") {
      return await createScout(req, user);
    }
    if (path === "/from-template" && req.method === "POST") {
      return await createScoutFromTemplate(req, user);
    }
    if (path === "/test" && req.method === "POST") {
      return await testScout(req, user);
    }
    if (idMatch && isRead) {
      return await getScout(user, idMatch[1]);
    }
    if (idMatch && req.method === "PATCH") {
      return await updateScout(req, user, idMatch[1]);
    }
    if (idMatch && req.method === "DELETE") {
      return await deleteScout(user, idMatch[1]);
    }
    if (idActionMatch && req.method === "POST") {
      const [, id, action] = idActionMatch;
      if (action === "run") return await runScout(user, id);
      if (action === "pause") return await pauseScout(user, id);
      if (action === "resume") return await resumeScout(user, id);
    }
    return jsonError("method not allowed", 405);
  } catch (e) {
    logEvent({
      level: "error",
      fn: "scouts",
      event: "unhandled",
      user_id: user.id,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonFromError(e);
  }
});

// ---------------------------------------------------------------------------

async function listScouts(req: Request, user: AuthedUser): Promise<Response> {
  const url = new URL(req.url);
  const offset = Math.max(0, parseInt(url.searchParams.get("offset") ?? "0", 10));
  const limit = Math.min(
    100,
    Math.max(1, parseInt(url.searchParams.get("limit") ?? "50", 10)),
  );

  const db = getUserClient(user.token);
  const { data, count, error } = await db
    .from("scouts")
    .select("*", { count: "exact" })
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) throw new Error(error.message);

  const shaped = await Promise.all(
    (data ?? []).map((row) => shapeScoutResponse(db, row)),
  );
  return jsonPaginated(shaped, count ?? 0, offset, limit);
}

/** Pre-parse normalisation: accept legacy field aliases the v1 UI still
 *  sends (`scout_type` → `type`). Also coerces `day_number` from string
 *  if it arrived that way. Doesn't validate — that's zod's job. */
function normalizeScoutBody(raw: unknown): unknown {
  if (typeof raw !== "object" || raw === null) return raw;
  const r = raw as Record<string, unknown>;
  const out: Record<string, unknown> = { ...r };
  if (out.type === undefined && typeof out.scout_type === "string") {
    out.type = out.scout_type;
  }
  delete out.scout_type;
  if (out.type === "pulse") {
    out.type = "beat";
  }
  if (typeof out.day_number === "string") {
    const n = parseInt(out.day_number, 10);
    if (!Number.isNaN(n)) out.day_number = n;
  }
  if (typeof out.profile_handle === "string" && typeof out.platform === "string") {
    const platform = out.platform;
    if (
      platform === "instagram" || platform === "x" || platform === "facebook" ||
      platform === "tiktok"
    ) {
      out.profile_handle = normalizeSocialHandle(platform, out.profile_handle);
    }
  }
  if (typeof out.root_domain === "string") {
    out.root_domain = out.root_domain
      .trim()
      .replace(/^https?:\/\//i, "")
      .replace(/\/+$/, "");
  }
  return out;
}

function needsScheduledBaseline(scout: BaselineableScout): boolean {
  return scout.type === "web" || scout.type === "civic";
}

function normalizeTrackedUrls(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .slice(0, CIVIC_BASELINE_MAX_TRACKED);
}

async function shortHash(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 12);
}

async function stampBaseline(
  svc: ReturnType<typeof getServiceClient>,
  scoutId: string,
  patch: Record<string, unknown> = {},
): Promise<void> {
  const { error } = await svc
    .from("scouts")
    .update({
      baseline_established_at: new Date().toISOString(),
      ...patch,
    })
    .eq("id", scoutId);
  if (error) throw new Error(error.message);
}

async function establishCivicBaseline(
  scout: BaselineableScout,
): Promise<void> {
  const tracked = normalizeTrackedUrls(scout.tracked_urls);
  if (tracked.length === 0) {
    throw new ValidationError("civic scouts require tracked_urls before scheduling");
  }

  for (const url of tracked) {
    await firecrawlChangeTrackingScrape(
      url,
      `civic-${scout.id}-${await shortHash(url)}`.slice(0, 128),
    );
  }
}

async function ensureScheduledBaseline(
  svc: ReturnType<typeof getServiceClient>,
  scout: BaselineableScout,
): Promise<void> {
  if (!needsScheduledBaseline(scout) || scout.baseline_established_at) return;
  if (scout.type === "web") {
    await ensureWebBaseline(svc, scout);
    return;
  }
  await establishCivicBaseline(scout);
  await stampBaseline(svc, scout.id);
}

async function seedSocialBaseline(
  svc: ReturnType<typeof getServiceClient>,
  scoutId: string,
  userId: string,
  platform: z.infer<typeof SocialPlatform>,
  handle: string,
  posts: Array<Record<string, unknown>>,
): Promise<void> {
  if (posts.length === 0) return;
  const { error } = await svc.from("post_snapshots").upsert({
    scout_id: scoutId,
    user_id: userId,
    platform,
    handle,
    post_count: posts.length,
    posts,
    updated_at: new Date().toISOString(),
  }, { onConflict: "scout_id" });
  if (error) throw new Error(error.message);
}

async function seedInitialPromises(
  svc: ReturnType<typeof getServiceClient>,
  scoutId: string,
  userId: string,
  promises: Array<z.infer<typeof InitialPromiseSchema>>,
): Promise<void> {
  if (promises.length === 0) return;
  const rows = promises.map((promise) => ({
    scout_id: scoutId,
    user_id: userId,
    promise_text: promise.promise_text,
    context: promise.context,
    source_url: promise.source_url,
    meeting_date: promise.source_date,
    due_date: promise.due_date ?? null,
    date_confidence: promise.date_confidence,
  }));
  const { error } = await svc.from("promises").insert(rows);
  if (error) throw new Error(error.message);
}

async function createScout(req: Request, user: AuthedUser): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = CreateSchema.safeParse(normalizeScoutBody(body));
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }

  // Strip legacy schedule fields; synthesise schedule_cron from them when
  // the client didn't provide one explicitly.
  const {
    schedule_cron: explicitCron,
    time,
    day_number,
    baseline_posts,
    initial_promises,
    ...rest
  } = parsed.data;
  const schedule_cron = explicitCron ??
    cronFromParts(rest.regularity, day_number, time);

  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("scouts")
    .insert({
      ...rest,
      schedule_cron: schedule_cron ?? null,
      user_id: user.id,
      is_active: schedule_cron ? true : false,
    })
    .select("*")
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("scout name already exists");
    }
    throw new Error(error.message);
  }

  if (schedule_cron) {
    const svc = getServiceClient();
    const baselineScout: BaselineableScout = {
      ...(data as BaselineableScout),
      tracked_urls: rest.type === "civic" ? rest.tracked_urls ?? data.tracked_urls : data.tracked_urls,
    };
    try {
      if (
        data.type === "social" &&
        data.platform &&
        data.profile_handle &&
        Array.isArray(baseline_posts) &&
        baseline_posts.length > 0
      ) {
        await seedSocialBaseline(
          svc,
          data.id,
          user.id,
          data.platform as z.infer<typeof SocialPlatform>,
          data.profile_handle,
          baseline_posts,
        );
      }
      if (data.type === "civic" && Array.isArray(initial_promises) && initial_promises.length > 0) {
        await seedInitialPromises(svc, data.id, user.id, initial_promises);
      }
    } catch (e) {
      await svc.from("scouts").delete().eq("id", data.id);
      throw e;
    }
    if (needsScheduledBaseline(baselineScout)) {
      try {
        await ensureScheduledBaseline(svc, baselineScout);
      } catch (e) {
        await svc.from("scouts").delete().eq("id", data.id);
        throw e;
      }
    }
    const { error: rpcErr } = await svc.rpc("schedule_scout", {
      p_scout_id: data.id,
      p_cron_expr: schedule_cron,
    });
    if (rpcErr) {
      logEvent({
        level: "warn",
        fn: "scouts",
        event: "schedule_failed",
        user_id: user.id,
        scout_id: data.id,
        msg: rpcErr.message,
      });
    }
  } else {
    const svc = getServiceClient();
    try {
      if (
        data.type === "social" &&
        data.platform &&
        data.profile_handle &&
        Array.isArray(baseline_posts) &&
        baseline_posts.length > 0
      ) {
        await seedSocialBaseline(
          svc,
          data.id,
          user.id,
          data.platform as z.infer<typeof SocialPlatform>,
          data.profile_handle,
          baseline_posts,
        );
      }
      if (data.type === "civic" && Array.isArray(initial_promises) && initial_promises.length > 0) {
        await seedInitialPromises(svc, data.id, user.id, initial_promises);
      }
    } catch (e) {
      await svc.from("scouts").delete().eq("id", data.id);
      throw e;
    }
  }

  logEvent({
    level: "info",
    fn: "scouts",
    event: "created",
    user_id: user.id,
    scout_id: data.id,
  });

  const shaped = await shapeScoutResponse(db, data);
  return jsonOk(shaped, 201);
}

async function getScout(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("scouts")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("scout");
  return jsonOk(await shapeScoutResponse(db, data));
}

async function updateScout(
  req: Request,
  user: AuthedUser,
  id: string,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = UpdateSchema.safeParse(normalizeScoutBody(body));
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "),
    );
  }
  // Synthesize schedule_cron from legacy fields if explicit one not given.
  const { time, day_number, ...rest } = parsed.data;
  if (rest.schedule_cron === undefined && (time !== undefined || day_number !== undefined)) {
    const synth = cronFromParts(rest.regularity ?? undefined, day_number, time);
    if (synth) rest.schedule_cron = synth;
  }
  if (Object.keys(rest).length === 0) {
    throw new ValidationError("no updatable fields provided");
  }
  // Replace parsed.data so the rest of the function sees the cleaned shape.
  (parsed as { data: typeof rest }).data = rest;

  const db = getUserClient(user.token);
  // Fetch current row so we can diff schedule / is_active
  const { data: current, error: readErr } = await db
    .from("scouts")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (readErr) throw new Error(readErr.message);
  if (!current) throw new NotFoundError("scout");

  const nextScout = { ...current, ...parsed.data } as BaselineableScout & {
    schedule_cron?: string | null;
    is_active?: boolean | null;
  };
  const willBeActive = nextScout.is_active === true;
  const willHaveSchedule = typeof nextScout.schedule_cron === "string" &&
    nextScout.schedule_cron.length > 0;
  if (willBeActive && willHaveSchedule) {
    await ensureScheduledBaseline(getServiceClient(), nextScout);
  }

  const { data, error } = await db
    .from("scouts")
    .update(parsed.data)
    .eq("id", id)
    .select("*")
    .maybeSingle();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("scout name already exists");
    }
    throw new Error(error.message);
  }
  if (!data) throw new NotFoundError("scout");

  const svc = getServiceClient();
  const cronChanged =
    Object.prototype.hasOwnProperty.call(parsed.data, "schedule_cron") &&
    parsed.data.schedule_cron !== current.schedule_cron;
  const activeChanged =
    Object.prototype.hasOwnProperty.call(parsed.data, "is_active") &&
    parsed.data.is_active !== current.is_active;

  // Turning is_active off => unschedule, regardless of cron changes.
  if (activeChanged && parsed.data.is_active === false) {
    const { error: rpcErr } = await svc.rpc("unschedule_scout", {
      p_scout_id: id,
    });
    if (rpcErr) {
      logEvent({
        level: "warn",
        fn: "scouts",
        event: "unschedule_failed",
        user_id: user.id,
        scout_id: id,
        msg: rpcErr.message,
      });
    }
  } else if (cronChanged) {
    if (parsed.data.schedule_cron) {
      const { error: rpcErr } = await svc.rpc("schedule_scout", {
        p_scout_id: id,
        p_cron_expr: parsed.data.schedule_cron,
      });
      if (rpcErr) {
        logEvent({
          level: "warn",
          fn: "scouts",
          event: "schedule_failed",
          user_id: user.id,
          scout_id: id,
          msg: rpcErr.message,
        });
      }
    } else {
      const { error: rpcErr } = await svc.rpc("unschedule_scout", {
        p_scout_id: id,
      });
      if (rpcErr) {
        logEvent({
          level: "warn",
          fn: "scouts",
          event: "unschedule_failed",
          user_id: user.id,
          scout_id: id,
          msg: rpcErr.message,
        });
      }
    }
  }

  return jsonOk(await shapeScoutResponse(db, data));
}

async function deleteScout(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  const { error, count } = await db
    .from("scouts")
    .delete({ count: "exact" })
    .eq("id", id);
  if (error) throw new Error(error.message);
  if (!count) throw new NotFoundError("scout");

  const svc = getServiceClient();
  const { error: rpcErr } = await svc.rpc("unschedule_scout", {
    p_scout_id: id,
  });
  if (rpcErr) {
    logEvent({
      level: "warn",
      fn: "scouts",
      event: "unschedule_failed",
      user_id: user.id,
      scout_id: id,
      msg: rpcErr.message,
    });
  }

  return new Response(null, {
    status: 204,
    headers: { "Access-Control-Allow-Origin": "*" },
  });
}

async function runScout(user: AuthedUser, id: string): Promise<Response> {
  // Verify the scout exists for this caller (RLS-scoped).
  const db = getUserClient(user.token);
  const { data: scout, error: readErr } = await db
    .from("scouts")
    .select("id")
    .eq("id", id)
    .maybeSingle();
  if (readErr) throw new Error(readErr.message);
  if (!scout) throw new NotFoundError("scout");

  const svc = getServiceClient();
  const { data: runId, error: rpcErr } = await svc.rpc("trigger_scout_run", {
    p_scout_id: id,
    p_user_id: user.id,
  });
  if (rpcErr) throw new Error(rpcErr.message);

  logEvent({
    level: "info",
    fn: "scouts",
    event: "run_triggered",
    user_id: user.id,
    scout_id: id,
    run_id: typeof runId === "string" ? runId : String(runId),
  });

  return jsonOk({ scout_id: id, run_id: runId }, 202);
}

async function pauseScout(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("scouts")
    .update({ is_active: false })
    .eq("id", id)
    .select("*")
    .maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("scout");

  const svc = getServiceClient();
  const { error: rpcErr } = await svc.rpc("unschedule_scout", {
    p_scout_id: id,
  });
  if (rpcErr) {
    logEvent({
      level: "warn",
      fn: "scouts",
      event: "unschedule_failed",
      user_id: user.id,
      scout_id: id,
      msg: rpcErr.message,
    });
  }

  return jsonOk(await shapeScoutResponse(db, data));
}

async function resumeScout(user: AuthedUser, id: string): Promise<Response> {
  const db = getUserClient(user.token);
  // chk_active_has_schedule requires schedule_cron when is_active=true.
  const { data: current, error: readErr } = await db
    .from("scouts")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (readErr) throw new Error(readErr.message);
  if (!current) throw new NotFoundError("scout");
  if (!current.schedule_cron) {
    throw new ValidationError(
      "cannot resume scout without schedule_cron; set a schedule first",
    );
  }

  const svc = getServiceClient();
  await ensureScheduledBaseline(svc, current as BaselineableScout);

  const { data, error } = await db
    .from("scouts")
    .update({ is_active: true })
    .eq("id", id)
    .select("*")
    .maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new NotFoundError("scout");

  const { error: rpcErr } = await svc.rpc("schedule_scout", {
    p_scout_id: id,
    p_cron_expr: current.schedule_cron,
  });
  if (rpcErr) {
    logEvent({
      level: "warn",
      fn: "scouts",
      event: "schedule_failed",
      user_id: user.id,
      scout_id: id,
      msg: rpcErr.message,
    });
  }

  return jsonOk(await shapeScoutResponse(db, data));
}

async function createScoutFromTemplate(
  req: Request,
  user: AuthedUser,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = FromTemplateSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }

  const { template_slug, name, fields, project_id } = parsed.data;

  const tpl = TEMPLATES.find((t) => t.slug === template_slug);
  if (!tpl) throw new NotFoundError("template");

  // Validate required fields are present and non-empty.
  const missing: string[] = [];
  for (const f of tpl.fields) {
    if (!f.required) continue;
    const v = fields[f.key];
    if (v === undefined || v === null) {
      missing.push(f.key);
      continue;
    }
    if (typeof v === "string" && v.trim() === "") missing.push(f.key);
    if (Array.isArray(v) && v.length === 0) missing.push(f.key);
  }
  if (missing.length > 0) {
    throw new ValidationError(`missing required fields: ${missing.join(", ")}`);
  }

  // Normalise array fields that may come in as newline-separated strings.
  const normalisedFields: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (ARRAY_FIELDS.has(key) && typeof value === "string") {
      normalisedFields[key] = value
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    } else {
      normalisedFields[key] = value;
    }
  }

  const insertRow: Record<string, unknown> = {
    ...tpl.defaults,
    ...normalisedFields,
    name,
    type: tpl.type,
    user_id: user.id,
    is_active: false,
  };
  if (project_id !== undefined) insertRow.project_id = project_id;

  const db = getUserClient(user.token);
  const { data, error } = await db
    .from("scouts")
    .insert(insertRow)
    .select("*")
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new ConflictError("scout name already exists");
    }
    throw new Error(error.message);
  }

  logEvent({
    level: "info",
    fn: "scouts",
    event: "created_from_template",
    user_id: user.id,
    scout_id: data.id,
    template_slug,
  });

  const shaped = await shapeScoutResponse(db, data);
  return jsonOk(shaped, 201);
}

// ---------------------------------------------------------------------------

const TestSchema = z.object({
  url: z.string().url().max(2000),
  criteria: z.string().max(4000).optional(),
  scraperName: z.string().max(200).optional(),
});

const TEST_MARKDOWN_MAX = 15_000;
const CIVIC_BASELINE_MAX_TRACKED = 20;

interface BaselineableScout {
  id: string;
  user_id: string;
  type: "web" | "beat" | "social" | "civic";
  url?: string | null;
  provider?: string | null;
  tracked_urls?: unknown;
  baseline_established_at?: string | null;
}

const TEST_EXTRACTION_SCHEMA: Record<string, unknown> = {
  type: "object",
  properties: {
    matches: { type: "boolean" },
    summary: { type: "string" },
  },
  required: ["matches", "summary"],
};

interface TestExtraction {
  matches: boolean;
  summary: string;
}

async function testScout(
  req: Request,
  user: AuthedUser,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    throw new ValidationError("invalid JSON body");
  }
  const parsed = TestSchema.safeParse(body);
  if (!parsed.success) {
    throw new ValidationError(
      parsed.error.issues.map((i) => i.message).join("; "),
    );
  }
  const { url, criteria } = parsed.data;

  // Run preview scrape AND double-probe baseline verification in parallel,
  // mirroring prod: the probe decides whether this scout can use Firecrawl's
  // changeTracking or needs plain + hash dedup at run-time.
  const tag = `${user.id}#preview-${crypto.randomUUID().slice(0, 8)}`.slice(0, 128);
  const probePromise = doubleProbe(url, tag).catch(
    (): "firecrawl" | "firecrawl_plain" => "firecrawl_plain",
  );

  let scraped;
  try {
    scraped = await firecrawlScrape(url);
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "scouts",
      event: "test_scrape_failed",
      user_id: user.id,
      url,
      msg: e instanceof Error ? e.message : String(e),
    });
    return jsonOk({
      summary: "",
      scraper_status: false,
      criteria_status: false,
      provider: "firecrawl",
    });
  }
  const provider = await probePromise;

  const markdown = (scraped.markdown ?? "").slice(0, TEST_MARKDOWN_MAX);

  if (!markdown.trim()) {
    return jsonOk({
      summary: "No readable content at that URL.",
      scraper_status: false,
      criteria_status: false,
      provider,
    });
  }

  const prompt = criteria
    ? `You are checking whether a web page matches a monitoring criteria.\n\n` +
      `Criteria: ${criteria}\n\n---\n\n${markdown}\n\n---\n\n` +
      `Return { matches: boolean, summary: string }. The summary must be a 1-2 sentence ` +
      `plain-text (no markdown, no navigation chrome) description of the page relative to the criteria.`
    : `Summarize what this web page is about in 1-2 plain-text sentences. ` +
      `Do NOT return raw markdown, navigation, or boilerplate like "Skip to Main Content". ` +
      `Focus on the actual content of the page. Return { matches: true, summary: string }.\n\n` +
      `---\n\n${markdown}`;

  let extraction: TestExtraction;
  try {
    extraction = await geminiExtract<TestExtraction>(
      prompt,
      TEST_EXTRACTION_SCHEMA,
    );
  } catch (_e) {
    return jsonOk({
      summary: "Page scraped successfully (summary unavailable).",
      scraper_status: true,
      criteria_status: false,
      provider: "firecrawl",
    });
  }

  logEvent({
    level: "info",
    fn: "scouts",
    event: "test_preview",
    user_id: user.id,
    url,
    matched: extraction.matches,
  });

  return jsonOk({
    summary: extraction.summary ?? "",
    scraper_status: true,
    // When no criteria, `matches` is meaningless — the LLM returns `true` per
    // the prompt contract; we always set criteria_status=false in that case so
    // the UI doesn't falsely celebrate a match.
    criteria_status: criteria ? !!extraction.matches : false,
    provider,
  });
}
