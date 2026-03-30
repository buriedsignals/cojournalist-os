/**
 * API Configuration -- resolves the backend API base URL.
 *
 * USED BY: api-client.ts, services/webhook-client.ts, stores/auth.ts
 * DEPENDS ON: VITE_API_URL env var (optional)
 *
 * Resolves VITE_API_URL into a normalized base URL. Falls back to '/api'
 * when no env var is set (same-origin proxy in dev/production).
 * Exports: API_BASE_URL (string), buildApiUrl(path) => full URL.
 */
const DEFAULT_API_PREFIX = '/api';

function resolveApiBaseUrl() {
	const rawBase = (import.meta.env.VITE_API_URL || '').trim();
	if (!rawBase) {
		return DEFAULT_API_PREFIX;
	}

	const trimmedBase = rawBase.replace(/\/$/, '');

	if (/^https?:\/\//i.test(trimmedBase)) {
		try {
			const url = new URL(trimmedBase);

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
