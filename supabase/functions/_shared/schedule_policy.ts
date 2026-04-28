export type ScheduledScoutType = "web" | "beat" | "social" | "civic" | string;
export type ScheduleRegularity = "daily" | "weekly" | "monthly" | string;

function isSingleCronField(field: string): boolean {
  const normalized = field.trim();
  return Boolean(normalized) &&
    normalized !== "*" &&
    normalized !== "?" &&
    !/[,\-/]/.test(normalized);
}

export function cronIsNoMoreFrequentThanWeekly(cron: string): boolean {
  const trimmed = cron.trim();
  if (!trimmed) return true;

  const macro = trimmed.toLowerCase();
  if (
    macro === "@weekly" || macro === "@monthly" || macro === "@yearly" ||
    macro === "@annually"
  ) {
    return true;
  }
  if (macro === "@daily" || macro === "@hourly" || macro === "@reboot") {
    return false;
  }

  const parts = trimmed.split(/\s+/);
  if (parts.length !== 5) return true;

  const [, , dayOfMonth, , dayOfWeek] = parts;
  const hasSingleDayOfMonth = isSingleCronField(dayOfMonth);
  const hasSingleDayOfWeek = isSingleCronField(dayOfWeek);

  if (hasSingleDayOfMonth && dayOfWeek === "*") return true;
  if (dayOfMonth === "*" && hasSingleDayOfWeek) return true;
  return false;
}

export function schedulePolicyError(
  type: ScheduledScoutType | undefined | null,
  regularity?: ScheduleRegularity | null,
  scheduleCron?: string | null,
): string | null {
  if (type !== "beat" && type !== "civic") return null;

  const label = type === "beat" ? "beat scouts" : "civic scouts";
  if (regularity === "daily") {
    return `${label} support weekly or monthly schedules only`;
  }
  if (scheduleCron && !cronIsNoMoreFrequentThanWeekly(scheduleCron)) {
    return `${label} support weekly or monthly schedules only`;
  }
  return null;
}
