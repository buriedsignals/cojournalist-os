/**
 * Scout notification emails via Resend. Shared helper called by every worker
 * on its success path.
 *
 * Legacy reference: backend/app/services/notification_service.py. Templates
 * (colors, gradients, layout, copy) are ported verbatim for visual parity.
 *
 * Per-type entry points:
 *   - sendPageScoutAlert   (web  scout, dark blue)
 *   - sendBeatAlert        (pulse scout, purple, formerly "Smart Scout")
 *   - sendCivicAlert       (civic scout, amber)
 *   - sendSocialAlert      (social scout, rose)
 *
 * Contract:
 *   - Never throws. All failures are logged and returned as `false`.
 *   - Fetches recipient email from `auth.users` at send-time (no public-schema
 *     email leak).
 *   - Marks `scout_runs.notification_sent = true` after Resend 200.
 *   - Retries 5xx with exponential backoff (1s, 2s) up to 3 attempts.
 *     Fast-fails 4xx.
 *   - Early-returns if `RESEND_API_KEY` is missing, if the user has no email,
 *     or if the payload is empty (zero new content).
 */

import type { SupabaseClient } from "./supabase.ts";
import { logEvent } from "./log.ts";
import { getString } from "./email_translations.ts";

const RESEND_URL = "https://api.resend.com/emails";
const FROM = "coJournalist <info@cojournalist.ai>";
const REPLY_TO = "info@cojournalist.ai";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Article {
  title: string;
  summary?: string;
  url?: string;
  source?: string;
  originalTitle?: string;
}

export interface SocialPostSummary {
  /** Author handle or name shown as the card title. */
  author?: string;
  /** Post body / caption. Will be truncated to 150 chars. */
  text?: string;
  /** Permalink to the post. */
  url?: string;
}

export interface RemovedPostSummary {
  /** Caption of the now-missing post, already truncated upstream. */
  captionTruncated: string;
}

interface BaseAlertParams {
  userId: string;
  scoutId: string;
  runId: string;
  scoutName: string;
  /** ISO 639-1 code. Falls back to user preference, then English. */
  language?: string;
}

export interface PageScoutAlertParams extends BaseAlertParams {
  url: string;
  criteria?: string | null;
  summary: string;
  matchedUrl?: string | null;
  matchedTitle?: string | null;
}

export interface BeatAlertParams extends BaseAlertParams {
  location?: string | null;
  topic?: string | null;
  summary: string;
  articles: Article[];
  govArticles?: Article[];
  govSummary?: string;
}

export interface CivicAlertParams extends BaseAlertParams {
  summary: string;
}

export interface SocialAlertParams extends BaseAlertParams {
  platform: string;
  handle: string;
  summary: string;
  newPosts: SocialPostSummary[];
  removedPosts?: RemovedPostSummary[];
  topic?: string | null;
}

/**
 * One entry in a promise-digest email. Rendered as a Markdown bullet with the
 * promise text, optional source link, and optional due-date badge.
 */
export interface PromiseDigestItem {
  promiseText: string;
  sourceUrl?: string | null;
  sourceTitle?: string | null;
  dueDate?: string | null;
}

export interface PromiseDigestParams {
  userId: string;
  items: PromiseDigestItem[];
  language?: string | null;
}

export interface ScoutDeactivatedParams {
  userId: string;
  scoutId: string;
  scoutName: string;
  scoutType: "web" | "pulse" | "civic" | "social" | string;
  consecutiveFailures: number;
  language?: string | null;
}

interface UserContext {
  email: string | null;
  language: string;
  healthNotificationsEnabled: boolean;
}

// ---------------------------------------------------------------------------
// Public entry points
// ---------------------------------------------------------------------------

