/**
 * API Client -- typed wrapper for all FastAPI backend calls.
 *
 * USED BY: FeedView, ExportSlideOver, UnitCard, UnitGrid, ActiveJobsModal,
 *          ScoutScheduleModal, SmartScoutView, ScoutsPanel, DataExtract,
 *          stores/feed.ts, stores/notifications.ts, stores/pulse.ts,
 *          utils/feed.ts,
 *          tests/api-client.test.ts
 * DEPENDS ON: $lib/config/api (buildApiUrl), $lib/types
 *
 * Uses httpOnly session cookies for authentication (credentials: 'include').
 * Also exports shared types: InformationUnit, ExportDraft.
 */
import type {
	MonitoringSetupRequest,
	MonitoringSetupResponse,
	GeocodedLocation,
	ScoutSetupRequest,
	ScoutSetupResponse,
	User
} from '$lib/types';
import { buildApiUrl } from '$lib/config/api';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/**
 * Standard JSON headers for API requests.
 * Authentication is handled via httpOnly cookies (credentials: 'include').
 */
const JSON_HEADERS: Record<string, string> = {
	'Content-Type': 'application/json'
};

/**
 * Normalize a FastAPI error detail field into a human-readable string.
 * Handles string, array-of-objects (validation errors), and unknown shapes.
 */
function normalizeErrorDetail(detail: unknown, fallback: string): string {
	if (typeof detail === 'string') return detail;
	if (Array.isArray(detail))
		return detail.map((e: { msg?: string }) => e.msg || String(e)).join('; ');
	return fallback;
}

/**
 * Generic authenticated API request.
 * Uses session cookies for auth (credentials: 'include').
 */
async function apiRequest<T>(
	method: string,
	path: string,
	body?: unknown
): Promise<T> {
	const response = await fetch(buildApiUrl(path), {
		method,
		headers: JSON_HEADERS,
		credentials: 'include',
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(normalizeErrorDetail(error.detail, `API error: ${response.status}`));
	}

	return response.json();
}

/**
 * Like apiRequest, but uses safe JSON parsing for error responses
 * (handles cases where the error body is not valid JSON).
 * Also checks error.error as a fallback detail field.
 */
async function apiRequestSafeError<T>(
	method: string,
	path: string,
	body: unknown,
	fallbackMessage: string
): Promise<T> {
	const response = await fetch(buildApiUrl(path), {
		method,
		headers: JSON_HEADERS,
		credentials: 'include',
		body: JSON.stringify(body)
	});

	if (!response.ok) {
		let detail = fallbackMessage;
		try {
			const error = await response.json();
			detail = normalizeErrorDetail(error.detail, '') || error.error || detail;
		} catch {
			// Response body is not valid JSON
		}
		throw new Error(detail);
	}

	return response.json();
}

/**
 * Build a query string from an object, omitting undefined/null values.
 * Number values are converted to strings.
 */
function buildQueryString(params: Record<string, string | number | undefined | null>): string {
	const searchParams = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value != null) {
			searchParams.set(key, String(value));
		}
	}
	return searchParams.toString();
}

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------

/**
 * API Client for backend communication.
 */
