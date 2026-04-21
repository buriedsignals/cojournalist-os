/**
 * Tests for the workspace units store — pagination, search reset, state
 * transitions.
 *
 * Uses a stubbed api surface (no fetch mocks). Focuses on store semantics:
 * who sets what, when, and the reset/search interaction.
 */
import { describe, it, expect, vi } from 'vitest';
import type { WorkspaceUnit, WorkspacePaginatedUnits } from '$lib/api-client';
import { createUnitsStore, type UnitsApi } from '$lib/stores/workspace/units';

function unit(partial: Partial<WorkspaceUnit>): WorkspaceUnit {
	return {
		id: 'u-x',
		statement: 'hello',
		context_excerpt: null,
		unit_type: 'fact',
		entities: [],
		location: null,
		occurred_at: null,
		extracted_at: '2026-01-01T00:00:00Z',
		source: { url: null, title: null, domain: null },
		...partial
	};
}

describe('workspace units store', () => {
	// ---------------------------------------------------------------------
	// load
	// ---------------------------------------------------------------------

	it('load() replaces units and records scope + cursor', async () => {
		const page: WorkspacePaginatedUnits = {
			units: [unit({ id: 'u1' }), unit({ id: 'u2' })],
			next_cursor: '50'
		};
		const api = {
			listUnits: vi.fn(async () => page),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');

		const s = store.getState();
		expect(s.units.map((u) => u.id)).toEqual(['u1', 'u2']);
		expect(s.scoutId).toBe('s1');
		expect(s.cursor).toBe('50');
		expect(s.hasMore).toBe(true);
		expect(s.loading).toBe(false);
		expect(s.searchQuery).toBe('');
		expect(api.listUnits).toHaveBeenCalledWith('s1', null);
	});

	it('load() with null loads all scouts', async () => {
		const api = {
			listUnits: vi.fn(async () => ({ units: [], next_cursor: null })),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load(null);
		expect(api.listUnits).toHaveBeenCalledWith(null, null);
		expect(store.getState().hasMore).toBe(false);
	});

	// ---------------------------------------------------------------------
	// loadMore — pagination
	// ---------------------------------------------------------------------

	it('loadMore() appends the next page and advances the cursor', async () => {
		const first: WorkspacePaginatedUnits = {
			units: [unit({ id: 'u1' }), unit({ id: 'u2' })],
			next_cursor: '50'
		};
		const second: WorkspacePaginatedUnits = {
			units: [unit({ id: 'u3' })],
			next_cursor: null
		};
		const api = {
			listUnits: vi
				.fn()
				.mockResolvedValueOnce(first)
				.mockResolvedValueOnce(second),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		await store.loadMore();

		const s = store.getState();
		expect(s.units.map((u) => u.id)).toEqual(['u1', 'u2', 'u3']);
		expect(s.cursor).toBeNull();
		expect(s.hasMore).toBe(false);
		expect(api.listUnits).toHaveBeenNthCalledWith(2, 's1', '50');
	});

	it('loadMore() no-ops when hasMore=false', async () => {
		const api = {
			listUnits: vi.fn(async () => ({ units: [], next_cursor: null })),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load(null);
		api.listUnits.mockClear();

		await store.loadMore();
		expect(api.listUnits).not.toHaveBeenCalled();
	});

	// ---------------------------------------------------------------------
	// search — replaces list, clears cursor
	// ---------------------------------------------------------------------

	it('search() replaces the list with search results and clears hasMore', async () => {
		const initial: WorkspacePaginatedUnits = {
			units: [unit({ id: 'u1' }), unit({ id: 'u2' })],
			next_cursor: '50'
		};
		const hits = [unit({ id: 'u-hit' })];
		const api = {
			listUnits: vi.fn(async () => initial),
			searchUnits: vi.fn(async () => hits)
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		await store.search('climate');

		const s = store.getState();
		expect(s.searchQuery).toBe('climate');
		expect(s.units).toEqual(hits);
		expect(s.hasMore).toBe(false);
		expect(s.cursor).toBeNull();
		expect(api.searchUnits).toHaveBeenCalledWith('climate', 's1');
	});

	it('search("") exits search mode and reloads the current scout', async () => {
		const reload: WorkspacePaginatedUnits = {
			units: [unit({ id: 'u1' })],
			next_cursor: null
		};
		const api = {
			listUnits: vi
				.fn()
				.mockResolvedValueOnce({
					units: [unit({ id: 'u1' })],
					next_cursor: null
				})
				.mockResolvedValueOnce(reload),
			searchUnits: vi.fn(async () => [unit({ id: 'u-hit' })])
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		await store.search('x');
		expect(store.getState().searchQuery).toBe('x');

		await store.search('   ');
		expect(store.getState().searchQuery).toBe('');
		// load called 2x (initial + after clear), searchUnits only for 'x'.
		expect(api.listUnits).toHaveBeenCalledTimes(2);
		expect(api.searchUnits).toHaveBeenCalledTimes(1);
	});

	it('loadMore() no-ops while in search mode', async () => {
		const api = {
			listUnits: vi.fn(async () => ({
				units: [unit({ id: 'u1' })],
				next_cursor: '50'
			})),
			searchUnits: vi.fn(async () => [unit({ id: 'u-hit' })])
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		await store.search('x');
		api.listUnits.mockClear();
		await store.loadMore();
		expect(api.listUnits).not.toHaveBeenCalled();
	});

	// ---------------------------------------------------------------------
	// reset
	// ---------------------------------------------------------------------

	it('reset() clears state entirely', async () => {
		const api = {
			listUnits: vi.fn(async () => ({
				units: [unit({ id: 'u1' })],
				next_cursor: '50'
			})),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		store.reset();
		const s = store.getState();
		expect(s.units).toEqual([]);
		expect(s.cursor).toBeNull();
		expect(s.scoutId).toBeNull();
		expect(s.searchQuery).toBe('');
	});

	// ---------------------------------------------------------------------
	// errors
	// ---------------------------------------------------------------------

	it('load() records error message on failure', async () => {
		const api = {
			listUnits: vi.fn(async () => {
				throw new Error('down');
			}),
			searchUnits: vi.fn()
		};
		const store = createUnitsStore(api as unknown as UnitsApi);
		await store.load('s1');
		expect(store.getState().error).toBe('down');
		expect(store.getState().loading).toBe(false);
	});
});