export async function sendPageScoutAlert(
  svc: SupabaseClient,
  params: PageScoutAlertParams,
): Promise<boolean> {
  return guarded(svc, "page", params.userId, params.runId, async (ctx) => {
    const language = params.language ?? ctx.language;
    const headerTitle = getString("scout_alert", language);
    const contextLabel = getString("page_scout", language);
    const monitoringLabel = getString("monitoring_url", language);
    const criteriaLabel = getString("criteria", language);
    const cueText = getString("page_scout_cue", language);
    const seeWhatMatched = getString("see_what_matched", language);

    const urlEscaped = escapeHtml(params.url);
    const criteriaSection = params.criteria
      ? `
      <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
        <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
        escapeHtml(criteriaLabel)
      }</p>
        <p style="margin: 0; color: #333;">${escapeHtml(params.criteria)}</p>
      </div>
      `
      : "";

    const articles: Article[] = params.matchedUrl && params.matchedTitle
      ? [{
        title: params.matchedTitle,
        url: params.matchedUrl,
        summary: "",
        source: "",
      }]
      : [];
    const articlesSectionTitle = articles.length > 0 ? seeWhatMatched : "";

    const extraContent = `
      <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
        <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
      escapeHtml(monitoringLabel)
    }</p>
        <a href="${urlEscaped}" style="color: #2563eb; text-decoration: none; word-break: break-all;">${urlEscaped}</a>
      </div>
      ${criteriaSection}
      <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
        ${escapeHtml(cueText)}
      </div>
    `;

    const html = buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(params.scoutName),
      headerGradient: "#1a1a2e",
      accentColor: "#2563eb",
      contextLabel,
      summary: params.summary,
      articles,
      articlesSectionTitle,
      extraContent,
      language,
    });

    return {
      subject: `\uD83D\uDD0E Page Scout: ${params.scoutName}`,
      html,
    };
  });
}

export async function sendBeatAlert(
  svc: SupabaseClient,
  params: BeatAlertParams,
): Promise<boolean> {
  return guarded(svc, "beat", params.userId, params.runId, async (ctx) => {
    const language = params.language ?? ctx.language;
    const headerTitle = getString("beat_scout", language);
    const sectionTitle = getString("top_stories", language);

    const contextSource = params.topic ?? params.location ?? "";
    const contextLabel = escapeHtml((contextSource || "").toUpperCase());
    const subjectContext = params.topic ?? params.location ?? params.scoutName;

    const accent = "#7c3aed";
    const pulseCue = `
      <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
        ${escapeHtml(getString("pulse_scout_cue", language))}
      </div>
    `;

    let postContent = "";
    if (params.govArticles && params.govArticles.length > 0) {
      const govTitle = getString("government_municipal", language);
      const govSummaryHtml = params.govSummary
        ? `
        <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 16px; border-left: 4px solid ${accent};">
          ${markdownToHtml(params.govSummary, accent)}
        </div>`
        : "";
      const govCards = renderArticleCards(params.govArticles, accent);
      postContent = `
        <div style="margin-top: 24px; padding-top: 20px; border-top: 2px solid #e5e7eb;">
          <h3 style="margin: 0 0 16px 0; color: #333;">${escapeHtml(govTitle)}</h3>
          ${govSummaryHtml}
          ${govCards}
        </div>`;
    }

    const html = buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(params.scoutName),
      headerGradient: ["#7c3aed", "#6d28d9"],
      accentColor: accent,
      contextLabel,
      summary: params.summary,
      articles: params.articles,
      articlesSectionTitle: sectionTitle,
      extraContent: pulseCue,
      postContent,
      language,
    });

    const beatCtx = subjectContext
      ? `: ${subjectContext} \u2014 ${params.scoutName}`
      : `: ${params.scoutName}`;
    return {
      subject: `\uD83D\uDCE1 Beat Scout${beatCtx}`,
      html,
    };
  });
}

export async function sendCivicAlert(
  svc: SupabaseClient,
  params: CivicAlertParams,
): Promise<boolean> {
  return guarded(svc, "civic", params.userId, params.runId, async (ctx) => {
    const language = params.language ?? ctx.language;
    const headerTitle = getString("civic_scout", language);
    const cueText = getString("civic_scout_cue", language);

    const civicCueHtml = `
      <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
        ${escapeHtml(cueText)}
      </div>
    `;

    const html = buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(params.scoutName),
      headerGradient: ["#d97706", "#b45309"],
      accentColor: "#d97706",
      contextLabel: headerTitle,
      summary: params.summary,
      articles: [],
      articlesSectionTitle: "",
      extraContent: civicCueHtml,
      language,
    });

    return {
      subject: `\uD83C\uDFDB\uFE0F Civic Scout: ${params.scoutName}`,
      html,
    };
  });
}

