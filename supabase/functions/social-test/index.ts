/**
 * social-test Edge Function — synchronous profile validation + baseline scrape
 * for the Social Scout "Scan Profile" button.
 *
 * Route:
 *   POST /social-test
 *     body: { platform: "instagram"|"x"|"facebook"|"tiktok", handle: string }
 *     -> 200 {
 *       valid: boolean,
 *       profile_url: string,
 *       error?: string,
 *       post_ids: string[],           // baseline IDs the scheduled run will diff against
 *       preview_posts: { id, text, timestamp }[],  // up to 20, truncated to 120 chars
 *       posts_data: { post_id, caption_truncated, image_url, timestamp }[]
 *     }
 *
 * Pipeline:
 *   1. HEAD (or GET for x/tiktok) the profile URL to check it exists.
 *   2. If valid, fire an Apify synchronous actor run (run-sync-get-dataset-items)
 *      with maxItems=20 and return normalized posts. Timeout 120s per platform.
 *   3. Partial-success path: HEAD ok but Apify failed → return valid:true with
 *      empty post arrays and a warning `error` field (prod parity).
 *
 * **Costs REAL money** — every call burns one Apify actor run against the
 * profile. Gate callers accordingly (rate-limit etc.). No credit decrement
 * happens here; the authoritative charge is in `social-kickoff` when the
 * scout is scheduled.
 */

import { z } from "https://esm.sh/zod@3";
import { handleCors } from "../_shared/cors.ts";
import { requireUser, AuthedUser } from "../_shared/auth.ts";
import { jsonError, jsonFromError, jsonOk } from "../_shared/responses.ts";
import { ValidationError } from "../_shared/errors.ts";
import { logEvent } from "../_shared/log.ts";

const InputSchema = z.object({
  platform: z.enum(["instagram", "x", "facebook", "tiktok"]),
  handle: z.string().min(1).max(200),
});

const MAX_ITEMS = 20;
const APIFY_TIMEOUT_SECS = 120;
const PREVIEW_TEXT_MAX = 120;
const CAPTION_TRUNCATED_MAX = 200;

interface ApifyActor {
  id: string;
  buildInput: (url: string) => Record<string, unknown>;
}

// Actor IDs lifted from production `apify_client.py`.
const ACTORS: Record<string, ApifyActor> = {
  instagram: {
    id: "culc72xb7MP3EbaeX", // apidojo/instagram-scraper
    buildInput: (url) => ({ startUrls: [url], maxItems: MAX_ITEMS }),
  },
  x: {
    id: "61RPP7dywgiy0JPD0", // X/Twitter scraper
    buildInput: (url) => {
      const handle = url.split("/").filter(Boolean).pop() || "";
      return {
        startUrls: [url],
        maxItems: MAX_ITEMS,
        twitterHandles: handle ? [handle] : undefined,
      };
    },
  },
  facebook: {
    id: "cleansyntax~facebook-profile-posts-scraper",
    buildInput: (url) => ({
      endpoint: "profile_posts_by_url",
      urls_text: url,
      max_posts: MAX_ITEMS,
    }),
  },
  tiktok: {
    id: "novi~tiktok-user-api",
    buildInput: (url) => ({ startUrls: [url], maxItems: MAX_ITEMS }),
  },
};

interface NormalizedPost {
  id: string;
  text: string;
  timestamp: string;
  imageUrl: string | null;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const cors = handleCors(req);
  if (cors) return cors;

  if (req.method !== "POST") {
    return jsonError("method not allowed", 405);
  }

  let user: AuthedUser;
  try {
    user = await requireUser(req);
  } catch (e) {
    return jsonFromError(e);
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return jsonFromError(new ValidationError("invalid JSON body"));
  }
  const parsed = InputSchema.safeParse(body);
  if (!parsed.success) {
    return jsonFromError(
      new ValidationError(
        parsed.error.issues.map((i) => i.message).join("; "),
      ),
    );
  }
  const { platform, handle } = parsed.data;

  // Guard: Facebook pages (not profiles) are unsupported.
  if (platform === "facebook" && isFacebookPageUrl(handle)) {
    return jsonOk({
      valid: false,
      profile_url: "",
      error:
        "Facebook Pages are not supported. Please enter a personal profile handle (e.g. 'username').",
      post_ids: [],
      preview_posts: [],
      posts_data: [],
    });
  }

  const profileUrl = buildProfileUrl(platform, handle);
  if (!profileUrl) {
    return jsonOk({
      valid: false,
      profile_url: "",
      error: "Unsupported platform",
      post_ids: [],
      preview_posts: [],
      posts_data: [],
    });
  }

  // Step 1: HEAD/GET validation
  const headValid = await validateProfileExists(platform, profileUrl);
  if (!headValid) {
    logEvent({
      level: "info",
      fn: "social-test",
      event: "profile_invalid",
      user_id: user.id,
      platform,
      handle,
    });
    return jsonOk({
      valid: false,
      profile_url: profileUrl,
      error: "Profile not found or inaccessible",
      post_ids: [],
      preview_posts: [],
      posts_data: [],
    });
  }

  // Step 2: Apify synchronous scrape
  const apifyToken = Deno.env.get("APIFY_API_TOKEN");
  if (!apifyToken) {
    logEvent({
      level: "warn",
      fn: "social-test",
      event: "no_apify_token",
      user_id: user.id,
      platform,
    });
    return jsonOk({
      valid: true,
      profile_url: profileUrl,
      error: "APIFY_API_TOKEN not configured — baseline scan skipped",
      post_ids: [],
      preview_posts: [],
      posts_data: [],
    });
  }

