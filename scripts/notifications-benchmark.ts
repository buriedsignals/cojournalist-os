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

import { buildBaseHtml } from "../supabase/functions/_shared/notifications.ts";
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
  const scoutName = `[BENCHMARK ${tag}] Oakland City Hall`;
  const url = "https://www.oaklandca.gov/news";
  return {
    subject: `🔎 Page Scout: ${scoutName}`,
    html: buildBaseHtml({
      variant: "page",
      eyebrowLabel: getString("page_scout", language),
      contextLabel: getString("scout_alert", language),
      headerTitle: getString("scout_alert", language),
      headerSubtitle: scoutName,
      summary:
        "- Council approved a $12M transit fund for zero-emission buses.\n" +
        "- Commitment to reduce city-fleet emissions by 30% by 2028.\n" +
        "- Public comment period opens May 1.",
      articles: [{
        title: "Council approves $12M transit fund",
        url: "https://www.oaklandca.gov/news/press-release-042026",
        summary: "New language added to the public notice and funding memo.",
        source: "oaklandca.gov",
      }],
      articlesSectionTitle: getString("see_what_matched", language),
      metadataPanels: [
        {
          label: getString("monitoring_url", language),
          value: url,
          href: url,
        },
        {
          label: getString("criteria", language),
          value: "climate action, transit funding",
        },
      ],
      cueText: getString("page_scout_cue", language),
      language,
    }),
  };
}

function beatSample(tag: string) {
  const scoutName = `[BENCHMARK ${tag}] Zurich climate beat`;
  const location = "Zurich, Switzerland";
  return {
    subject: `📡 Beat Scout: ${location} — ${scoutName}`,
    html: buildBaseHtml({
      variant: "beat",
      eyebrowLabel: getString("beat_scout", language),
      contextLabel: location.toUpperCase(),
      headerTitle: getString("beat_scout", language),
      headerSubtitle: scoutName,
      summary: "- Canton opens bids for city-wide e-bus fleet.\n" +
        "- Protest outside parliament against cut to solar subsidies.\n" +
        "- Vote scheduled May 15 on road pricing proposal.",
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
      articlesSectionTitle: getString("top_stories", language),
      cueText: getString("beat_scout_cue", language),
      secondarySection: {
        title: getString("government_municipal", language),
        summary:
          "- City transport committee published a revised cost estimate.\n" +
          "- Final vote now expected next Tuesday.",
        articles: [{
          title: "Transport committee memo",
          url: "https://stadt-zurich.example/memo",
          summary: "Updated procurement and scheduling details.",
          source: "stadt-zurich.example",
        }],
      },
      language,
    }),
  };
}

function civicSample(tag: string) {
  const scoutName = `[BENCHMARK ${tag}] Oakland Council watch`;
  return {
    subject: `🏛️ Civic Scout: ${scoutName}`,
    html: buildBaseHtml({
      variant: "civic",
      eyebrowLabel: getString("civic_scout", language),
      contextLabel: getString("key_findings", language),
      headerTitle: getString("civic_scout", language),
      headerSubtitle: scoutName,
      summary:
        "- **Commit to cutting fleet emissions 30% by 2028** ([April minutes](https://oakland.example/minutes-2026-04.pdf))\n" +
        "- **Approve $12M transit fund** ([Resolution 2026-042](https://oakland.example/res-2026-042.pdf))\n" +
        "- **Reopen public comment on zoning map** ([Agenda](https://oakland.example/agenda-2026-05.pdf))",
      articles: [],
      articlesSectionTitle: "",
      cueText: getString("civic_scout_cue", language),
      language,
    }),
  };
}

function socialSample(tag: string) {
  const scoutName = `[BENCHMARK ${tag}] Mayor Khan watch`;
  const handle = "SadiqKhan";
  const platform = "x";
  const profileUrl = `https://twitter.com/${handle}`;
  return {
    subject: `💬 Social Scout: @${handle} — ${scoutName}`,
    html: buildBaseHtml({
      variant: "social",
      eyebrowLabel: getString("social_scout", language),
      contextLabel: `@${handle} on ${platform.toUpperCase()}`,
      headerTitle: getString("social_scout", language),
      headerSubtitle: scoutName,
      summary:
        "Three new posts in the past 24 hours: a transit zone update, a climate milestone, and a response to opposition.",
      articles: [
        {
          title: `@${handle}`,
          url: "https://twitter.com/SadiqKhan/status/1",
          summary:
            "ULEZ expansion has cut roadside NO2 by 46% in outer London.",
          source: platform,
        },
        {
          title: `@${handle}`,
          url: "https://twitter.com/SadiqKhan/status/2",
          summary: "London remains on track for the zero-emission bus pledge.",
          source: platform,
        },
        {
          title: `@${handle}`,
          url: "https://twitter.com/SadiqKhan/status/3",
          summary: "Responding to tonight's debate on transit funding.",
          source: platform,
        },
      ],
      articlesSectionTitle: getString("new_posts", language),
      metadataPanels: [{
        label: getString("profile_label", language),
        value: profileUrl,
        href: profileUrl,
      }],
      cueText: getString("social_scout_cue", language),
      cautionSection: {
        title: getString("removed_posts", language),
        items: [
          `${
            getString("removed_label", language)
          } An older post about budget revisions has been deleted from the profile.`,
        ],
      },
      language,
    }),
  };
}

function build(type: ScoutType, tag: string) {
  switch (type) {
    case "page":
      return pageSample(tag);
    case "beat":
      return beatSample(tag);
    case "civic":
      return civicSample(tag);
    case "social":
      return socialSample(tag);
  }
}

const results: Array<{
  run: number;
  type: ScoutType;
  ok: boolean;
  status: number;
  subject: string;
  detail?: string;
}> = [];

for (let i = 1; i <= runs; i++) {
  const tag = runs === 1 ? "" : `#${i}`;
  for (const type of TYPES) {
    const { subject, html } = build(type, tag);
    const r = await send(subject, html);
    results.push({ run: i, type, ...r, subject });
    console.log(
      `[run ${i}/${runs}] ${type.padEnd(6)} -> ${
        r.ok ? "OK" : "FAIL"
      } (HTTP ${r.status})${r.detail ? " " + r.detail : ""}`,
    );
  }
}

const ok = results.filter((r) => r.ok).length;
const fail = results.length - ok;
console.log(
  `\nSent ${ok}/${results.length} (${fail} failed) to ${email} in language=${language}.`,
);
Deno.exit(fail === 0 ? 0 : 1);
