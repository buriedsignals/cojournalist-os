/**
 * Tests for workspace pagination helpers.
 * Pure logic — sentinel/cursor decisions.
 */
import { describe, it, expect } from 'vitest';
import { shouldLoadMore, mergePage, resetPagination } from '$lib/utils/workspace-pagination';

describe('shouldLoadMore', () => {
	it('returns true when the sentinel intersects and more pages exist', () => {
		expect(
			shouldLoadMore({ isIntersecting: true, hasMore: true, loading: false, loadingMore: false })
		).toBe(true);
	});

	it('returns false when not intersecting', () => {
		expect(
			shouldLoadMore({ isIntersecting: false, hasMore: true, loading: false, loadingMore: false })
		).toBe(false);
	});

	it('returns false when hasMore is false', () => {
		expect(
			shouldLoadMore({ isIntersecting: true, hasMore: false, loading: false, loadingMore: false })
		).toBe(false);
	});

	it('returns false while loading is in flight', () => {
		expect(
			shouldLoadMore({ isIntersecting: true, hasMore: true, loading: true, loadingMore: false })
		).toBe(false);
		expect(
			shouldLoadMore({ isIntersecting: true, hasMore: true, loading: false, loadingMore: true })
		).toBe(false);
	});
});

describe('mergePage', () => {
	it('appends new items and updates cursor + hasMore', () => {
		const prev = { items: [{ id: 'a' }, { id: 'b' }], cursor: '2', hasMore: true };
		const page = { items: [{ id: 'c' }, { id: 'd' }], next_cursor: '4' };
		const next = mergePage(prev, page);
		expect(next.items.map((i) => i.id)).toEqual(['a', 'b', 'c', 'd']);
		expect(next.cursor).toBe('4');
		expect(next.hasMore).toBe(true);
	});

	it('dedupes by id so polling reloads do not double-insert', () => {
		const prev = { items: [{ id: 'a' }, { id: 'b' }], cursor: '2', hasMore: true };
		const page = { items: [{ id: 'b' }, { id: 'c' }], next_cursor: '4' };
		const next = mergePage(prev, page);
		expect(next.items.map((i) => i.id)).toEqual(['a', 'b', 'c']);
	});

	it('next_cursor=null sets hasMore false', () => {
		const prev = { items: [{ id: 'a' }], cursor: '1', hasMore: true };
		const page = { items: [{ id: 'b' }], next_cursor: null };
		const next = mergePage(prev, page);
		expect(next.hasMore).toBe(false);
		expect(next.cursor).toBeNull();
	});
});

describe('resetPagination', () => {
	it('returns a clean initial state', () => {
		const state = resetPagination<{ id: string }>();
		expect(state).toEqual({ items: [], cursor: null, hasMore: true });
	});
});
