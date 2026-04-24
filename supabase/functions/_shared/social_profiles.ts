export type SocialPlatform = "instagram" | "x" | "facebook" | "tiktok";

export type ProfileProbeResult = "exists" | "missing" | "uncertain";

export function normalizeSocialHandle(
  platform: SocialPlatform,
  input: string,
): string {
  const raw = sanitizeBareHandle(input);
  if (!raw) return "";

  const extracted = extractHandleFromUrl(platform, raw);
  return sanitizeBareHandle(extracted ?? raw);
}

export function buildSocialProfileUrl(
  platform: SocialPlatform,
  input: string,
): string {
  const handle = normalizeSocialHandle(platform, input);
  if (!handle) return "";

  switch (platform) {
    case "instagram":
      return `https://www.instagram.com/${handle}/`;
    case "x":
      return `https://x.com/${handle}`;
    case "facebook":
      return `https://www.facebook.com/${handle}`;
    case "tiktok":
      return `https://www.tiktok.com/@${handle}`;
  }
}

export function classifyProfileProbeStatus(status: number): ProfileProbeResult {
  if (status === 404 || status === 410) return "missing";
  if (status >= 200 && status < 400) return "exists";
  return "uncertain";
}

export function looksLikeMissingProfileError(message: string): boolean {
  return [
    /not found/i,
    /private profile/i,
    /profile.*private/i,
    /does(?:n't| not) exist/i,
    /user.*does(?:n't| not) exist/i,
    /username.*does(?:n't| not) exist/i,
    /profile.*unavailable/i,
    /no such user/i,
  ].some((pattern) => pattern.test(message));
}

function sanitizeBareHandle(input: string): string {
  return input
    .trim()
    .replace(/^@/, "")
    .replace(/^\/+/, "")
    .replace(/\/+$/, "");
}

function extractHandleFromUrl(
  platform: SocialPlatform,
  input: string,
): string | null {
  const matchers: Record<SocialPlatform, RegExp> = {
    instagram: /^(?:https?:\/\/)?(?:www\.)?instagram\.com\/([^/?#]+)/i,
    x: /^(?:https?:\/\/)?(?:www\.)?(?:x|twitter)\.com\/([^/?#]+)/i,
    facebook: /^(?:https?:\/\/)?(?:www\.|m\.)?facebook\.com\/([^/?#]+)/i,
    tiktok: /^(?:https?:\/\/)?(?:www\.|m\.)?tiktok\.com\/@([^/?#]+)/i,
  };

  return input.match(matchers[platform])?.[1] ?? null;
}
