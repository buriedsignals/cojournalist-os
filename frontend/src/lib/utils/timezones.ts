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
	if (currentTimezone && !list.includes(currentTimezone)) {
		list.unshift(currentTimezone);
	}
	return list;
}
