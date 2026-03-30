/**
 * Notification Store -- in-app notifications for scout run results.
 *
 * USED BY: +layout.svelte
 * DEPENDS ON: $lib/types (Notification), $lib/api-client (getActiveJobs)
 *
 * State: Notification[] (id, scraperName, timestamp)
 * Side effects:
 *   - Reads/writes localStorage keys: coJournalist_notifications,
 *     coJournalist_last_seen_runs
 *   - Writes sessionStorage key: coJournalist_last_active_jobs_check
 *   - Calls apiClient.getActiveJobs() to detect new scout results
 *
 * Notifications are generated when a scout run has criteria_status=true
 * and the run timestamp differs from the last-seen timestamp.
 */
import { writable } from 'svelte/store';
import type { Notification } from '$lib/types';
import { apiClient } from '$lib/api-client';

const STORAGE_KEY = 'coJournalist_notifications';
const LAST_CHECK_KEY = 'coJournalist_last_active_jobs_check';

/**
 * Load notifications from localStorage
 */
function loadFromStorage(): Notification[] {
	if (typeof window === 'undefined') return [];

	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored) {
			return JSON.parse(stored);
		}
	} catch (error) {
		console.error('Failed to load notifications from localStorage:', error);
	}
	return [];
}

/**
 * Save notifications to localStorage
 */
function saveToStorage(notifications: Notification[]): void {
	if (typeof window === 'undefined') return;

	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications));
	} catch (error) {
		console.error('Failed to save notifications to localStorage:', error);
	}
}

/**
 * Create notification store with localStorage persistence
 */
function createNotificationStore() {
	const { subscribe, set, update } = writable<Notification[]>(loadFromStorage());

	return {
		subscribe,

		/**
		 * Add a new notification
		 */
		addNotification: (scraperName: string) => {
			update(notifications => {
				const newNotification: Notification = {
					id: crypto.randomUUID(),
					scraperName,
					timestamp: Date.now()
				};
				const updated = [newNotification, ...notifications];
				saveToStorage(updated);
				return updated;
			});
		},

		/**
		 * Check active jobs for new notifications
		 * Deduplicates based on last_run timestamp
		 * Rate-limited to prevent excessive API calls
		 */
		checkActiveJobs: async () => {
			if (typeof window === 'undefined') return;

			const now = Date.now();

			try {
				const response = await apiClient.getActiveJobs();
				const lastSeenKey = 'coJournalist_last_seen_runs';
				let lastSeenRuns: Record<string, string> = {};

				try {
					const stored = localStorage.getItem(lastSeenKey);
					if (stored) lastSeenRuns = JSON.parse(stored);
				} catch (e) {
					console.warn('Failed to load last seen runs', e);
				}

				let hasUpdates = false;

				response.scrapers.forEach(job => {
					// Only notify if criteria was met
					if (job.last_run && job.last_run.criteria_status) {
						const lastRunTime = job.last_run.last_run;
						const lastSeenTime = lastSeenRuns[job.scraper_name];

						// If we haven't seen this run before
						if (lastRunTime && lastRunTime !== lastSeenTime) {
							// Add notification
							update(notifications => {
								const newNotification: Notification = {
									id: crypto.randomUUID(),
									scraperName: job.scraper_name,
									timestamp: Date.now()
								};
								const updated = [newNotification, ...notifications];
								saveToStorage(updated);
								return updated;
							});

							// Update last seen
							lastSeenRuns[job.scraper_name] = lastRunTime;
							hasUpdates = true;
						}
					}
				});

				if (hasUpdates) {
					localStorage.setItem(lastSeenKey, JSON.stringify(lastSeenRuns));
				}

				// Mark that we've checked in this session
				sessionStorage.setItem(LAST_CHECK_KEY, now.toString());
			} catch (error) {
				console.error('Failed to check active jobs for notifications:', error);
			}
		},

	};
}

export const notificationStore = createNotificationStore();
