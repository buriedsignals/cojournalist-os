/**
 * Auth Store -- Session cookie authentication and user state.
 *
 * USED BY: api-client.ts, webhook-client.ts, +layout.svelte, +page.svelte,
 *          login/+page.svelte, pricing/+page.svelte,
 *          PreferencesModal, ScoutScheduleModal, UpgradeModal,
 *          ScoutsPanel, DataExtract, UnifiedSidebar, FeedView
 * DEPENDS ON: $lib/config/api (buildApiUrl)
 *
 * State: { authenticated: boolean, user: User | null, loading: boolean }
 * Side effects:
 *   - Fetches user data from GET /api/auth/me (cookie auth)
 *   - Updates preferences via apiClient.updateUserPreferences (lazy import)
 *   - Initializes new users via POST /api/onboarding/initialize
 *
 * Exports: authStore (primary), currentUser (derived), auth (convenience object)
 */
import { browser } from '$app/environment';
import { writable, derived } from 'svelte/store';
import type { User, AuthState, GeocodedLocation } from '$lib/types';
import { buildApiUrl } from '$lib/config/api';

const initialState: AuthState = {
	authenticated: false,
	user: null
};

function createAuthStore() {
	const { subscribe, set, update } = writable<AuthState>(initialState);

	let initialized = false;

	return {
		subscribe,

		/**
		 * Initialize auth state by checking session cookie via /auth/me.
		 */
		async init() {
			if (!browser) return;
			if (initialized) return;
			initialized = true;

			try {
				const response = await fetch(buildApiUrl('/auth/me'), {
					credentials: 'include'
				});
				if (response.ok) {
					const data = await response.json();
					set({ authenticated: true, user: data });
				} else {
					set({ authenticated: false, user: null });
				}
			} catch {
				set({ authenticated: false, user: null });
			}
		},

		/**
		 * Redirect to OAuth login flow.
		 */
		login() {
			if (!browser) return;
			window.location.href = buildApiUrl('/auth/login');
		},

		/**
		 * Sign out: clear session cookie and redirect to login.
		 */
		async signOut() {
			try {
				await fetch(buildApiUrl('/auth/logout'), {
					method: 'POST',
					credentials: 'include'
				});
			} catch {
				// Best-effort
			}
			set({ authenticated: false, user: null });
			initialized = false;
			if (browser) {
				window.location.href = '/login';
			}
		},

		/**
		 * Refresh user data from backend.
		 */
		async refreshUser() {
			if (!browser) return;

			try {
				const response = await fetch(buildApiUrl('/auth/me'), {
					credentials: 'include'
				});
				if (response.ok) {
					const data = await response.json();
					update((s) => ({ ...s, user: data, authenticated: true }));
				}
			} catch {
				// Silent fail
			}
		},

		/**
		 * Force-set the current credit balance.
		 */
		setCredits(credits: number) {
			update((state) => {
				if (!state.user) return state;
				return {
					...state,
					user: {
						...state.user,
						credits
					}
				};
			});
		},

		/**
		 * Get session token for API calls.
		 * No longer needed -- cookies are sent automatically.
		 * Kept for backward compatibility with code that calls it.
		 */
		async getToken(): Promise<string | null> {
			return null;
		},

		/**
		 * Initialize new user with default metadata (credits, timezone, location).
		 * Called after user signs up for the first time.
		 */
		async initializeUser(
			timezone?: string,
			location?: GeocodedLocation | null,
			preferredLanguage?: string
		) {
			if (!timezone) {
				throw new Error('Please choose a timezone to finish onboarding.');
			}

			const response = await fetch(buildApiUrl('/onboarding/initialize'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					timezone,
					location: location ?? undefined,
					preferred_language: preferredLanguage ?? undefined
				})
			});

			const payload = await response.json();

			if (!response.ok) {
				throw new Error(payload?.detail || 'Failed to initialize user');
			}

			// Backend returns the full updated user dict — use it directly
			set({ authenticated: true, user: payload as User });

			return payload;
		},

		/**
		 * Update user preferences (language, timezone, CMS config) via backend API.
		 */
		async updatePreferences(params: {
			preferred_language?: string;
			timezone?: string;
			cms_api_url?: string;
			cms_api_token?: string;
		}): Promise<void> {
			const { apiClient } = await import('$lib/api-client');

			const result = await apiClient.updateUserPreferences(params);

			if (!result.success) {
				throw new Error('Failed to update preferences');
			}

			update((state) => {
				if (!state.user) return state;
				return {
					...state,
					user: {
						...state.user,
						...(params.preferred_language && { preferred_language: params.preferred_language }),
						...(params.timezone && { timezone: params.timezone }),
						...(params.cms_api_url !== undefined && { cms_api_url: params.cms_api_url || null }),
						...(params.cms_api_token !== undefined && { has_cms_token: !!params.cms_api_token })
					}
				};
			});
		}
	};
}

export const authStore = createAuthStore();

// Derived store for easy access to current user
export const currentUser = derived(authStore, ($authStore) => $authStore.user);

// Convenience alias -- some consumer code may use `auth` instead of `authStore`
export const auth = authStore;
