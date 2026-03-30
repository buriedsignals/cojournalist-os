/**
 * Progress Timer Utilities -- calibrated progress bar for long-running API calls.
 *
 * USED BY: SmartScoutView.svelte
 * DEPENDS ON: (none)
 *
 * Uses an ease-out curve so the bar starts fast (responsive feel) and
 * decelerates as it approaches the expected duration, never hard-capping.
 * The PULSE_EXPECTED_DURATION_MS constant is calibrated from benchmark_pulse.py.
 */

/**
 * Expected wall-clock duration for Smart Scout (type pulse) pipeline in ms.
 *
 * Measured via benchmark_pulse.py (3 runs, 2 categories in parallel):
 *   Location queries: 35.6–49.1s (gov queries now functional after get_country_code fix)
 *   Topic-only queries: 14.8s
 *   Mean: 33.2s, Max: 49.1s
 *
 * Set to 40s — covers ~P80 for location queries. The ease-out overrun curve
 * handles the tail (Seattle peaked at 49s). Topic-only queries finish early
 * and jump to 100%.
 */
export const PULSE_EXPECTED_DURATION_MS = 40_000;

/**
 * Compute progress percentage (0–100) using an ease-out deceleration curve.
 *
 * - Starts fast for responsiveness
 * - Reaches ~95% at `expectedDuration`
 * - Slowly crawls toward 98% if overrunning
 * - Never reaches 100 (that's set when the API responds)
 *
 * @param elapsedMs  Time elapsed since the request started
 * @param expectedMs Expected total duration
 * @returns Progress percentage [0, 98]
 */
export function easeOutProgress(elapsedMs: number, expectedMs: number): number {
	if (elapsedMs <= 0) return 0;

	const ratio = elapsedMs / expectedMs;

	if (ratio <= 1) {
		// Main phase: ease-out curve reaching ~95% at ratio=1
		// Formula: 1 - (1 - ratio)^2.5  scaled to 95%
		const eased = 1 - Math.pow(1 - ratio, 2.5);
		return Math.round(eased * 95);
	}

	// Overrun phase: slowly crawl from 95% toward 98%
	const overrunRatio = ratio - 1; // how far past expected
	const extra = 3 * (1 - Math.exp(-overrunRatio * 2)); // asymptotic approach to +3%
	return Math.min(98, Math.round(95 + extra));
}

/**
 * Format remaining time as a human-readable hint string.
 *
 * @param remainingMs Estimated milliseconds remaining
 * @returns Object with type and value for i18n interpolation
 */
export function formatEstimatedTime(remainingMs: number): { type: 'seconds' | 'minutes' | 'done'; value: number } {
	if (remainingMs <= 3000) {
		return { type: 'done', value: 0 };
	}

	const seconds = Math.ceil(remainingMs / 5000) * 5; // Round up to nearest 5s

	if (seconds >= 120) {
		return { type: 'minutes', value: Math.ceil(seconds / 60) };
	}

	return { type: 'seconds', value: seconds };
}

