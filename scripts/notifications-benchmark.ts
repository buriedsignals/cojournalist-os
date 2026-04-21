/**
 * Standalone notifications-benchmark runner.
 *
 * Renders one sample email per scout type using the same shared template
 * code as the Edge Functions, then POSTs each to Resend. Use this to
 * eyeball email styling in Gmail/Apple Mail/Outlook without deploying
 * the `notifications-benchmark` Edge Function to production.
 *
 *   RESEND_API_KEY=... deno run --allow-env --allow-net --allow-read=. \
 *     scripts/notifications-benchmark.ts [email] [language] [runs]
 *
 * Defaults: email=tom@buriedsignals.com, language=en, runs=1.
 * Sends runs * 4 emails (page + beat + civic + social) per run.
 */

// Intentionally imports the ACTUAL shared helpers used by the Edge
// Functions, so this script is a true mirror of production behavior.
import { buildBaseHtml, escapeHtml } from "../supabase/functions/_shared/notifications.ts";
import { getString } from "../supabase/functions/_shared/email_translations.ts";

const args = Deno.args;
const email = args[0] ?? "tom@buriedsignals.com";
const language = args[1] ?? "en";
const runs = Math.max(1, parseInt(args[2] ?? "1", 10) || 1);

const FROM = "coJournalist <info@cojournalist.ai>";
const REPLY_TO = "info@cojournalist.ai";
const RESEND_URL = "https://api.resend.com/emails";

const resendKey = Deno.env.get("RESEND_API_KEY");
if (!resendKey) {
  console.error("RESEND_API_KEY not set. Source your .env first.");
  Deno.exit(2);
}

type ScoutType = "page" | "beat" | "civic" | "social";
const TYPES: ScoutType[] = ["page", "beat", "civic", "social"];

async function send(
  subject: string,
  html: string,
): Promise<{ ok: boolean; status: number; detail?: string }> {
  const res = await fetch(RESEND_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${resendKey}`,
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
  const detail = ok ? undefined : (await res.text()).slice(0, 500);
  if (ok) {
    try {
      await res.body?.cancel();
    } catch {
      /* stream already consumed or locked */
    }
  }
  return { ok, status: res.status, detail };
}

function pageSample(tag: string) {
  const headerTitle = getString("scout_alert", language);
  const monitoringLabel = getString("monitoring_url", language);
  const criteriaLabel = getString("criteria", language);
  const seeWhatMatched = getString("see_what_matched", language);
  const cueText = getString("page_scout_cue", language);
  const scoutName = `[BENCHMARK ${tag}] Oakland City Hall`;
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
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${escapeHtml(monitoringLabel)}</p>
      <a href="${escapeHtml(url)}" style="color: #2563eb; text-decoration: none; word-break: break-all;">${escapeHtml(url)}</a>
    </div>
    <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${escapeHtml(criteriaLabel)}</p>
      <p style="margin: 0; color: #333;">${escapeHtml(criteria)}</p>
    </div>
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(cueText)}
    </div>
  `;

  return {
    subject: `\uD83D\uDD0E Page Scout: ${scoutName}`,
    html: buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(scoutName),
      headerGradient: "#1a1a2e",
      accentColor: "#2563eb",
      contextLabel: getString("page_scout", language),
      summary,
      articles: [{ title: matchedTitle, url: matchedUrl, summary: "", source: "" }],
      articlesSectionTitle: seeWhatMatched,
      extraContent,
      language,
    }),
  };
}

function beatSample(tag: string) {
  const headerTitle = getString("beat_scout", language);
  const sectionTitle = getString("top_stories", language);
  const scoutName = `[BENCHMARK ${tag}] Zurich climate beat`;
  const location = "Zurich, Switzerland";
  const summary =
    "- Canton opens bids for city-wide e-bus fleet.\n" +
    "- Protest outside parliament against cut to solar subsidies.\n" +
    "- Vote scheduled May 15 on road pricing proposal.";
  const cueHtml = `<div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">${escapeHtml(getString("pulse_scout_cue", language))}</div>`;
  return {
    subject: `\uD83D\uDCE1 Beat Scout: ${location} \u2014 ${scoutName}`,
    html: buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(scoutName),
      headerGradient: ["#7c3aed", "#6d28d9"],
      accentColor: "#7c3aed",
      contextLabel: escapeHtml(location.toUpperCase()),
      summary,
      articles: [
        { title: "Canton opens bids for e-bus fleet", url: "https://nzz.example/article-1", summary: "Fleet replacement contract expected to run to 2030.", source: "nzz.example" },
        { title: "Solar subsidy cuts spark protest", url: "https://tagesanzeiger.example/article-2", summary: "Hundreds gathered at parliament Thursday evening.", source: "tagesanzeiger.example" },
        { title: "Road pricing vote scheduled", url: "https://srf.example/article-3", summary: "Outcome will set precedent for other Swiss cantons.", source: "srf.example" },
      ],
      articlesSectionTitle: sectionTitle,
      extraContent: cueHtml,
      language,
    }),
  };
}