export async function sendSocialAlert(
  svc: SupabaseClient,
  params: SocialAlertParams,
): Promise<boolean> {
  return guarded(svc, "social", params.userId, params.runId, async (ctx) => {
    const language = params.language ?? ctx.language;
    const headerTitle = getString("social_scout", language);
    const newPostsLabel = getString("new_posts", language);
    const removedPostsLabel = getString("removed_posts", language);
    const removedLabel = getString("removed_label", language);
    const profileLabel = getString("profile_label", language);
    const cueText = getString("social_scout_cue", language);

    const profileUrl = buildProfileUrl(params.platform, params.handle);
    const safeProfileUrl = escapeHtml(profileUrl);
    const safeHandle = escapeHtml(params.handle);

    const articles: Article[] = params.newPosts.slice(0, 5).map((p) => ({
      title: p.author ? `@${p.author}` : "New Post",
      summary: (p.text ?? "").slice(0, 150),
      url: p.url ?? "#",
      source: params.platform,
    }));

    const extraContent = `
      <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
        <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
      escapeHtml(profileLabel)
    }</p>
        <a href="${safeProfileUrl}" style="color: #e11d48; text-decoration: none;">${safeProfileUrl}</a>
      </div>
      <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
        ${escapeHtml(cueText)}
      </div>
    `;

    let postContent = "";
    if (params.removedPosts && params.removedPosts.length > 0) {
      const removalLines = params.removedPosts.slice(0, 5).map((rp) =>
        `<div style="margin-bottom: 8px; padding: 8px; background: #fff3f3; border-radius: 4px;">` +
        `<span style="color: #dc2626; font-weight: 600;">${
          escapeHtml(removedLabel)
        }</span> ${escapeHtml(rp.captionTruncated)}</div>`
      );
      postContent =
        `<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">` +
        `<h3 style="margin: 0 0 12px 0; color: #333;">${
          escapeHtml(removedPostsLabel)
        }</h3>` +
        removalLines.join("\n") +
        `</div>`;
    }

    const html = buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(params.scoutName),
      headerGradient: ["#e11d48", "#be123c"],
      accentColor: "#e11d48",
      contextLabel: `@${safeHandle} on ${escapeHtml(params.platform.toUpperCase())}`,
      summary: params.summary,
      articles,
      articlesSectionTitle: newPostsLabel,
      extraContent,
      postContent,
      language,
    });

    const subject = params.topic
      ? `\uD83D\uDCAC Social Scout: ${params.topic} \u2014 @${params.handle} \u2014 ${params.scoutName}`
      : `\uD83D\uDCAC Social Scout: @${params.handle} \u2014 ${params.scoutName}`;

    return { subject, html };
  });
}

/**
 * Send the daily civic-promise digest to one user. Unlike the scout alerts
 * this is not bound to a single scout_run — the promise-digest Edge Function
 * groups promises due today across every civic scout the user owns. Returns
 * true if Resend accepted the email (so the caller can flip
 * promises.status='notified' for the included rows).
 */
