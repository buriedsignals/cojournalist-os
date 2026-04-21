/**
 * PKCE (RFC 7636) S256 verifier check.
 *
 * The MCP client produced:
 *   verifier  = random 43-128 char string from [A-Za-z0-9-._~]
 *   challenge = base64url(sha256(verifier)) without padding
 *
 * We recompute the challenge from the verifier and compare it constant-time
 * to the stored `code_challenge`.
 */

import { base64urlEncode } from "./state.ts";

const VERIFIER_ALPHABET = /^[A-Za-z0-9\-._~]+$/;

export function validateVerifier(verifier: string): void {
  if (typeof verifier !== "string") throw new Error("code_verifier missing");
  if (verifier.length < 43) throw new Error("code_verifier too short");
  if (verifier.length > 128) throw new Error("code_verifier too long");
  if (!VERIFIER_ALPHABET.test(verifier)) {
    throw new Error("code_verifier contains invalid characters");
  }
}

function timingSafeEqualString(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/**
 * Returns true iff `base64url(sha256(verifier)) === challenge`.
 * Throws if the verifier fails shape validation.
 */
export async function verifyS256(verifier: string, challenge: string): Promise<boolean> {
  validateVerifier(verifier);
  const digest = new Uint8Array(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)),
  );
  const computed = base64urlEncode(digest);
  return timingSafeEqualString(computed, challenge);
}