function civicSample(tag: string) {
  const headerTitle = getString("civic_scout", language);
  const scoutName = `[BENCHMARK ${tag}] Oakland Council watch`;
  const summary =
    "- **Commit to cutting fleet emissions 30% by 2028** ([April minutes](https://oakland.example/minutes-2026-04.pdf))\n" +
    "- **Approve $12M transit fund** ([Resolution 2026-042](https://oakland.example/res-2026-042.pdf))\n" +
    "- **Reopen public comment on zoning map** ([Agenda](https://oakland.example/agenda-2026-05.pdf))";
  const cueHtml = `<div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">${escapeHtml(getString("civic_scout_cue", language))}</div>`;
  return {
    subject: `\uD83C\uDFDB\uFE0F Civic Scout: ${scoutName}`,
    html: buildBaseHtml({
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
    }),
  };
}

function socialSample(tag: string) {
  const headerTitle = getString("social_scout", language);
  const newPostsLabel = getString("new_posts", language);
  const removedPostsLabel = getString("removed_posts", language);
  const removedLabel = getString("removed_label", language);
  const profileLabel = getString("profile_label", language);
  const scoutName = `[BENCHMARK ${tag}] Mayor Khan watch`;
  const handle = "SadiqKhan";
  const platform = "x";
  const profileUrl = `https://twitter.com/${handle}`;
  const summary =
    "Three new posts in the past 24 hours: a transit zone update, a climate milestone, and a response to opposition.";
  const extraContent = `
    <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
      <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">${escapeHtml(profileLabel)}</p>
      <a href="${escapeHtml(profileUrl)}" style="color: #e11d48; text-decoration: none;">${escapeHtml(profileUrl)}</a>
    </div>
    <div style="margin-bottom: 16px; font-size: 12px; color: #9ca3af; font-style: italic;">
      ${escapeHtml(getString("social_scout_cue", language))}
    </div>
  `;
  const removedHtml =
    `<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">` +
    `<h3 style="margin: 0 0 12px 0; color: #333;">${escapeHtml(removedPostsLabel)}</h3>` +
    `<div style="margin-bottom: 8px; padding: 8px; background: #fff3f3; border-radius: 4px;">` +
    `<span style="color: #dc2626; font-weight: 600;">${escapeHtml(removedLabel)}</span> An older post about budget revisions has been deleted from the profile.</div>` +
    `</div>`;
  return {
    subject: `\uD83D\uDCAC Social Scout: @${handle} \u2014 ${scoutName}`,
    html: buildBaseHtml({
      headerTitle,
      headerSubtitle: escapeHtml(scoutName),
      headerGradient: ["#e11d48", "#be123c"],
      accentColor: "#e11d48",
      contextLabel: `@${escapeHtml(handle)} on ${escapeHtml(platform.toUpperCase())}`,
      summary,
      articles: [
        { title: `@${handle}`, url: "https://twitter.com/SadiqKhan/status/1", summary: "ULEZ expansion has cut roadside NO2 by 46% in outer London.", source: platform },
        { title: `@${handle}`, url: "https://twitter.com/SadiqKhan/status/2", summary: "London on track for the zero-emission bus fleet pledge.", source: platform },
        { title: `@${handle}`, url: "https://twitter.com/SadiqKhan/status/3", summary: "Responding to tonight's debate on transit funding.", source: platform },
      ],
      articlesSectionTitle: newPostsLabel,
      extraContent,
      postContent: removedHtml,
      language,
    }),
  };
}

function build(type: ScoutType, tag: string) {
  switch (type) {
    case "page":   return pageSample(tag);
    case "beat":   return beatSample(tag);
    case "civic":  return civicSample(tag);
    case "social": return socialSample(tag);
  }
}

const results: { run: number; type: ScoutType; ok: boolean; status: number; subject: string; detail?: string }[] = [];
for (let i = 1; i <= runs; i++) {
  const tag = runs === 1 ? "" : `#${i}`;
  for (const type of TYPES) {
    const { subject, html } = build(type, tag);
    const r = await send(subject, html);
    results.push({ run: i, type, ...r, subject });
    console.log(
      `[run ${i}/${runs}] ${type.padEnd(6)} -> ${r.ok ? "OK" : "FAIL"} (HTTP ${r.status})${r.detail ? " " + r.detail : ""}`,
    );
  }
}

const ok = results.filter((r) => r.ok).length;
const fail = results.length - ok;
console.log(`\nSent ${ok}/${results.length} (${fail} failed) to ${email} in language=${language}.`);
Deno.exit(fail === 0 ? 0 : 1);
