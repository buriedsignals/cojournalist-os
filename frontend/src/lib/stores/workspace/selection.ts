/**
 * Workspace selection store — which scout + unit are currently highlighted.
 *
 * Synchronous only (no async, no fetches). Separate from the drawer store so
 * drawer exit-animations don't race with selection changes.
 *
 * Consumed by: `components/workspace/ScoutList.svelte`, `Inbox.svelte`,
 *              `UnitDrawer.svelte` (PR 2).
 */
import { writable, type Writable } from 'svelte/store';

export interface SelectionState {
	scoutId: string | null;
	unitId: string | null;
}

const initialState: SelectionState = {
	scoutId: null,
	unitId: null
};

function createSelectionStore() {
	const { subscribe, set, update }: Writable<SelectionState> = writable({ ...initialState });

	return {
		subscribe,

		/**
		 * Select a scout. Clears the current unit selection — units live under
		 * a scout scope so the previous unit is no longer relevant.
		 */
		selectScout(id: string | null): void {
			update((s) => ({ ...s, scoutId: id, unitId: null }));
		},

		/**
		 * Select (or clear) the focused unit. Does NOT toggle the drawer — the
		 * caller is responsible (usually via `drawerStore.open()`), which lets
		 * callers animate the drawer open before changing the unit id.
		 */
		selectUnit(id: string | null): void {
			update((s) => ({ ...s, unitId: id }));
		},

		/**
		 * Reset both ids to null.
		 */
		clear(): void {
			set({ ...initialState });
		},

		/**
		 * Synchronously read the current state. Test-only.
		 */
		getState(): SelectionState {
			let snapshot: SelectionState = { ...initialState };
			const unsub = subscribe((s) => {
				snapshot = s;
			});
			unsub();
			return snapshot;
		}
	};
}

export const selectionStore = createSelectionStore();
