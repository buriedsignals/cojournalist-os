/**
 * Tests for the API client — verifies request URLs, methods, bodies, and error handling.
 * Mocks fetch to test the frontend->backend contract.
 * Auth is Bearer JWT via authStore.getToken() — no cookies.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/config/api', () => ({
	API_BASE_URL: '/api',
	buildApiUrl: (path: string) => `/api${path.startsWith('/') ? path : '/' + path}`
}));

import { apiClient } from '$lib/api-client';

// ---- Test helpers ----

function mockFetchResponse(body: unknown, status = 200) {
	return vi.fn().mockResolvedValue({
		ok: status >= 200 && status < 300,
		status,
		json: vi.fn().mockResolvedValue(body),
		text: vi.fn().mockResolvedValue(JSON.stringify(body))
	});
}

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
	vi.clearAllMocks();
	fetchSpy = mockFetchResponse({});
	vi.stubGlobal('fetch', fetchSpy);
});

// ===========================================================================
// getActiveJobs
// ===========================================================================

describe('getActiveJobs', () => {
	it('calls GET /scrapers/active with Bearer auth', async () => {
		fetchSpy = mockFetchResponse({ scrapers: [] });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.getActiveJobs();

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/scrapers/active',
			expect.objectContaining({
				method: 'GET',
				headers: expect.objectContaining({ 'Content-Type': 'application/json' })
			})
		);
		const options = fetchSpy.mock.calls[0][1];
		expect(options.credentials).toBeUndefined();
	});

	it('returns parsed response', async () => {
		const mockScouts = { scrapers: [{ scraper_name: 'test' }] };
		fetchSpy = mockFetchResponse(mockScouts);
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.getActiveJobs();
		expect(result).toEqual(mockScouts);
	});

	it('throws on API error', async () => {
		fetchSpy = mockFetchResponse({ detail: 'Server error' }, 500);
		vi.stubGlobal('fetch', fetchSpy);

		await expect(apiClient.getActiveJobs()).rejects.toThrow('Server error');
	});
});

// ===========================================================================
// deleteActiveJob
// ===========================================================================

describe('deleteActiveJob', () => {
	it('calls DELETE with encoded scout name', async () => {
		fetchSpy = mockFetchResponse(undefined, 204);
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.deleteActiveJob('my scout name');

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/scrapers/active/my%20scout%20name',
			expect.objectContaining({ method: 'DELETE' })
		);
	});

	it('handles special characters in scout name', async () => {
		fetchSpy = mockFetchResponse(undefined, 204);
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.deleteActiveJob('scout/with&special');

		const url = fetchSpy.mock.calls[0][0];
		expect(url).toContain(encodeURIComponent('scout/with&special'));
	});
});

// ===========================================================================
// runScoutNow
// ===========================================================================

describe('runScoutNow', () => {
	it('calls POST /scrapers/run-now with scout name', async () => {
		const mockResult = { scraper_status: true, criteria_status: true, summary: 'Found changes' };
		fetchSpy = mockFetchResponse(mockResult);
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.runScoutNow('test-scout');

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/scrapers/run-now',
			expect.objectContaining({
				method: 'POST',
					body: JSON.stringify({ scraper_name: 'test-scout' })
			})
		);
		expect(result).toEqual(mockResult);
	});
});

// ===========================================================================
// validateCredits
// ===========================================================================

describe('validateCredits', () => {
	it('returns valid when credits are sufficient', async () => {
		fetchSpy = mockFetchResponse({ current_credits: 10, per_run_cost: 1 });
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.validateCredits(1, 'monitoring');

		expect(result.valid).toBe(true);
	});

	it('returns invalid on 402 with credit details', async () => {
		fetchSpy = mockFetchResponse(
			{ current_credits: 0, required_credits: 2 },
			402
		);
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.validateCredits(2, 'monitoring');

		expect(result.valid).toBe(false);
		expect(result.current_credits).toBe(0);
		expect(result.required_credits).toBe(2);
	});
});

// ===========================================================================
// searchPulse
// ===========================================================================

describe('searchPulse', () => {
	it('requires location or criteria', async () => {
		await expect(apiClient.searchPulse({})).rejects.toThrow(
			'Location or criteria is required'
		);
	});

	it('sends criteria-only search', async () => {
		const mockResult = { status: 'completed', articles: [] };
		fetchSpy = mockFetchResponse(mockResult);
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.searchPulse({ criteria: 'AI' });

		const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
		expect(body.criteria).toBe('AI');
		expect(body.category).toBe('news');
	});

	it('sends location search', async () => {
		const loc = { displayName: 'Zurich', country: 'CH', state: 'Zurich', city: 'Zurich', locationType: 'city' as const, maptilerId: 'maptiler-123' };
		fetchSpy = mockFetchResponse({ status: 'completed', articles: [] });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.searchPulse({ location: loc });

		const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
		expect(body.location.displayName).toBe('Zurich');
	});

	it('passes custom filter prompt', async () => {
		fetchSpy = mockFetchResponse({ status: 'completed', articles: [] });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.searchPulse({
			criteria: 'tech',
			custom_filter_prompt: 'Focus on startups'
		});

		const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
		expect(body.custom_filter_prompt).toBe('Focus on startups');
	});
});

// ===========================================================================
// scheduleMonitoring
// ===========================================================================

describe('scheduleMonitoring', () => {
	it('sends POST with full payload', async () => {
		const payload = {
			name: 'my-scout',
			url: 'https://example.com',
			criteria: 'price changes',
			regularity: 'daily' as const,
			day_number: 1,
			time: '09:00',
			channel: 'website' as const,
			monitoring: 'EMAIL' as const
		};

		fetchSpy = mockFetchResponse({ success: true });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.scheduleMonitoring(payload);

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/scrapers/monitoring',
			expect.objectContaining({
				method: 'POST',
					body: JSON.stringify(payload)
			})
		);
	});
});

// ===========================================================================
// Information Units API
// ===========================================================================

describe('Information Units', () => {
	it('getUserUnitLocations calls GET /units/locations', async () => {
		fetchSpy = mockFetchResponse({ locations: ['CH#Zurich#_'] });
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.getUserUnitLocations();

		expect(fetchSpy.mock.calls[0][0]).toBe('/api/units/locations');
		expect(result.locations).toEqual(['CH#Zurich#_']);
	});

	it('getUnitsByTopic passes topic as query param', async () => {
		fetchSpy = mockFetchResponse({ units: [], count: 0 });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.getUnitsByTopic({ topic: 'Climate' });

		const url: string = fetchSpy.mock.calls[0][0];
		expect(url).toContain('topic=Climate');
	});

	it('searchUnitsSemantic passes query param', async () => {
		fetchSpy = mockFetchResponse({ units: [], count: 0, query: 'AI' });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.searchUnitsSemantic({ query: 'AI' });

		const url: string = fetchSpy.mock.calls[0][0];
		expect(url).toContain('query=AI');
	});

	it('markUnitsUsed sends PATCH with unit keys', async () => {
		fetchSpy = mockFetchResponse({ marked_count: 2, total_requested: 2 });
		vi.stubGlobal('fetch', fetchSpy);

		const keys = [
			{ pk: 'USER#123', sk: 'UNIT#abc' },
			{ pk: 'USER#123', sk: 'UNIT#def' }
		];
		await apiClient.markUnitsUsed(keys);

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/units/mark-used',
			expect.objectContaining({
				method: 'PATCH',
					body: JSON.stringify({ unit_keys: keys })
			})
		);
	});
});

// ===========================================================================
// updateUserPreferences
// ===========================================================================

describe('updateUserPreferences', () => {
	it('sends only changed fields', async () => {
		fetchSpy = mockFetchResponse({ success: true, preferred_language: 'fr' });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.updateUserPreferences({ preferred_language: 'fr' });

		const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
		expect(body).toEqual({ preferred_language: 'fr' });
	});
});

// ===========================================================================
// autoSelectUnits
// ===========================================================================

describe('autoSelectUnits', () => {
	const mockParams = {
		units: [
			{
				unit_id: 'unit-001',
				statement: 'City council approved new budget',
				entities: ['City Council', 'Budget Office'],
				source_title: 'Local Times',
				created_at: '2026-03-01T10:00:00Z',
				date: null,
				unit_type: 'fact',
				scout_type: 'pulse'
			},
			{
				unit_id: 'unit-002',
				statement: 'New park opens downtown',
				entities: ['Parks Department'],
				source_title: 'City News',
				created_at: '2026-03-02T12:00:00Z',
				date: null,
				unit_type: 'event',
				scout_type: 'pulse'
			}
		],
		prompt: 'Select units about local government spending',
		location: 'Zurich, Switzerland',
		topic: null
	};

	it('sends POST to /export/auto-select with correct body', async () => {
		const mockResponse = {
			selected_unit_ids: ['unit-001'],
			selection_summary: 'Selected 1 unit about government budget decisions'
		};
		fetchSpy = mockFetchResponse(mockResponse);
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.autoSelectUnits(mockParams);

		expect(fetchSpy).toHaveBeenCalledWith(
			'/api/export/auto-select',
			expect.objectContaining({
				method: 'POST',
					body: JSON.stringify(mockParams)
			})
		);
	});

	it('returns selected_unit_ids and selection_summary', async () => {
		const mockResponse = {
			selected_unit_ids: ['unit-001', 'unit-002'],
			selection_summary: 'Selected 2 units matching the prompt'
		};
		fetchSpy = mockFetchResponse(mockResponse);
		vi.stubGlobal('fetch', fetchSpy);

		const result = await apiClient.autoSelectUnits(mockParams);

		expect(result.selected_unit_ids).toEqual(['unit-001', 'unit-002']);
		expect(result.selection_summary).toBe('Selected 2 units matching the prompt');
	});

	it('preserves date: null in the request body (not stripped)', async () => {
		fetchSpy = mockFetchResponse({ selected_unit_ids: [], selection_summary: '' });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.autoSelectUnits(mockParams);

		const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
		expect(body.units[0]).toHaveProperty('date', null);
		expect(body.units[1]).toHaveProperty('date', null);
		expect(body.topic).toBeNull();
	});

	it('throws on API error', async () => {
		fetchSpy = mockFetchResponse({ detail: 'Insufficient credits' }, 402);
		vi.stubGlobal('fetch', fetchSpy);

		await expect(apiClient.autoSelectUnits(mockParams)).rejects.toThrow('Insufficient credits');
	});
});

// ===========================================================================
// Cookie-based auth
// ===========================================================================

describe('Bearer auth', () => {
	it('all requests omit credentials (Authorization attached only when token exists)', async () => {
		fetchSpy = mockFetchResponse({ scrapers: [] });
		vi.stubGlobal('fetch', fetchSpy);

		await apiClient.getActiveJobs();

		const options = fetchSpy.mock.calls[0][1];
		// credentials dropped — Supabase Edge Functions return '*' origin;
		// browsers reject credentials:'include' with wildcard CORS.
		expect(options.credentials).toBeUndefined();
		expect(options.headers['Content-Type']).toBe('application/json');
		// In this test the authStore is unmocked, so getToken returns null and
		// no Authorization header is attached. api-client-workspace.test.ts
		// covers the Bearer-token-present path with a mocked authStore.
	});
});