  try {
    const posts = await runApifySync(platform, profileUrl, apifyToken);
    const postIds: string[] = [];
    const previewPosts: Array<{ id: string; text: string; timestamp: string }> =
      [];
    const postsData: Array<{
      post_id: string;
      caption_truncated: string;
      image_url: string | null;
      timestamp: string;
    }> = [];
    for (const p of posts) {
      if (!p.id) continue;
      postIds.push(p.id);
      previewPosts.push({
        id: p.id,
        text: (p.text ?? "").slice(0, PREVIEW_TEXT_MAX),
        timestamp: p.timestamp,
      });
      postsData.push({
        post_id: p.id,
        caption_truncated: (p.text ?? "").slice(0, CAPTION_TRUNCATED_MAX),
        image_url: p.imageUrl ?? null,
        timestamp: p.timestamp,
      });
    }

    logEvent({
      level: "info",
      fn: "social-test",
      event: "success",
      user_id: user.id,
      platform,
      handle,
      posts: postIds.length,
    });

    return jsonOk({
      valid: true,
      profile_url: profileUrl,
      post_ids: postIds,
      preview_posts: previewPosts,
      posts_data: postsData,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    logEvent({
      level: "warn",
      fn: "social-test",
      event: "scrape_failed",
      user_id: user.id,
      platform,
      handle,
      msg,
    });
    // HEAD succeeded, so profile is valid — return partial success with empty baseline.
    return jsonOk({
      valid: true,
      profile_url: profileUrl,
      error: `Profile valid but baseline scan failed: ${msg.slice(0, 140)}`,
      post_ids: [],
      preview_posts: [],
      posts_data: [],
    });
  }
});

// ---------------------------------------------------------------------------

function buildProfileUrl(platform: string, handle: string): string {
  const clean = handle.replace(/^@/, "").trim();
  if (!clean) return "";
  switch (platform) {
    case "instagram":
      return `https://www.instagram.com/${clean}/`;
    case "x":
      return `https://x.com/${clean}`;
    case "facebook":
      return `https://www.facebook.com/${clean}`;
    case "tiktok":
      return `https://www.tiktok.com/@${clean}`;
    default:
      return "";
  }
}

function isFacebookPageUrl(input: string): boolean {
  const s = input.toLowerCase();
  return s.includes("/pg/") || s.includes("/pages/") || /\/p\//.test(s);
}

async function validateProfileExists(
  platform: string,
  url: string,
): Promise<boolean> {
  // X/TikTok reject HEAD for logged-out users; use GET with no-follow.
  const method = platform === "x" || platform === "tiktok" ? "GET" : "HEAD";
  try {
    const res = await fetch(url, {
      method,
      redirect: "follow",
      // Keep it quick.
      signal: AbortSignal.timeout(10_000),
    });
    return res.status < 400;
  } catch {
    return false;
  }
}

async function runApifySync(
  platform: string,
  profileUrl: string,
  token: string,
): Promise<NormalizedPost[]> {
  const actor = ACTORS[platform];
  if (!actor) throw new Error(`Unsupported platform: ${platform}`);

  // `run-sync-get-dataset-items` blocks until the actor finishes + returns items.
  // Apify encodes `~` in slash-form actor IDs; our literal strings include the
  // `~` which Apify's router accepts directly on this endpoint.
  const endpoint =
    `https://api.apify.com/v2/acts/${actor.id}/run-sync-get-dataset-items` +
    `?token=${encodeURIComponent(token)}&timeout=${APIFY_TIMEOUT_SECS}`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(actor.buildInput(profileUrl)),
    signal: AbortSignal.timeout((APIFY_TIMEOUT_SECS + 15) * 1000),
  });
  if (!res.ok) {
    throw new Error(
      `Apify ${platform} actor failed: ${res.status} ${
        (await res.text()).slice(0, 200)
      }`,
    );
  }

  const items = await res.json().catch(() => []);
  if (!Array.isArray(items)) return [];
  return items.map((raw) => normalizePost(platform, raw)).filter((p) => p.id);
}

function normalizePost(
  platform: string,
  raw: Record<string, unknown>,
): NormalizedPost {
  const r = raw as Record<string, unknown>;
  let id = "";
  let text = "";
  let timestamp = "";
  let imageUrl: string | null = null;

  if (platform === "instagram") {
    id = str(r.shortCode) || str(r.id) || str(r.url);
    text = str(r.caption);
    timestamp = str(r.timestamp) || str(r.takenAt) || "";
    imageUrl = str(r.displayUrl) || firstImage(r.images) || firstImage(r.imagesUrls);
  } else if (platform === "x") {
    id = str(r.id) || str(r.conversationId) || str(r.url);
    text = str(r.text) || str(r.fullText);
    timestamp = str(r.createdAt) || str(r.date);
    const media = r.media as Array<{ url?: string }> | undefined;
    imageUrl = media?.[0]?.url ?? null;
  } else if (platform === "facebook") {
    id = str(r.postId) || str(r.id) || str(r.url);
    text = str(r.text) || str(r.message) || str(r.caption);
    timestamp = str(r.timestamp) || str(r.publishedTime) || str(r.time);
    imageUrl = str(r.image) || firstImage(r.images);
  } else if (platform === "tiktok") {
    id = str(r.id) || str(r.videoId) || str(r.url);
    text = str(r.desc) || str(r.caption) || str(r.text);
    timestamp = str(r.createTime) || str(r.timestamp);
    imageUrl = str(r.cover) || str(r.thumbnail);
  }
  return { id, text, timestamp, imageUrl };
}

function str(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return "";
}

function firstImage(v: unknown): string {
  if (Array.isArray(v) && v.length > 0) {
    const first = v[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object") {
      const o = first as Record<string, unknown>;
      return str(o.url) || str(o.src) || "";
    }
  }
  return "";
}
