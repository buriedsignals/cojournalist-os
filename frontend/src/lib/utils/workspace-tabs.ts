/**
 * Tab-state helpers extracted from `UnitDrawer.svelte`.
 * Three-way tab state machine (content / entities / reflections) + next/prev
 * transitions used by keyboard shortcuts.
 *
 * Tested in src/tests/utils/workspace-tabs.test.ts.
 */

export const DRAWER_TABS = ['content', 'entities', 'reflections'] as const;
export type DrawerTab = (typeof DRAWER_TABS)[number];

export const DEFAULT_TAB: DrawerTab = 'content';

export function isDrawerTab(value: unknown): value is DrawerTab {
	return typeof value === 'string' && (DRAWER_TABS as readonly string[]).includes(value);
}

export function nextTab(current: DrawerTab): DrawerTab {
	const idx = DRAWER_TABS.indexOf(current);
	return DRAWER_TABS[(idx + 1) % DRAWER_TABS.length];
}

export function prevTab(current: DrawerTab): DrawerTab {
	const idx = DRAWER_TABS.indexOf(current);
	return DRAWER_TABS[(idx - 1 + DRAWER_TABS.length) % DRAWER_TABS.length];
}

/**
 * Resolve a requested tab to a valid DrawerTab, falling back to DEFAULT_TAB
 * if the input is unknown. Used on URL hash sync or external triggers.
 */
export function resolveTab(requested: unknown): DrawerTab {
	return isDrawerTab(requested) ? requested : DEFAULT_TAB;
}
