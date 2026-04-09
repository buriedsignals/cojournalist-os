/**
 * Shared timezone utilities used by OnboardingModal and PreferencesModal.
 */

export const POPULAR_TIMEZONES = [
	'America/New_York',
	'America/Chicago',
	'America/Denver',
	'America/Los_Angeles',
	'America/Sao_Paulo',
	'Europe/London',
	'Europe/Paris',
	'Europe/Berlin',
	'Asia/Kolkata',
	'Asia/Tokyo',
	'Asia/Singapore',
	'Australia/Sydney',
	'UTC'
];

/**
 * Deprecated IANA timezone names that browsers may return via
 * Intl.DateTimeFormat().resolvedOptions().timeZone on certain OS configurations.
 * Maps to canonical IANA identifiers for display and submission.
 */
const TIMEZONE_ALIASES: Record<string, string> = {
	'America/Buenos_Aires': 'America/Argentina/Buenos_Aires',
	'America/Indianapolis': 'America/Indiana/Indianapolis',
	'America/Fort_Wayne': 'America/Indiana/Indianapolis',
	'America/Louisville': 'America/Kentucky/Louisville',
	'America/Knox_IN': 'America/Indiana/Knox',
	'Asia/Calcutta': 'Asia/Kolkata',
	'Asia/Saigon': 'Asia/Ho_Chi_Minh',
	'Asia/Katmandu': 'Asia/Kathmandu',
	'Asia/Rangoon': 'Asia/Yangon',
	'Europe/Kiev': 'Europe/Kyiv',
	'Pacific/Ponape': 'Pacific/Pohnpei',
	'Atlantic/Faeroe': 'Atlantic/Faroe'
};

/** Map a deprecated IANA timezone name to its canonical equivalent. */
export function normalizeTimezone(tz: string): string {
	return TIMEZONE_ALIASES[tz] ?? tz;
}

/** Format IANA timezone for display: replace underscores with spaces */
export function formatTz(tz: string): string {
	return tz.replace(/_/g, ' ');
}

/**
 * Build a timezone options list: popular timezones + the user's current
 * timezone (if not already in the list). This keeps the dropdown short (~13 items).
 */
export function getTimezoneOptions(currentTimezone?: string | null): string[] {
	const list = [...POPULAR_TIMEZONES];
	const normalized = currentTimezone ? normalizeTimezone(currentTimezone) : null;
	if (normalized && !list.includes(normalized)) {
		list.unshift(normalized);
	}
	return list;
}
