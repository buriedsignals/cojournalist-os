/**
 * Supabase Auth Store -- Supabase Auth authentication and user state.
 *
 * Replacement for auth-muckrock.ts when PUBLIC_DEPLOYMENT_TARGET=supabase.
 * Uses @supabase/supabase-js for email/password authentication.
 *
 * USED BY: auth.ts (conditional loader)
 * DEPENDS ON: @supabase/supabase-js, $lib/config/api (buildApiUrl)
 */
import { browser } from '$app/environment';
import { writable, derived } from 'svelte/store';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { User, AuthState, GeocodedLocation } from '$lib/types';
import { buildApiUrl } from '$lib/config/api';

const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL ?? '';
const SUPABASE_ANON_KEY = import.meta.env.PUBLIC_SUPABASE_ANON_KEY ?? '';

let supabase: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
	if (!supabase) {
		supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
	}
	return supabase;
}

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
		 * Initialize auth state by checking Supabase session.
		 */
		async init() {
			if (!browser) return;
			if (initialized) return;
			initialized = true;

			const sb = getSupabase();

			try {
				const {
					data: { session }
				} = await sb.auth.getSession();

				if (session) {
					// Authentication proven by the session alone — don't gate the
					// authenticated flag on a profile fetch. Use the session's
					// user + metadata immediately so a refresh never bounces back
					// to /login while we wait on the backend.
					const sessionUser = {
						user_id: session.user.id,
						email: session.user.email ?? null,
						credits: 0,
						...(session.user.user_metadata ?? {})
					} as unknown as User;
					set({ authenticated: true, user: sessionUser });

					// Try to enrich with the full profile from the `user` Edge
					// Function. Silently fall back to session-derived user if
					// the endpoint isn't reachable.
					try {
						const response = await fetch(buildApiUrl('/user/me'), {
							headers: {
								Authorization: `Bearer ${session.access_token}`
							}
						});
						if (response.ok) {
							const data = await response.json();
							update((s) => ({ ...s, user: { ...sessionUser, ...data } }));
						}
					} catch {
						/* keep session-derived user */
					}
				} else {
					set({ authenticated: false, user: null });
				}
			} catch {
				set({ authenticated: false, user: null });
			}

			// Listen for auth state changes (token refresh, sign out)
			sb.auth.onAuthStateChange(async (event, session) => {
				if (event === 'SIGNED_OUT' || !session) {
					set({ authenticated: false, user: null });
					initialized = false;
				}
			});
		},

		/**
		 * Redirect to Supabase login page.
		 */
		login() {
			if (!browser) return;
			window.location.href = '/api/auth/login';
		},

		/**
		 * Sign out via Supabase.
		 */
		async signOut() {
			const sb = getSupabase();
			await sb.auth.signOut();
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

			const sb = getSupabase();
			const {
				data: { session }
			} = await sb.auth.getSession();

			if (!session) return;

			try {
				const response = await fetch(buildApiUrl('/user/me'), {
					headers: {
						Authorization: `Bearer ${session.access_token}`
					}
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
		 * Optimistically update the current credit balance in the store.
		 * Called after a scout run returns a new balance in its response; the
		 * next /user/me refresh reconciles against the server-of-record.
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
		 * Get the Supabase access token for API calls.
		 */
		async getToken(): Promise<string | null> {
			if (!browser) return null;
			const sb = getSupabase();
			const {
				data: { session }
			} = await sb.auth.getSession();
			return session?.access_token ?? null;
		},

		/**
		 * Initialize new user with default metadata.
		 */
		async initializeUser(
			timezone?: string,
			location?: GeocodedLocation | null,
			preferredLanguage?: string
		) {
			if (!timezone) {
				throw new Error('Please choose a timezone to finish onboarding.');
			}

			const sb = getSupabase();
			const {
				data: { session }
			} = await sb.auth.getSession();

			if (!session) {
				throw new Error('Not authenticated');
			}

			const response = await fetch(buildApiUrl('/onboarding/initialize'), {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session.access_token}`
				},
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

			set({ authenticated: true, user: payload as User });
			return payload;
		},

		/**
		 * Update user preferences via backend API.
		 */
		async updatePreferences(params: {
			preferred_language?: string;
			timezone?: string;
			health_notifications_enabled?: boolean;
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
						...(params.preferred_language && {
							preferred_language: params.preferred_language
						}),
						...(params.timezone && { timezone: params.timezone }),
						...(params.health_notifications_enabled !== undefined && {
							health_notifications_enabled: params.health_notifications_enabled
						})
					}
				};
			});
		}
	};
}

export const authStore = createAuthStore();
export const currentUser = derived(authStore, ($authStore) => $authStore.user);
export const auth = authStore;
