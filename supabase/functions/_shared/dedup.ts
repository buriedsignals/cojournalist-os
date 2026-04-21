/**
 * Cosine similarity + within-run dedup helpers.
 *
 * The legacy pipeline applied a within-run pairwise filter (threshold 0.75)
 * after extraction, before hitting the cross-run dedup RPC. Without it, Gemini
 * paraphrase pairs ("Council voted on budget" / "City budget approved by
 * council") both land as separate information_units. See audit §4.1 row 19
 * and §4.2 row 20.
 */

const WITHIN_RUN_SIMILARITY_THRESHOLD = 0.75;

export function cosineSimilarity(a: number[], b: number[]): number {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length || a.length === 0) {
    return 0;
  }
  let dot = 0;
  let magA = 0;
  let magB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    magA += a[i] * a[i];
    magB += b[i] * b[i];
  }
  if (magA === 0 || magB === 0) return 0;
  return dot / (Math.sqrt(magA) * Math.sqrt(magB));
}

/**
 * Return true if `embedding` is near-duplicate of any entry in `kept` at or
 * above the within-run threshold. O(n) in the size of `kept`; callers use
 * this to filter each newly-extracted unit before inserting.
 */
export function isWithinRunDuplicate(
  embedding: number[],
  kept: number[][],
  threshold = WITHIN_RUN_SIMILARITY_THRESHOLD,
): boolean {
  for (const prior of kept) {
    if (cosineSimilarity(embedding, prior) >= threshold) return true;
  }
  return false;
}
