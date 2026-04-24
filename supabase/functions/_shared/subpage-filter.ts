/**
 * Filter extracted links to the subpages considered safe to fetch during
 * Phase B of the web-scout listing-page follow. Host-lock + denylist are
 * already handled by `extractLinksFromHtml` (in scout-web-execute); this
 * layer adds the subpage-specific rules: path-prefix under the index URL,
 * path traversal block, and a second-pass domain validator.
 *
 * Pure function — no network, no I/O.
 */

/** Reject IPs, localhost, reserved hostnames. */
export function validateDomain(domain: string): { valid: boolean; error?: string } {
  const cleaned = domain.trim().toLowerCase();
  if (!cleaned) return { valid: false, error: "Empty domain" };
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(cleaned)) return { valid: false, error: "IP not allowed" };
  if (cleaned.includes(":") || cleaned.startsWith("[")) return { valid: false, error: "IPv6 not allowed" };
  const reserved = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal", "169.254.169.254"]);
  if (reserved.has(cleaned.split("/")[0].split(":")[0])) return { valid: false, error: "Reserved hostname" };
  if (!cleaned.includes(".")) return { valid: false, error: "No TLD" };
  return { valid: true };
}

/**
 * Keep only links that:
 *   1. Parse as a valid URL.
 *   2. Have a path under `indexUrl`'s path (strict prefix + separator).
 *   3. Contain no `..` or percent-encoded traversal in the path.
 *   4. Pass `validateDomain` (reject IPs / localhost / reserved names).
 */
export function filterSubpageUrls(links: string[], indexUrl: string): string[] {
  let indexPath: string;
  try {
    indexPath = new URL(indexUrl).pathname.replace(/\/+$/, "");
  } catch {
    return [];
  }

  return links.filter((url) => {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return false;
    }
    const cleanPath = parsed.pathname.replace(/\/+$/, "");
    if (!cleanPath.startsWith(indexPath + "/")) return false;
    if (cleanPath.includes("..") || cleanPath.toLowerCase().includes("%2e%2e")) return false;
    if (!validateDomain(parsed.hostname).valid) return false;
    return true;
  });
}