export async function sendCivicPromiseDigest(
  svc: SupabaseClient,
  params: PromiseDigestParams,
): Promise<boolean> {
  const resendKey = Deno.env.get("RESEND_API_KEY") ?? "";
  if (!resendKey) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "resend_key_missing",
      scout_type: "civic_digest",
      user_id: params.userId,
    });
    return false;
  }
  const ctx = await resolveUserContext(svc, params.userId);
  if (!ctx.email) {
    logEvent({
      level: "info",
      fn: "notifications",
      event: "skipped_no_email",
      scout_type: "civic_digest",
      user_id: params.userId,
    });
    return false;
  }
  const language = params.language ?? ctx.language;
  const summary = params.items
    .slice(0, 20)
    .map((item) => {
      const escapedText = escapeMarkdown(item.promiseText);
      const due = item.dueDate ? ` _(due ${item.dueDate})_` : "";
      if (!item.sourceUrl) return `- **${escapedText}**${due}`;
      let label = item.sourceTitle?.trim() || "";
      if (!label) {
        try {
          label = new URL(item.sourceUrl).hostname;
        } catch {
          label = item.sourceUrl;
        }
      }
      const escapedLabel = escapeMarkdown(label).replace(/\]/g, "\\]");
      return `- **${escapedText}**${due} ([${escapedLabel}](${item.sourceUrl}))`;
    })
    .join("\n");

  const n = params.items.length;
  const nounPlural = n === 1 ? "promise" : "promises";
  const html = buildBaseHtml({
    headerTitle: "Civic Digest",
    headerSubtitle: `${n} ${nounPlural} due today`,
    headerGradient: ["#d97706", "#b45309"],
    accentColor: "#d97706",
    contextLabel: "Civic Digest",
    summary,
    articles: [],
    articlesSectionTitle: "",
    language,
  });
  const subject = `📅 Civic Digest: ${n} ${nounPlural} due today`;

  try {
    return await sendWithRetry(resendKey, ctx.email, subject, html);
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "send_failed",
      scout_type: "civic_digest",
      user_id: params.userId,
      msg: e instanceof Error ? e.message : String(e),
    });
    return false;
  }
}

function escapeMarkdown(s: string): string {
  return s.replace(/[\[\]()*_]/g, (c) => `\\${c}`);
}

/**
 * Email a user when one of their scouts has been auto-deactivated after the
 * consecutive-failure threshold (see increment_scout_failures). Legacy
 * scraper-lambda fired the same notification via FastAPI /scouts/failure-notification.
 */
export async function sendScoutDeactivated(
  svc: SupabaseClient,
  params: ScoutDeactivatedParams,
): Promise<boolean> {
  const resendKey = Deno.env.get("RESEND_API_KEY") ?? "";
  if (!resendKey) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "resend_key_missing",
      scout_type: "deactivated",
      user_id: params.userId,
      scout_id: params.scoutId,
    });
    return false;
  }
  const ctx = await resolveUserContext(svc, params.userId);
  if (!ctx.email) return false;
  if (!ctx.healthNotificationsEnabled) {
    logEvent({
      level: "info",
      fn: "notifications",
      event: "skipped_health_opt_out",
      scout_type: "deactivated",
      user_id: params.userId,
      scout_id: params.scoutId,
    });
    return false;
  }

  const language = params.language ?? ctx.language;
  const summary =
    `**${escapeMarkdown(params.scoutName)}** was paused after ` +
    `${params.consecutiveFailures} consecutive failures. ` +
    `Re-enable it in the dashboard once the issue is resolved.`;
  const html = buildBaseHtml({
    headerTitle: "Scout Paused",
    headerSubtitle: escapeHtml(params.scoutName),
    headerGradient: ["#991b1b", "#7f1d1d"],
    accentColor: "#991b1b",
    contextLabel: "Scout Health",
    summary,
    articles: [],
    articlesSectionTitle: "",
    language,
  });
  const subject = `⚠️ Scout paused: ${params.scoutName}`;

  try {
    return await sendWithRetry(resendKey, ctx.email, subject, html);
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "send_failed",
      scout_type: "deactivated",
      user_id: params.userId,
      scout_id: params.scoutId,
      msg: e instanceof Error ? e.message : String(e),
    });
    return false;
  }
}

// ---------------------------------------------------------------------------
// Shared pipeline — all four public entry points route through this.
// ---------------------------------------------------------------------------

