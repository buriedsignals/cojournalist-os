import { ValidationError } from "./errors.ts";
import {
  buildSocialProfileUrl,
  normalizeSocialHandle,
  type SocialPlatform,
} from "./social_profiles.ts";

const MAX_ITEMS = 20;
const APIFY_TIMEOUT_SECS = 120;
const CAPTION_TRUNCATED_MAX = 200;

interface ApifyActor {
  id: string;
  buildInput: (url: string) => Record<string, unknown>;
}

const ACTORS: Record<SocialPlatform, ApifyActor> = {
  instagram: {
    id: "culc72xb7MP3EbaeX",
    buildInput: (url) => ({ startUrls: [url], maxItems: MAX_ITEMS }),
  },
  x: {
    id: "61RPP7dywgiy0JPD0",
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
    buildInput: (url) => ({ urls: [url], limit: MAX_ITEMS }),
  },
};

export interface NormalizedSocialPost {
  id: string;
  text: string;
  timestamp: string;
  imageUrl: string | null;
  url: string | null;
}

export interface SocialBaselineScan {
  profileUrl: string;
  posts: NormalizedSocialPost[];
}

export async function scanSocialBaseline(
  platform: SocialPlatform,
  handle: string,
  token = Deno.env.get("APIFY_API_TOKEN") ?? "",
): Promise<SocialBaselineScan> {
  if (!token) {
    throw new ValidationError(
      "APIFY_API_TOKEN not configured; cannot establish social baseline",
    );
  }
  const normalizedHandle = normalizeSocialHandle(platform, handle);
  const profileUrl = buildSocialProfileUrl(platform, normalizedHandle);
  if (!profileUrl) throw new ValidationError("unsupported social profile");
  const actor = ACTORS[platform];
  if (!actor) throw new ValidationError(`unsupported platform: ${platform}`);

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
      `Apify ${platform} baseline failed: ${res.status} ${
        (await res.text()).slice(0, 200)
      }`,
    );
  }

  const items = await res.json().catch(() => []);
  const posts = Array.isArray(items)
    ? items.map((raw) => normalizePost(platform, raw)).filter((p) => p.id)
    : [];
  return { profileUrl, posts };
}

export function formatSocialBaselinePosts(
  posts: NormalizedSocialPost[],
): Array<Record<string, unknown>> {
  return posts.map((post) => ({
    id: post.id,
    post_id: post.id,
    url: post.url,
    text: post.text,
    caption: post.text,
    caption_truncated: post.text.slice(0, CAPTION_TRUNCATED_MAX),
    image_url: post.imageUrl,
    timestamp: post.timestamp,
  }));
}

function normalizePost(
  platform: SocialPlatform,
  raw: Record<string, unknown>,
): NormalizedSocialPost {
  const r = raw as Record<string, unknown>;
  let id = "";
  let text = "";
  let timestamp = "";
  let imageUrl: string | null = null;
  let url: string | null = null;

  if (platform === "instagram") {
    id = str(r.shortCode) || str(r.id) || str(r.url);
    text = str(r.caption);
    timestamp = str(r.timestamp) || str(r.takenAt) || "";
    imageUrl = str(r.displayUrl) || firstImage(r.images) ||
      firstImage(r.imagesUrls);
    url = str(r.url) || (str(r.shortCode)
      ? `https://www.instagram.com/p/${str(r.shortCode)}/`
      : null);
  } else if (platform === "x") {
    id = str(r.id) || str(r.conversationId) || str(r.url);
    text = str(r.text) || str(r.fullText);
    timestamp = str(r.createdAt) || str(r.date);
    const media = r.media as Array<{ url?: string }> | undefined;
    imageUrl = media?.[0]?.url ?? null;
    url = str(r.url);
  } else if (platform === "facebook") {
    id = str(r.postId) || str(r.id) || str(r.url);
    text = str(r.text) || str(r.message) || str(r.caption);
    timestamp = str(r.timestamp) || str(r.publishedTime) || str(r.time);
    imageUrl = str(r.image) || firstImage(r.images);
    url = str(r.url);
  } else if (platform === "tiktok") {
    id = str(r.id) || str(r.videoId) || str(r.url);
    text = str(r.desc) || str(r.caption) || str(r.text);
    timestamp = str(r.createTime) || str(r.timestamp);
    imageUrl = str(r.cover) || str(r.thumbnail);
    url = str(r.url) || str(r.webVideoUrl);
  }
  return { id, text, timestamp, imageUrl, url };
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
