/**
 * Local Storage Utilities -- timed-value (TTL) persistence helpers.
 *
 * USED BY: stores/feed.ts, stores/pulse.ts
 * DEPENDS ON: (none)
 *
 * Provides loadTimedValue/saveTimedValue for localStorage entries that
 * auto-expire after a configurable TTL (default 7 days). Used to persist
 * user prompts and excluded-domain lists across sessions.
 */

/** Default TTL: 7 days in milliseconds. */
const DEFAULT_TTL_MS = 7 * 24 * 60 * 60 * 1000;

interface StoredTimedValue {
	value: string;
	timestamp: number;
}

/**
 * Load a value from localStorage, returning null if missing or expired.
 *
 * @param key - localStorage key
 * @param ttlMs - time-to-live in milliseconds (default: 7 days)
 */
export function loadTimedValue(key: string, ttlMs: number = DEFAULT_TTL_MS): string | null {
	if (typeof window === 'undefined') return null;

	const stored = localStorage.getItem(key);
	if (!stored) return null;

	try {
		const parsed: StoredTimedValue = JSON.parse(stored);
		if (Date.now() - parsed.timestamp >= ttlMs) {
			localStorage.removeItem(key);
			return null;
		}
		return parsed.value;
	} catch {
		localStorage.removeItem(key);
		return null;
	}
}

/**
 * Save a value to localStorage with a timestamp, or remove it if null.
 *
 * @param key - localStorage key
 * @param value - string to persist, or null to remove
 */
export function saveTimedValue(key: string, value: string | null): void {
	if (typeof window === 'undefined') return;

	if (value) {
		const entry: StoredTimedValue = { value, timestamp: Date.now() };
		localStorage.setItem(key, JSON.stringify(entry));
	} else {
		localStorage.removeItem(key);
	}
}
