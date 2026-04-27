/**
 * API Configuration -- resolves the backend API base URL.
 *
 * USED BY: api-client.ts, services/webhook-client.ts, stores/auth.ts
 * DEPENDS ON: VITE_API_URL env var (optional), PUBLIC_DEPLOYMENT_TARGET,
 *             PUBLIC_SUPABASE_URL
 *
 * Supabase-native deployments default to the Edge Functions gateway when
 * VITE_API_URL is unset (or still left at the old '/api' placeholder).
 * Everything else keeps the same-origin '/api' default.
 */
const DEFAULT_API_PREFIX = '/api';
const SUPABASE_FUNCTIONS_PREFIX = '/functions/v1';
const deploymentTarget = (import.meta.env.PUBLIC_DEPLOYMENT_TARGET || '').trim().toLowerCase();
const supabaseUrl = (import.meta.env.PUBLIC_SUPABASE_URL || '').trim().replace(/\/$/, '');

function resolveSupabaseFunctionsBase(): string | null {
	if (!supabaseUrl) return null;
	return `${supabaseUrl}${SUPABASE_FUNCTIONS_PREFIX}`;
}

function resolveApiBaseUrl() {
	const rawBase = (import.meta.env.VITE_API_URL || '').trim();
	const supabaseFunctionsBase =
		deploymentTarget === 'supabase' ? resolveSupabaseFunctionsBase() : null;

	if (!rawBase) {
		return supabaseFunctionsBase ?? DEFAULT_API_PREFIX;
	}

	const trimmedBase = rawBase.replace(/\/$/, '');

	if (supabaseFunctionsBase && trimmedBase === DEFAULT_API_PREFIX) {
		return supabaseFunctionsBase;
	}

	if (/^https?:\/\//i.test(trimmedBase)) {
		try {
			const url = new URL(trimmedBase);

			if (supabaseFunctionsBase && url.pathname === DEFAULT_API_PREFIX) {
				return supabaseFunctionsBase;
			}

			if (!url.pathname || url.pathname === '/') {
				url.pathname = DEFAULT_API_PREFIX;
			} else {
				url.pathname = url.pathname.replace(/\/$/, '');
			}

			return url.toString().replace(/\/$/, '');
		} catch {
			// fall through to the generic handling below
		}
	}

	if (trimmedBase.startsWith('/')) {
		return trimmedBase || DEFAULT_API_PREFIX;
	}

	if (trimmedBase.toLowerCase().includes('/api')) {
		return trimmedBase;
	}

	return `${trimmedBase}${DEFAULT_API_PREFIX}`;
}

export const API_BASE_URL = resolveApiBaseUrl();

export const buildApiUrl = (path: string) => {
	const normalizedPath = path.startsWith('/') ? path : `/${path}`;
	return `${API_BASE_URL}${normalizedPath}`;
};

/**
 * Build a URL for the residual FastAPI service that still runs on Render.
 *
 * Most product APIs now live behind Supabase Edge Functions and use
 * buildApiUrl(). A few SaaS-only endpoints, including Linear feedback, still
 * live in FastAPI at the same-origin /api prefix in production and behind the
 * Vite /api proxy in local development.
 */
export const buildFastApiUrl = (path: string) => {
	const normalizedPath = path.startsWith('/') ? path : `/${path}`;
	return `${DEFAULT_API_PREFIX}${normalizedPath}`;
};
