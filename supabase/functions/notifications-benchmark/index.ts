/**
 * notifications-benchmark Edge Function — fires one sample email per scout
 * type (Page / Beat / Civic / Social) at a target address via Resend.
 *
 * Purpose: visually confirm the ported HTML templates render correctly across
 * Gmail / Apple Mail / Outlook before wiring real traffic through. Dev/QA
 * tool — NOT scheduled, NOT exposed to end users.
 *
 * Route:
 *   POST /notifications-benchmark
 *     body: { email?: string, language?: string, types?: string[] }
 *     -> 200 { sent: [{ type, ok, error? }, ...] }
 *
 * Defaults:
 *   - email:    tom@buriedsignals.com
 *   - language: "en"
 *   - types:    ["page", "beat", "civic", "social"]
 *
 * Auth: service-role Bearer only. Invoke from the local/remote CLI:
 *   curl -X POST $SUPABASE_URL/functions/v1/notifications-benchmark \
 *     -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
 *     -H "Content-Type: application/json" \
 *     -d '{"email":"tom@buriedsignals.com"}'
 */

import { handleCors } from "../_shared/cors.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { AuthError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";
import { buildBaseHtml, escapeHtml } from "../_shared/notifications.ts";
import { getString } from "../_shared/email_translations.ts";

const RESEND_URL = "https://api.resend.com/emails";
const FROM = "coJournalist <info@cojournalist.ai>";
const REPLY_TO = "info@cojournalist.ai";
const DEFAULT_TO = "tom@buriedsignals.com";
const DEFAULT_TYPES = ["page", "beat", "civic", "social"] as const;

type ScoutType = typeof DEFAULT_TYPES[number];

interface BenchResult {
  type: ScoutType;
  ok: boolean;
  status?: number;
  error?: string;
  subject: string;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const authHeader = req.headers.get("authorization") ??
    req.headers.get("Authorization") ?? "";
  if (!serviceKey || authHeader !== `Bearer ${serviceKey}`) {
    return jsonFromError(new AuthError("service-role key required"));
  }

