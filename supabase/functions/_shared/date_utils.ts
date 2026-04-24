/**
 * Shared date helpers for Edge Functions.
 *
 * `normalizeDate` is the canonical implementation previously duplicated
 * across 5 Edge Functions (beat-search, ingest, scout-beat-execute,
 * scout-web-execute, civic-extract-worker). Single source of truth now.
 *
 * Accepts anything the `Date` constructor can parse. Returns:
 *   - the `YYYY-MM-DD` prefix if present literally at the start (fast path),
 *   - otherwise the `toISOString()` date prefix of the parsed `Date`,
 *   - or `null` if the input is empty/unparseable.
 *
 * Stored as `YYYY-MM-DD` because Postgres `DATE` columns expect that shape.
 */
export function normalizeDate(v: string | null | undefined): string | null {
  if (!v) return null;
  const trimmed = v.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const d = new Date(trimmed);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}