async function guarded(
  svc: SupabaseClient,
  scoutType: "page" | "beat" | "civic" | "social",
  userId: string,
  runId: string,
  render: (ctx: UserContext) => Promise<{ subject: string; html: string }>,
): Promise<boolean> {
  try {
    const resendKey = Deno.env.get("RESEND_API_KEY") ?? "";
    if (!resendKey) {
      logEvent({
        level: "warn",
        fn: "notifications",
        event: "resend_key_missing",
        scout_type: scoutType,
        user_id: userId,
        run_id: runId,
      });
      return false;
    }

    const ctx = await resolveUserContext(svc, userId);
    if (!ctx.email) {
      logEvent({
        level: "info",
        fn: "notifications",
        event: "skipped_no_email",
        scout_type: scoutType,
        user_id: userId,
        run_id: runId,
      });
      return false;
    }

    const { subject, html } = await render(ctx);

    const sent = await sendWithRetry(resendKey, ctx.email, subject, html);
    if (!sent) return false;

    const { error: updateErr } = await svc
      .from("scout_runs")
      .update({ notification_sent: true })
      .eq("id", runId);
    if (updateErr) {
      // Send succeeded but flag didn't flip — log so reconciliation can see
      // the inconsistency, but still report success upstream.
      logEvent({
        level: "warn",
        fn: "notifications",
        event: "notification_sent_flag_update_failed",
        scout_type: scoutType,
        user_id: userId,
        run_id: runId,
        msg: updateErr.message,
      });
    }

    logEvent({
      level: "info",
      fn: "notifications",
      event: "sent",
      scout_type: scoutType,
      user_id: userId,
      run_id: runId,
    });
    return true;
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "send_failed",
      scout_type: scoutType,
      user_id: userId,
      run_id: runId,
      msg: e instanceof Error ? e.message : String(e),
    });
    return false;
  }
}

// ---------------------------------------------------------------------------
// User context lookup — email comes from auth.users, language from
// user_preferences. Never stored in public.*.
// ---------------------------------------------------------------------------

export async function resolveUserContext(
  svc: SupabaseClient,
  userId: string,
): Promise<UserContext> {
  let email: string | null = null;
  try {
    const { data, error } = await svc.auth.admin.getUserById(userId);
    if (error) throw new Error(error.message);
    email = data.user?.email ?? null;
  } catch (e) {
    logEvent({
      level: "warn",
      fn: "notifications",
      event: "auth_lookup_failed",
      user_id: userId,
      msg: e instanceof Error ? e.message : String(e),
    });
  }

  let language = "en";
  let healthNotificationsEnabled = true;
  try {
    const { data } = await svc
      .from("user_preferences")
      .select("preferred_language, health_notifications_enabled")
      .eq("user_id", userId)
      .maybeSingle();
    if (data) {
      if (typeof data.preferred_language === "string" && data.preferred_language) {
        language = data.preferred_language;
      }
      if (typeof data.health_notifications_enabled === "boolean") {
        healthNotificationsEnabled = data.health_notifications_enabled;
      }
    }
  } catch {
    // Missing column (pre-migration) or row — defaults stand.
  }

  return { email, language, healthNotificationsEnabled };
}

// ---------------------------------------------------------------------------
// Resend transport
// ---------------------------------------------------------------------------

