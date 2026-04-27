/**
 * Abstain-R1 fact-checking module.
 *
 * Sends extracted information units to a locally-hosted Abstain-R1 model
 * (3B params, calibrated abstention) via an OpenAI-compatible chat endpoint
 * (Ollama, vLLM, llama.cpp). The model evaluates each claim and either
 * confirms with a confidence score or abstains — flagging uncertain claims
 * for human review instead of presenting them as facts.
 *
 * Graceful degradation: when the endpoint is not configured or unreachable,
 * units pass through with fact_checked=false and no confidence score.
 */

import { ApiError } from "./errors.ts";

export interface FactCheckResult {
  /** Whether the unit was evaluated by the fact-checker. */
  fact_checked: boolean;
  /** 0.0–1.0 confidence the claim is accurate. null if not checked. */
  confidence_score: number | null;
  /** True if the model abstained (insufficient evidence to verify). */
  abstained: boolean;
  /** Reason for abstention, when applicable. */
  abstain_reason: string | null;
}

export interface FactCheckConfig {
  /** Base URL for the OpenAI-compatible inference endpoint. */
  endpointUrl: string | null;
  /** Model identifier to send in the request (default: "abstain-r1"). */
  modelId: string;
  /** Confidence threshold below which units are marked as abstained (0.0–1.0). */
  abstainThreshold: number;
  /** Request timeout in milliseconds. */
  timeoutMs: number;
}

const UNCHECKED: FactCheckResult = {
  fact_checked: false,
  confidence_score: null,
  abstained: false,
  abstain_reason: null,
};

const SYSTEM_PROMPT = `You are a fact-checking assistant with calibrated confidence. Given a factual claim extracted from a news article, evaluate whether the claim is verifiable and likely accurate.

IMPORTANT: You must be honest about uncertainty. If you cannot verify the claim with reasonable confidence, you MUST abstain rather than guess.

Respond with a JSON object:
{
  "verdict": "accept" | "abstain" | "reject",
  "confidence": <float 0.0 to 1.0>,
  "reason": "<brief explanation, 1-2 sentences>"
}

WHEN TO ABSTAIN:
- The claim references specific data (numbers, dates, names) you cannot verify
- The claim is about a very recent or local event outside your training data
- The claim mixes verifiable facts with unverifiable details
- You have low confidence (below 0.5) in any direction

WHEN TO ACCEPT:
- The claim is consistent with well-established facts
- The claim's structure and specifics are internally consistent
- You have high confidence the claim is plausible and well-formed

WHEN TO REJECT:
- The claim contains demonstrably false information
- The claim contradicts well-established facts
- The claim has logical inconsistencies

Always provide a confidence score even when abstaining — it helps calibrate thresholds.`;

interface ChatCompletionMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface VerdictResponse {
  verdict: "accept" | "abstain" | "reject";
  confidence: number;
  reason: string;
}

export function loadFactCheckConfig(): FactCheckConfig {
  const endpointUrl = Deno.env.get("ABSTAIN_R1_ENDPOINT_URL") || null;
  const modelId = Deno.env.get("ABSTAIN_R1_MODEL") || "abstain-r1";
  const raw = Deno.env.get("ABSTAIN_CONFIDENCE_THRESHOLD");
  const abstainThreshold = raw ? Math.max(0, Math.min(1, parseFloat(raw))) : 0.4;
  const timeoutRaw = Deno.env.get("ABSTAIN_R1_TIMEOUT_MS");
  const timeoutMs = timeoutRaw ? parseInt(timeoutRaw, 10) : 15_000;
  return { endpointUrl, modelId, abstainThreshold, timeoutMs };
}

export function isFactCheckEnabled(config: FactCheckConfig): boolean {
  return config.endpointUrl !== null && config.endpointUrl.trim().length > 0;
}