export const apiClient = {
	/**
	 * Get all active monitoring jobs from AWS.
	 */
	async getActiveJobs(): Promise<import('$lib/types').ActiveJobsResponse> {
		return apiRequest('GET', '/scrapers/active');
	},

	/**
	 * Delete an active monitoring job from AWS.
	 */
	async deleteActiveJob(scraperName: string): Promise<void> {
		const response = await fetch(
			buildApiUrl(`/scrapers/active/${encodeURIComponent(scraperName)}`),
			{
				method: 'DELETE',
				headers: JSON_HEADERS,
				credentials: 'include'
			}
		);

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to delete monitoring job');
		}

		if (response.status === 204) return;
		return response.json();
	},

	/**
	 * Schedule a monitoring job for a scraper.
	 */
	async scheduleMonitoring(payload: MonitoringSetupRequest): Promise<MonitoringSetupResponse> {
		return apiRequestSafeError('POST', '/scrapers/monitoring', payload, 'Failed to schedule monitoring');
	},

	/**
	 * Schedule a local scout (pulse).
	 */
	async scheduleLocalScout(payload: ScoutSetupRequest): Promise<ScoutSetupResponse> {
		return apiRequestSafeError('POST', '/scrapers/monitoring', payload, 'Failed to schedule local scout');
	},

	/**
	 * Manually trigger a scout execution ("Run Now").
	 */
	async runScoutNow(scraperName: string): Promise<{
		scraper_status: boolean;
		criteria_status: boolean;
		summary: string;
		notification_sent?: boolean;
		change_status?: string;
	}> {
		return apiRequestSafeError('POST', '/scrapers/run-now', { scraper_name: scraperName }, 'Failed to run scout');
	},

	/**
	 * Get authentication status. Does not throw on errors.
	 */
	async getAuthStatus(): Promise<{ authenticated: boolean; user: User | null }> {
		try {
			const response = await fetch(buildApiUrl('/auth/me'), {
				method: 'GET',
				headers: JSON_HEADERS,
				credentials: 'include'
			});

			if (!response.ok) {
				return { authenticated: false, user: null };
			}

			const user = await response.json();
			return { authenticated: true, user };
		} catch {
			return { authenticated: false, user: null };
		}
	},

	/**
	 * AI-orchestrated pulse search.
	 * Returns AI-curated news articles for a location and/or topic (~30-60s).
	 */
	async searchPulse(filters: {
		location?: GeocodedLocation;
		category?: import('$lib/types').SearchCategory;
		custom_filter_prompt?: string;
		source_mode?: 'reliable' | 'niche';
		criteria?: string;
		excluded_domains?: string[];
	}): Promise<import('$lib/types').PulseSearchResponse> {
		if (!filters.location && !filters.criteria) {
			throw new Error('Location or criteria is required for pulse search');
		}

		const body: Record<string, unknown> = {
			category: filters.category || 'news',
			custom_filter_prompt: filters.custom_filter_prompt || undefined
		};
		if (filters.location) body.location = filters.location;
		if (filters.source_mode) body.source_mode = filters.source_mode;
		if (filters.criteria) body.criteria = filters.criteria;
		if (filters.excluded_domains?.length) body.excluded_domains = filters.excluded_domains;

		const response = await fetch(buildApiUrl('/pulse/search'), {
			method: 'POST',
			headers: JSON_HEADERS,
			credentials: 'include',
			body: JSON.stringify(body)
		});

		let result;
		try {
			result = await response.json();
		} catch {
			const textError = await response.text().catch(() => 'Unknown server error');
			console.error('[API] searchPulse received non-JSON response:', textError);
			throw new Error(`Server error: ${textError || 'Unknown error'}`);
		}

		if (!response.ok || result.status === 'failed') {
			console.error('[API] searchPulse error:', result);
			throw new Error(result.detail || result.response_markdown || 'Failed to search pulse');
		}

		return result;
	},

	/**
	 * Discover council/civic pages for a root domain.
	 * Returns candidate URLs found on the council website.
	 */
	async discoverCivic(rootDomain: string): Promise<{
		candidates: Array<{ url: string; description: string; confidence: number }>;
	}> {
		return apiRequest('POST', '/civic/discover', {
			root_domain: rootDomain,
		});
	},

	/**
	 * Test civic scout extraction on selected URLs.
	 * Returns preview of extracted promises without storing anything.
	 */
	async testCivic(trackedUrls: string[], criteria?: string): Promise<{
		valid: boolean;
		documents_found: number;
		sample_promises: Array<{ promise_text: string; context: string; source_url: string; source_date: string; due_date?: string; date_confidence: string; criteria_match: boolean }>;
		error?: string;
	}> {
		return apiRequest('POST', '/civic/test', {
			tracked_urls: trackedUrls,
			...(criteria ? { criteria } : {}),
		});
	},

	/**
	 * Start an async data extraction job.
	 */
	async startExtraction(payload: {
		url: string;
		target: string;
		channel: string;
		criteria?: string;
	}): Promise<{ job_id: string; status: string }> {
		return apiRequest('POST', '/extract/start', payload);
	},

	/**
	 * Get the status of an extraction job.
	 */
	async getExtractionStatus(jobId: string): Promise<{
		job_id: string;
		status: 'running' | 'completed' | 'failed';
		result?: any;
		error?: string;
	}> {
		return apiRequest('GET', `/extract/status/${jobId}`);
	},

	/**
	 * Validate credits before extraction.
	 * Throws an error with type 'insufficient_credits' if user doesn't have enough.
	 */
	async validateExtractionCredits(payload: {
		url: string;
		target: string;
		channel: string;
	}): Promise<{
		valid: boolean;
		cost: number;
		current_credits: number;
		remaining_after: number;
	}> {
		const response = await fetch(buildApiUrl('/extract/validate'), {
			method: 'POST',
			headers: JSON_HEADERS,
			credentials: 'include',
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			const error = await response.json();
			if (response.status === 402) {
				throw { type: 'insufficient_credits', ...error.detail };
			}
			throw new Error(error.detail || 'Failed to validate credits');
		}

		return response.json();
	},

	/**
	 * Validate credits before monitoring setup.
	 * Throws an error with type 'insufficient_credits' if user doesn't have enough.
	 */
	async validateMonitoringCredits(payload: {
		channel: string;
		regularity: string;
		scout_type?: string;
		platform?: string;
		source_mode?: string;
		has_location?: boolean;
	}): Promise<{
		valid: boolean;
		per_run_cost: number;
		monthly_cost: number;
		current_credits: number;
		remaining_after: number;
	}> {
		const response = await fetch(buildApiUrl('/scrapers/monitoring/validate'), {
			method: 'POST',
			headers: JSON_HEADERS,
			credentials: 'include',
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			const error = await response.json();
			if (response.status === 402) {
				throw { type: 'insufficient_credits', ...error.detail };
			}
			throw new Error(error.detail || 'Failed to validate credits');
		}

		return response.json();
	},

	// ==================== Information Units API ====================

	/**
	 * Get distinct locations where user has information units.
	 */
	async getUserUnitLocations(): Promise<{ locations: string[] }> {
		return apiRequest('GET', '/units/locations');
	},

	/**
	 * Get all unused information units (no location/topic filter).
	 */
	async getAllUnusedUnits(limit: number = 50): Promise<{
		units: InformationUnit[];
		count: number;
	}> {
		const qs = buildQueryString({ limit });
		return apiRequest('GET', `/units/all?${qs}`);
	},

	/**
	 * Get only unused information units for a location.
	 */
	async getUnusedUnitsByLocation(params: {
		country: string;
		state?: string;
		city?: string;
		displayName: string;
		limit?: number;
	}): Promise<{
		units: InformationUnit[];
		count: number;
	}> {
		const qs = buildQueryString({
			country: params.country,
			state: params.state,
			city: params.city,
			displayName: params.displayName,
			limit: params.limit
		});
		return apiRequest('GET', `/units/unused?${qs}`);
	},

	/**
	 * Mark units as used in an article.
	 */
	async markUnitsUsed(unitKeys: { pk: string; sk: string }[]): Promise<{
		marked_count: number;
		total_requested: number;
	}> {
		return apiRequest('PATCH', '/units/mark-used', { unit_keys: unitKeys });
	},

	/**
	 * Generate an export from selected information units.
	 */
	async generateExportDraft(params: {
		units: {
			statement: string;
			source_title: string;
			source_url: string;
			unit_type?: string;
			entities?: string[];
			source_domain?: string | null;
			topic?: string | null;
		}[];
		location_name: string;
		language?: string;
		custom_system_prompt?: string;
	}): Promise<ExportDraft> {
		const body: Record<string, unknown> = {
			units: params.units,
			location_name: params.location_name
		};
		if (params.language) body.language = params.language;
		if (params.custom_system_prompt) body.custom_system_prompt = params.custom_system_prompt;
		return apiRequest('POST', '/export/generate', body);
	},

	/**
	 * AI-powered auto-selection of information units based on a prompt.
	 * Returns IDs of selected units and a summary of why they were chosen.
	 */
	async autoSelectUnits(params: {
		units: {
			unit_id: string;
			statement: string;
			entities: string[];
			source_title: string;
			created_at: string;
			date: string | null;
			unit_type: string;
			scout_type: string;
		}[];
		prompt: string;
		location: string | null;
		topic: string | null;
	}): Promise<{ selected_unit_ids: string[]; selection_summary: string }> {
		return apiRequest('POST', '/export/auto-select', params);
	},

	/**
	 * Update user preferences (language, timezone, and/or excluded domains).
	 */
	async updateUserPreferences(params: {
		preferred_language?: string;
		timezone?: string;
		excluded_domains?: string[];
		cms_api_url?: string;
		cms_api_token?: string;
	}): Promise<{ success: boolean; preferred_language?: string; timezone?: string; excluded_domains?: string[] }> {
		return apiRequest('PUT', '/user/preferences', params);
	},

	/**
	 * Get distinct topics where user has information units.
	 */
	async getUserUnitTopics(): Promise<{ topics: string[] }> {
		return apiRequest('GET', '/units/topics');
	},

	/**
	 * Get information units for a specific topic.
	 */
	async getUnitsByTopic(params: {
		topic: string;
		limit?: number;
	}): Promise<{
		units: InformationUnit[];
		count: number;
	}> {
		const qs = buildQueryString({ topic: params.topic, limit: params.limit });
		return apiRequest('GET', `/units/by-topic?${qs}`);
	},

	/**
	 * Semantic search across information units.
	 */
	async searchUnitsSemantic(params: {
		country?: string;
		state?: string;
		city?: string;
		displayName?: string;
		topic?: string;
		query: string;
		limit?: number;
	}): Promise<{
		units: (InformationUnit & { similarity_score: number })[];
		count: number;
		query: string;
	}> {
		const qs = buildQueryString({
			country: params.country,
			state: params.state,
			city: params.city,
			displayName: params.displayName,
			topic: params.topic,
			query: params.query,
			limit: params.limit
		});
		return apiRequest('GET', `/units/search?${qs}`);
	},

	/**
	 * Export a draft to the user's configured CMS endpoint.
	 */
	async exportToCms(payload: {
		draft: ExportDraft;
		units: { statement: string; source_title: string; source_url: string }[];
	}): Promise<{ success: boolean }> {
		return apiRequest('POST', '/export/to-cms', payload);
	},

	// ==================== API Key Management ====================

	/**
	 * Create a new API key.
	 */
	async createApiKey(name?: string): Promise<{
		key: string;
		key_id: string;
		key_prefix: string;
		name: string;
		created_at: string;
	}> {
		return apiRequest('POST', '/v1/keys', { name: name || 'My API Key' });
	},

	/**
	 * List all API keys for the current user.
	 */
	async listApiKeys(): Promise<{
		keys: Array<{
			key_id: string;
			key_prefix: string;
			name: string;
			created_at: string;
			last_used_at: string | null;
		}>;
		count: number;
	}> {
		return apiRequest('GET', '/v1/keys');
	},

	/**
	 * Revoke an API key.
	 */
	async revokeApiKey(keyId: string): Promise<void> {
		return apiRequest('DELETE', `/v1/keys/${keyId}`);
	},

	/**
	 * Validate credits for an operation.
	 * Returns 402 status if insufficient credits.
	 */
	async validateCredits(
		required_credits: number,
		operation_type?: string
	): Promise<{ valid: boolean; current_credits: number; required_credits: number }> {
		const response = await fetch(buildApiUrl('/scrapers/monitoring/validate'), {
			method: 'POST',
			headers: JSON_HEADERS,
			credentials: 'include',
			body: JSON.stringify({
				channel: 'website',
				regularity: 'monthly',
				scout_type: operation_type || 'web'
			})
		});

		if (response.status === 402) {
			const error = await response.json();
			return {
				valid: false,
				current_credits: error.current_credits || 0,
				required_credits: error.required_credits || required_credits
			};
		}

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to validate credits');
		}

		const data = await response.json();
		return {
			valid: true,
			current_credits: data.current_credits || 0,
			required_credits
		};
	}
};

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

/**
 * Atomic information unit from scout execution.
 */
export interface InformationUnit {
	unit_id: string;
	pk: string;
	sk: string;
	statement: string;
	unit_type: string;
	entities: string[];
	source_url: string;
	source_domain: string | null;
	source_title: string;
	scout_type: string;
	scout_id: string;
	topic?: string;
	created_at: string;
	used_in_article: boolean;
	date?: string | null;
}

/**
 * Generated export from information units.
 */
export interface ExportDraft {
	title: string;
	headline: string;
	sections: { heading: string; content: string }[];
	gaps: string[];
	bullet_points: string[];
	sources: { title: string; url: string; domain?: string }[];
}
