/**
 * Sidebar Nav Store -- active view, scout filter, and collapsed state.
 *
 * USED BY: FeedView.svelte, PageScoutView.svelte, SmartScoutView.svelte,
 *          UnifiedSidebar.svelte, GuidedTourController.svelte, +page.svelte
 * DEPENDS ON: (none)
 *
 * State: { activeView: SidebarView, scoutFilter: ScoutFilter, collapsed: boolean }
 * Side effects: reads/writes localStorage key 'sidebar_collapsed'
 */
import { writable } from 'svelte/store';

export type SidebarView =
	| 'scouts'
	| 'pulse'
	| 'page-scout'
	| 'social-scout'
	| 'civic-scout'
	| 'extract'
	| 'feed'
	| 'api';

type ScoutFilter = 'all' | 'web' | 'pulse' | 'social' | 'civic';

const COLLAPSED_KEY = 'sidebar_collapsed';

function loadCollapsed(): boolean {
	if (typeof window === 'undefined') return false;
	return localStorage.getItem(COLLAPSED_KEY) === 'true';
}

function saveCollapsed(collapsed: boolean) {
	if (typeof window === 'undefined') return;
	localStorage.setItem(COLLAPSED_KEY, String(collapsed));
}

interface SidebarNavState {
	activeView: SidebarView;
	scoutFilter: ScoutFilter;
	collapsed: boolean;
}

function createSidebarNavStore() {
	const { subscribe, set, update } = writable<SidebarNavState>({
		activeView: 'scouts',
		scoutFilter: 'all',
		collapsed: loadCollapsed()
	});

	return {
		subscribe,
		setView: (view: SidebarView) => update(state => ({ ...state, activeView: view })),
		setScoutFilter: (filter: ScoutFilter) => update(state => ({ ...state, scoutFilter: filter })),
		toggleCollapsed: () => update(state => {
			const next = !state.collapsed;
			saveCollapsed(next);
			return { ...state, collapsed: next };
		}),
		reset: () => set({ activeView: 'scouts', scoutFilter: 'all', collapsed: loadCollapsed() })
	};
}

export const sidebarNav = createSidebarNavStore();