function buildUserPrompt(statement: string, context?: {
  sourceUrl?: string | null;
  sourceDomain?: string | null;
  occurredAt?: string | null;
}): string {
  let prompt = `Evaluate this factual claim:\n\n"${statement}"`;
  if (context?.sourceDomain) {
    prompt += `\n\nSource: ${context.sourceDomain}`;
  }
  if (context?.occurredAt) {
    prompt += `\nDate: ${context.occurredAt}`;
  }
  return prompt;
}

function parseVerdict(text: string): VerdictResponse | null {
  try {
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return null;
    const parsed = JSON.parse(jsonMatch[0]);
    if (
      typeof parsed.verdict !== "string" ||
      !["accept", "abstain", "reject"].includes(parsed.verdict)
    ) {
      return null;
    }
    const confidence = typeof parsed.confidence === "number"
      ? Math.max(0, Math.min(1, parsed.confidence))
      : 0.5;
    return {
      verdict: parsed.verdict as "accept" | "abstain" | "reject",
      confidence,
      reason: typeof parsed.reason === "string" ? parsed.reason : "",
    };
  } catch {
    return null;
  }
}

/**
 * Fact-check a single statement against the Abstain-R1 model.
 *
 * Returns UNCHECKED (fact_checked=false) when the endpoint is not configured
 * or unreachable — never blocks the pipeline.
 */
export async function factCheckUnit(
  statement: string,
  config: FactCheckConfig,
  context?: {
    sourceUrl?: string | null;
    sourceDomain?: string | null;
    occurredAt?: string | null;
  },
): Promise<FactCheckResult> {
  if (!isFactCheckEnabled(config)) return UNCHECKED;

  const messages: ChatCompletionMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: buildUserPrompt(statement, context) },
  ];

  const ac = new AbortController();
  const fuse = setTimeout(() => ac.abort(), config.timeoutMs + 2_000);

  let res: Response;
  try {
    res = await fetch(`${config.endpointUrl}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: config.modelId,
        messages,
        temperature: 0.1,
        max_tokens: 256,
      }),
      signal: ac.signal,
    });
  } catch {
    clearTimeout(fuse);
    return UNCHECKED;
  }
  clearTimeout(fuse);

  if (!res.ok) return UNCHECKED;

  let body: Record<string, unknown>;
  try {
    body = await res.json();
  } catch {
    return UNCHECKED;
  }

  const choices = body?.choices as Array<{
    message?: { content?: string };
  }> | undefined;
  const content = choices?.[0]?.message?.content;
  if (typeof content !== "string") return UNCHECKED;

  const verdict = parseVerdict(content);
  if (!verdict) return UNCHECKED;

  const abstained = verdict.verdict === "abstain" ||
    verdict.verdict === "reject" ||
    verdict.confidence < config.abstainThreshold;

  return {
    fact_checked: true,
    confidence_score: verdict.confidence,
    abstained,
    abstain_reason: abstained ? (verdict.reason || "Low confidence") : null,
  };
}

/**
 * Batch fact-check multiple statements. Processes sequentially to avoid
 * overwhelming the local inference endpoint (3B model, single GPU).
 */
export async function factCheckBatch(
  units: Array<{
    statement: string;
    sourceUrl?: string | null;
    sourceDomain?: string | null;
    occurredAt?: string | null;
  }>,
  config: FactCheckConfig,
): Promise<FactCheckResult[]> {
  if (!isFactCheckEnabled(config)) {
    return units.map(() => UNCHECKED);
  }

  const results: FactCheckResult[] = [];
  for (const unit of units) {
    const result = await factCheckUnit(unit.statement, config, {
      sourceUrl: unit.sourceUrl,
      sourceDomain: unit.sourceDomain,
      occurredAt: unit.occurredAt,
    });
    results.push(result);
  }
  return results;
}

export { UNCHECKED, SYSTEM_PROMPT, parseVerdict as _parseVerdict, buildUserPrompt as _buildUserPrompt };
