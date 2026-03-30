/**
 * Feed Refresh Signal -- event bus for triggering feed re-fetches.
 *
 * USED BY: FeedView.svelte, ScoutScheduleModal.svelte, ScoutsPanel.svelte
 * DEPENDS ON: (none)
 *
 * Incrementing counter pattern: subscribers react to any value change
 * without caring about the actual number. Call triggerFeedRefresh()
 * after a scout run completes or units are modified.
 */
import { writable } from 'svelte/store';

/** Increment to signal FeedView to re-fetch. */
export const feedRefreshSignal = writable(0);

export function triggerFeedRefresh() {
	feedRefreshSignal.update(n => n + 1);
}