async function sendWithRetry(
  resendKey: string,
  toEmail: string,
  subject: string,
  html: string,
  maxRetries = 3,
): Promise<boolean> {
  const body = JSON.stringify({
    from: FROM,
    to: [toEmail],
    subject,
    html,
    reply_to: REPLY_TO,
  });

  let lastError: string | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const res = await fetch(RESEND_URL, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${resendKey}`,
          "Content-Type": "application/json",
        },
        body,
      });

      if (res.ok) {
        await res.body?.cancel();
        return true;
      }

      const detail = await safeText(res);
      if (res.status < 500) {
        // Client error — don't retry.
        logEvent({
          level: "error",
          fn: "notifications",
          event: "resend_client_error",
          status: res.status,
          msg: detail.slice(0, 500),
        });
        return false;
      }
      lastError = `HTTP ${res.status}: ${detail.slice(0, 500)}`;
    } catch (e) {
      lastError = e instanceof Error ? e.message : String(e);
    }

    if (attempt < maxRetries - 1) {
      await sleep(1000 * Math.pow(2, attempt));
    }
  }

  logEvent({
    level: "error",
    fn: "notifications",
    event: "resend_exhausted",
    attempts: maxRetries,
    msg: lastError ?? "unknown",
  });
  return false;
}

async function safeText(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Template primitives
// ---------------------------------------------------------------------------

interface BaseHtmlParams {
  headerTitle: string;
  headerSubtitle: string;
  headerGradient: string | [string, string];
  accentColor: string;
  contextLabel: string;
  summary: string;
  articles: Article[];
  articlesSectionTitle: string;
  extraContent?: string;
  postContent?: string;
  ctaText?: string;
  language: string;
}

export function buildBaseHtml(p: BaseHtmlParams): string {
  const bgStyle = Array.isArray(p.headerGradient)
    ? `linear-gradient(135deg, ${p.headerGradient[0]}, ${p.headerGradient[1]})`
    : p.headerGradient;

  const articlesHtml = renderArticleCards(p.articles, p.accentColor);
  const articlesSection = p.articles.length > 0 && p.articlesSectionTitle
    ? `
      <h3 style="margin: 0 0 16px 0; color: #333;">${escapeHtml(p.articlesSectionTitle)}</h3>
      ${articlesHtml}
      `
    : "";

  const summaryHtml = markdownToHtml(p.summary, p.accentColor);

  const ctaSection = p.ctaText
    ? `
      <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center;">
        <a href="https://cojournalist.ai" style="color: ${p.accentColor}; text-decoration: none; font-size: 14px;">
          ${escapeHtml(p.ctaText)}
        </a>
      </div>`
    : "";

  const disclaimer = getString("email_disclaimer", p.language);

  return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto;">
        <div style="background: ${bgStyle}; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">${escapeHtml(p.headerTitle)}</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">${p.headerSubtitle}</p>
        </div>
        <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <div style="margin-bottom: 16px;">
                <span style="font-size: 12px; text-transform: uppercase; color: ${p.accentColor}; font-weight: 600;">
                    ${p.contextLabel}
                </span>
            </div>

            ${p.extraContent ?? ""}

            <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 24px; border-left: 4px solid ${p.accentColor};">
                ${summaryHtml}
            </div>

            ${articlesSection}

            ${p.postContent ?? ""}

            ${ctaSection}

            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 11px; color: #9ca3af; line-height: 1.5;">
                ${disclaimer}
            </div>
        </div>
    </div>
</body>
</html>
`;
}

export function renderArticleCards(
  articles: Article[],
  accentColor: string,
  limit = 5,
): string {
  let out = "";
  for (const article of articles.slice(0, limit)) {
    const url = escapeHtml(article.url ?? "#");
    const title = escapeHtml(article.title ?? "Untitled");
    let summary = article.summary ?? "";
    summary = escapeHtml(summary);
    if (summary.includes("\n")) {
      const lines = summary.split("\n");
      summary = lines.slice(0, 5).join("<br>");
      if (lines.length > 5) summary += "<br>...";
    } else if (summary.length > 150) {
      summary = summary.slice(0, 150) + "...";
    }
    const source = escapeHtml(article.source ?? "");
    const sourceHtml = source
      ? `<span style="font-size: 12px; color: #999;">${source}</span>`
      : "";
    const originalTitle = escapeHtml(article.originalTitle ?? "");
    const originalHtml = originalTitle
      ? `<div style="font-size:11px;color:#9ca3af;margin-top:2px;">Original: ${originalTitle}</div>`
      : "";

    out += `
      <div style="margin-bottom: 12px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
        <a href="${url}" style="color: ${accentColor}; text-decoration: none; font-weight: 600;">
          ${title}
        </a>
        ${originalHtml}
        <p style="margin: 8px 0 0 0; color: #666; font-size: 14px;">
          ${summary}
        </p>
        ${sourceHtml}
      </div>
      `;
  }
  return out;
}

/** Port of `group_facts_by_source` in notification_service.py. */
export interface Fact {
  source_url?: string | null;
  source_title?: string | null;
  source_domain?: string | null;
  statement?: string | null;
}

export function groupFactsBySource(
  facts: Fact[],
  sourceLimit = 5,
): Article[] {
  interface Bucket {
    title: string;
    url: string;
    source: string;
    statements: string[];
  }
  const grouped = new Map<string, Bucket>();
  const order: string[] = [];

  facts.forEach((fact, idx) => {
    const key = fact.source_url || `__no_url_${idx}__`;
    let bucket = grouped.get(key);
    if (!bucket) {
      bucket = {
        title: fact.source_title ?? "Untitled",
        url: fact.source_url ?? "",
        source: fact.source_domain ?? "",
        statements: [],
      };
      grouped.set(key, bucket);
      order.push(key);
    }
    bucket.statements.push(fact.statement ?? "");
  });

  const result: Article[] = [];
  for (const key of order.slice(0, sourceLimit)) {
    const b = grouped.get(key);
    if (!b) continue;
    const summary = b.statements.length === 1
      ? b.statements[0]
      : b.statements.map((s) => `\u2022 ${s}`).join("\n");
    result.push({
      title: b.title,
      summary,
      url: b.url,
      source: b.source,
    });
  }
  return result;
}

/**
 * Port of `markdown_to_html` in notification_service.py. Supports headers (##,
 * ###), bold (**), bullet lists (- * \u2022), links [text](url). HTML in the
 * source is escaped before markdown constructs are restored as safe HTML.
 */
export function markdownToHtml(text: string, accentColor = "#7c6fc7"): string {
  if (!text) return "";

  const lines = text.split("\n");
  const out: string[] = [];
  let inList = false;

  for (const raw of lines) {
    const stripped = raw.trim();

    if (stripped.startsWith("### ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(
        `<h3 style="margin: 16px 0 8px 0; font-size: 16px; color: #333;">${
          escapeHtml(stripped.slice(4))
        }</h3>`,
      );
      continue;
    }
    if (stripped.startsWith("## ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(
        `<h2 style="margin: 20px 0 12px 0; font-size: 18px; color: #333;">${
          escapeHtml(stripped.slice(3))
        }</h2>`,
      );
      continue;
    }

    const listMatch = /^[-*\u2022]\s+(.+)$/.exec(stripped);
    if (listMatch) {
      if (!inList) {
        out.push(`<ul style="margin: 8px 0; padding-left: 20px;">`);
        inList = true;
      }
      const item = processInlineMarkdown(listMatch[1], accentColor);
      out.push(`<li style="margin: 4px 0; color: #333;">${item}</li>`);
      continue;
    }

    if (inList && stripped) {
      out.push("</ul>");
      inList = false;
    }

    if (!stripped) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push("<br>");
      continue;
    }

    const processed = processInlineMarkdown(stripped, accentColor);
    out.push(
      `<p style="margin: 8px 0; color: #333; line-height: 1.6;">${processed}</p>`,
    );
  }

  if (inList) out.push("</ul>");
  return out.join("\n");
}

