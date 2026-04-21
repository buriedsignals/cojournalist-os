/**
 * Structured JSON logger for Edge Functions. One line per event to stdout.
 */

export interface LogEvent {
  ts?: string;
  level: "debug" | "info" | "warn" | "error";
  fn: string;
  event: string;
  msg?: string;
  user_id?: string;
  scout_id?: string;
  [extra: string]: unknown;
}

export function logEvent(e: LogEvent): void {
  const line = JSON.stringify({ ts: new Date().toISOString(), ...e });
  if (e.level === "error") console.error(line);
  else if (e.level === "warn") console.warn(line);
  else console.log(line);
}
