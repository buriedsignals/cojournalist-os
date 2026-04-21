/**
 * Debounce helper extracted from `Inbox.svelte` search input.
 * Pure — tested in src/tests/utils/workspace-debounce.test.ts.
 *
 * Usage:
 *   const debouncedSearch = debounce((q: string) => unitsStore.search(q), 300);
 *   on input: debouncedSearch(value);
 */

export interface Debounced<Args extends unknown[]> {
	(...args: Args): void;
	cancel(): void;
	flush(): void;
}

export function debounce<Args extends unknown[]>(
	fn: (...args: Args) => void,
	waitMs: number
): Debounced<Args> {
	let timer: ReturnType<typeof setTimeout> | null = null;
	let lastArgs: Args | null = null;

	const debounced = ((...args: Args) => {
		lastArgs = args;
		if (timer !== null) clearTimeout(timer);
		timer = setTimeout(() => {
			timer = null;
			if (lastArgs) fn(...lastArgs);
			lastArgs = null;
		}, waitMs);
	}) as Debounced<Args>;

	debounced.cancel = () => {
		if (timer !== null) clearTimeout(timer);
		timer = null;
		lastArgs = null;
	};

	debounced.flush = () => {
		if (timer !== null) {
			clearTimeout(timer);
			timer = null;
			if (lastArgs) fn(...lastArgs);
			lastArgs = null;
		}
	};

	return debounced;
}