function processInlineMarkdown(text: string, accentColor: string): string {
  // Same placeholder-swap strategy as the Python version: extract markdown
  // constructs, escape the remaining text, then re-insert them as safe HTML.
  const boldParts: string[] = [];
  const linkParts: Array<[string, string]> = [];

  let t = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, a: string, b: string) => {
    const idx = linkParts.length;
    linkParts.push([a, b]);
    return `\x00LINK${idx}\x00`;
  });
  t = t.replace(/\*\*([^*]+)\*\*/g, (_m, inner: string) => {
    const idx = boldParts.length;
    boldParts.push(inner);
    return `\x00BOLD${idx}\x00`;
  });

  t = escapeHtml(t);

  boldParts.forEach((content, idx) => {
    t = t.replace(
      `\x00BOLD${idx}\x00`,
      `<strong>${escapeHtml(content)}</strong>`,
    );
  });
  linkParts.forEach(([linkText, linkUrl], idx) => {
    t = t.replace(
      `\x00LINK${idx}\x00`,
      `<a href="${escapeHtml(linkUrl)}" style="color: ${accentColor}; text-decoration: none;">${
        escapeHtml(linkText)
      }</a>`,
    );
  });
  return t;
}

export function escapeHtml(s: string | null | undefined): string {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function buildProfileUrl(platform: string, handle: string): string {
  const h = handle.replace(/^@/, "");
  switch (platform.toLowerCase()) {
    case "instagram":
      return `https://instagram.com/${h}`;
    case "x":
    case "twitter":
      return `https://twitter.com/${h}`;
    case "facebook":
      return `https://facebook.com/${h}`;
    case "tiktok":
      return `https://tiktok.com/@${h}`;
    default:
      return `https://${platform}.com/${h}`;
  }
}