  const resendKey = Deno.env.get("RESEND_API_KEY") ?? "";
  if (!resendKey) {
    return jsonError("RESEND_API_KEY not configured", 500);
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await req.json()) ?? {};
  } catch {
    // empty body is fine.
  }

  const email = typeof body.email === "string" && body.email.trim()
    ? body.email.trim()
    : DEFAULT_TO;
  const language = typeof body.language === "string" && body.language.trim()
    ? body.language.trim()
    : "en";
  const typesInput = Array.isArray(body.types) && body.types.length > 0
    ? (body.types.filter(
      (t): t is ScoutType =>
        typeof t === "string" &&
        (DEFAULT_TYPES as readonly string[]).includes(t),
    ))
    : ([...DEFAULT_TYPES] as ScoutType[]);

  const results: BenchResult[] = [];
  for (const type of typesInput) {
    const { subject, html } = buildSample(type, language);
    try {
      const res = await fetch(RESEND_URL, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${resendKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          from: FROM,
          to: [email],
          subject,
          html,
          reply_to: REPLY_TO,
        }),
      });
      const ok = res.ok;
      const detail = ok ? "" : (await res.text()).slice(0, 500);
      await res.body?.cancel();
      results.push({
        type,
        ok,
        status: res.status,
        subject,
        ...(ok ? {} : { error: detail }),
      });
    } catch (e) {
      results.push({
        type,
        ok: false,
        subject,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  logEvent({
    level: "info",
    fn: "notifications-benchmark",
    event: "done",
    to: email,
    language,
    sent: results.filter((r) => r.ok).length,
    failed: results.filter((r) => !r.ok).length,
  });

  return jsonOk({ to: email, language, sent: results });
});

// ---------------------------------------------------------------------------
// Sample payloads per scout type — chosen to exercise each distinctive
// template element (criteria boxes, grouped articles, markdown lists,
// removed posts, gradients).
// ---------------------------------------------------------------------------

function buildSample(
  type: ScoutType,
  language: string,
): { subject: string; html: string } {
  switch (type) {
    case "page":
      return buildPageSample(language);
    case "beat":
      return buildBeatSample(language);
    case "civic":
      return buildCivicSample(language);
    case "social":
      return buildSocialSample(language);
  }
}

function buildPageSample(language: string): { subject: string; html: string } {
  const headerTitle = getString("scout_alert", language);
  const contextLabel = getString("page_scout", language);
  const monitoringLabel = getString("monitoring_url", language);
  const criteriaLabel = getString("criteria", language);
  const seeWhatMatched = getString("see_what_matched", language);
  const cueText = getString("page_scout_cue", language);
  const scoutName = "[BENCHMARK] Oakland City Hall";
  const url = "https://www.oaklandca.gov/news";
  const criteria = "climate action, transit funding";
  const matchedUrl = "https://www.oaklandca.gov/news/press-release-042026";
  const matchedTitle = "Council approves $12M transit fund";
  const summary =
    "- Council approved a $12M transit fund for zero-emission buses.\n" +
    "- Commitment to reduce city-fleet emissions by 30% by 2028.\n" +
    "- Public comment period opens May 1.";

  const extraContent = `
    <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
    escapeHtml(monitoringLabel)
  }</p>
      <a href="${
    escapeHtml(url)
  }" style="color: #2563eb; text-decoration: none; word-break: break-all;">${
    escapeHtml(url)
  }</a>
    </div>
    <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
    escapeHtml(criteriaLabel)
  }</p>
      <p style="margin: 0; color: #333;">${escapeHtml(criteria)}</p>
    </div>
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(cueText)}
    </div>
  `;

  const html = buildBaseHtml({
    headerTitle,
    headerSubtitle: escapeHtml(scoutName),
    headerGradient: "#1a1a2e",
    accentColor: "#2563eb",
    contextLabel,
    summary,
    articles: [{
      title: matchedTitle,
      url: matchedUrl,
      summary: "",
      source: "",
    }],
    articlesSectionTitle: seeWhatMatched,
    extraContent,
    language,
  });
  return {
    subject: `\uD83D\uDD0E Page Scout: ${scoutName}`,
    html,
  };
}

function buildBeatSample(language: string): { subject: string; html: string } {
  const headerTitle = getString("beat_scout", language);
  const sectionTitle = getString("top_stories", language);
  const scoutName = "[BENCHMARK] Zurich climate beat";
  const location = "Zurich, Switzerland";
  const summary =
    "- Canton opens bids for city-wide e-bus fleet.\n" +
    "- Protest outside parliament against cut to solar subsidies.\n" +
    "- Vote scheduled May 15 on road pricing proposal.";

  const cueHtml = `
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(getString("pulse_scout_cue", language))}
    </div>
  `;

  const html = buildBaseHtml({
    headerTitle,
    headerSubtitle: escapeHtml(scoutName),
    headerGradient: ["#7c3aed", "#6d28d9"],
    accentColor: "#7c3aed",
    contextLabel: escapeHtml(location.toUpperCase()),
    summary,
    articles: [
      {
        title: "Canton opens bids for e-bus fleet",
        url: "https://nzz.example/article-1",
        summary: "Fleet replacement contract expected to run to 2030.",
        source: "nzz.example",
      },
      {
        title: "Solar subsidy cuts spark protest",
        url: "https://tagesanzeiger.example/article-2",
        summary: "Hundreds gathered at parliament Thursday evening.",
        source: "tagesanzeiger.example",
      },
      {
        title: "Road pricing vote scheduled",
        url: "https://srf.example/article-3",
        summary: "Outcome will set precedent for other Swiss cantons.",
        source: "srf.example",
      },
    ],
    articlesSectionTitle: sectionTitle,
    extraContent: cueHtml,
    language,
  });
  return {
    subject: `\uD83D\uDCE1 Beat Scout: ${location} \u2014 ${scoutName}`,
    html,
  };
}

function buildCivicSample(language: string): { subject: string; html: string } {
  const headerTitle = getString("civic_scout", language);
  const scoutName = "[BENCHMARK] Oakland Council watch";
  const summary =
    "- **Commit to cutting fleet emissions 30% by 2028** ([April minutes](https://oakland.example/minutes-2026-04.pdf))\n" +
    "- **Approve $12M transit fund** ([Resolution 2026-042](https://oakland.example/res-2026-042.pdf))\n" +
    "- **Reopen public comment on zoning map** ([Agenda](https://oakland.example/agenda-2026-05.pdf))";

  const cueHtml = `
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(getString("civic_scout_cue", language))}
    </div>
  `;

  const html = buildBaseHtml({
    headerTitle,
    headerSubtitle: escapeHtml(scoutName),
    headerGradient: ["#d97706", "#b45309"],
    accentColor: "#d97706",
    contextLabel: headerTitle,
    summary,
    articles: [],
    articlesSectionTitle: "",
    extraContent: cueHtml,
    language,
  });
  return {
    subject: `\uD83C\uDFDB\uFE0F Civic Scout: ${scoutName}`,
    html,
  };
}

function buildSocialSample(language: string): { subject: string; html: string } {
  const headerTitle = getString("social_scout", language);
  const newPostsLabel = getString("new_posts", language);
  const removedPostsLabel = getString("removed_posts", language);
  const removedLabel = getString("removed_label", language);
  const profileLabel = getString("profile_label", language);
  const scoutName = "[BENCHMARK] Mayor Khan watch";
  const handle = "SadiqKhan";
  const platform = "x";
  const profileUrl = `https://twitter.com/${handle}`;
  const summary =
    "Three new posts in the past 24 hours: a transit zone update, a climate milestone, and a response to opposition.";

  const extraContent = `
    <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${
    escapeHtml(profileLabel)
  }</p>
      <a href="${
    escapeHtml(profileUrl)
  }" style="color: #e11d48; text-decoration: none;">${escapeHtml(profileUrl)}</a>
    </div>
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(getString("social_scout_cue", language))}
    </div>
  `;

  const removedHtml =
    `<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">` +
    `<h3 style="margin: 0 0 12px 0; color: #333;">${escapeHtml(removedPostsLabel)}</h3>` +
    `<div style="margin-bottom: 8px; padding: 8px; background: #fff3f3; border-radius: 4px;">` +
    `<span style="color: #dc2626; font-weight: 600;">${escapeHtml(removedLabel)}</span> ` +
    `An older post about budget revisions has been deleted from the profile.</div>` +
    `</div>`;

  const html = buildBaseHtml({
    headerTitle,
    headerSubtitle: escapeHtml(scoutName),
    headerGradient: ["#e11d48", "#be123c"],
    accentColor: "#e11d48",
    contextLabel: `@${escapeHtml(handle)} on ${escapeHtml(platform.toUpperCase())}`,
    summary,
    articles: [
      {
        title: `@${handle}`,
        url: "https://twitter.com/SadiqKhan/status/1",
        summary: "ULEZ expansion has cut roadside NO2 by 46% in outer London.",
        source: platform,
      },
      {
        title: `@${handle}`,
        url: "https://twitter.com/SadiqKhan/status/2",
        summary: "London on track for the zero-emission bus fleet pledge.",
        source: platform,
      },
      {
        title: `@${handle}`,
        url: "https://twitter.com/SadiqKhan/status/3",
        summary: "Responding to tonight's debate on transit funding.",
        source: platform,
      },
    ],
    articlesSectionTitle: newPostsLabel,
    extraContent,
    postContent: removedHtml,
    language,
  });
  return {
    subject: `\uD83D\uDCAC Social Scout: @${handle} \u2014 ${scoutName}`,
    html,
  };
}

