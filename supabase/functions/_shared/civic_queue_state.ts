export type CivicQueueFailureStatus = "pending" | "failed";

export interface CivicQueueFailureState {
  status: CivicQueueFailureStatus;
  terminal: boolean;
}

const DEFAULT_MAX_ATTEMPTS = 3;

export function classifyCivicQueueFailure(
  attempts: number,
  maxAttempts = DEFAULT_MAX_ATTEMPTS,
): CivicQueueFailureState {
  const safeAttempts = Number.isFinite(attempts)
    ? Math.max(0, Math.floor(attempts))
    : 0;
  const safeMax = Number.isFinite(maxAttempts) && maxAttempts > 0
    ? Math.floor(maxAttempts)
    : DEFAULT_MAX_ATTEMPTS;
  const terminal = safeAttempts >= safeMax;
  return {
    status: terminal ? "failed" : "pending",
    terminal,
  };
}
