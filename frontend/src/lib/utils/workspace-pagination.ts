/**
 * Pagination helpers extracted from `Inbox.svelte` infinite-scroll sentinel.
 * Pure logic only — IntersectionObserver stays in the component.
 *
 * Tested in src/tests/utils/workspace-pagination.test.ts.
 */

export interface PaginationState<T> {
	items: T[];
	cursor: string | null;
	hasMore: boolean;
}

/**
 * Determine whether a new page of results should be loaded given current
 * visibility + loading flags. Component wires an IntersectionObserver that
 * calls this on entries[0].isIntersecting to decide whether to invoke
 * `loadMore()`.
 */
export function shouldLoadMore(args: {
	isIntersecting: boolean;
	hasMore: boolean;
	loading: boolean;
	loadingMore: boolean;
}): boolean {
	return args.isIntersecting && args.hasMore && !args.loading && !args.loadingMore;
}

/**
 * Merge a new page into existing state. Dedupes by identity key (default: `id`).
 * Updates cursor + hasMore from the server response.
 */
export function mergePage<T extends { id: string }>(
	prev: PaginationState<T>,
	page: { items: T[]; next_cursor: string | null }
): PaginationState<T> {
	const seen = new Set(prev.items.map((item) => item.id));
	const additions = page.items.filter((item) => !seen.has(item.id));
	return {
		items: [...prev.items, ...additions],
		cursor: page.next_cursor,
		hasMore: page.next_cursor !== null
	};
}

/**
 * Reset pagination state — called on scout change or search query change.
 */
export function resetPagination<T>(): PaginationState<T> {
	return {
		items: [],
		cursor: null,
		hasMore: true
	};
}
