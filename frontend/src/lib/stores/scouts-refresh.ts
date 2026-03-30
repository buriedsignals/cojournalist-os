/**
 * Scouts Refresh Signal -- event bus for triggering ScoutsPanel re-fetches.
 *
 * USED BY: ScoutScheduleModal.svelte, ScoutsPanel.svelte
 * DEPENDS ON: (none)
 *
 * Same incrementing-counter pattern as feed-refresh.ts.
 * Call triggerScoutsRefresh() after creating, deleting, or running a scout.
 */
import { writable } from 'svelte/store';

/** Increment to signal ScoutsPanel to re-fetch. */
export const scoutsRefreshSignal = writable(0);

export function triggerScoutsRefresh() {
	scoutsRefreshSignal.update(n => n + 1);
}
