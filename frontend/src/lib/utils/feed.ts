/**
 * Feed Utilities -- pure functions for information unit filtering and display.
 *
 * USED BY: FeedView.svelte, tests/utils/feed.test.ts
 * DEPENDS ON: $lib/api-client (InformationUnit type)
 *
 * Extracted from FeedView for testability. Handles location key parsing,
 * scout name derivation, unit filtering, export readiness checks, and
 * type-based counting.
 */

import type { InformationUnit } from '$lib/api-client';

/**
 * Parse a compound location key (e.g. "CH#Zürich#Winterthur") into components.
 * The key format is: country#state#city, with "_" representing null.
 */
export function parseLocationKey(key: string): {
	displayName: string;
	country: string;
	state: string | null;
	city: string | null;
} {
	const parts = key.split('#');
	const country = parts[0] || '';
	const state = parts[1] && parts[1] !== '_' ? parts[1] : null;
	const city = parts[2] && parts[2] !== '_' ? parts[2] : null;
	const displayParts: string[] = [];
	if (city) displayParts.push(city);
	if (state) displayParts.push(state);
	if (country) displayParts.push(country);
	return { displayName: displayParts.join(', ') || key, country, state, city };
}

/**
 * Derive unique scout names from a list of information units.
 * Filters out "UI Search" scout IDs.
 */
export function deriveScoutNames(units: InformationUnit[]): { id: string; label: string }[] {
	const seen = new Map<string, string>();
	for (const u of units) {
		if (u.scout_id && u.scout_id !== 'UI Search' && !seen.has(u.scout_id)) {
			seen.set(u.scout_id, u.scout_id);
		}
	}
	return [...seen.entries()]
		.map(([id, label]) => ({ id, label }))
		.sort((a, b) => a.label.localeCompare(b.label));
}

/**
 * Filter units by type, scout, and used status.
 */
export function filterUnits(
	units: InformationUnit[],
	opts: {
		scoutTypeFilter?: string;
		selectedScoutId?: string | null;
		excludeUsed?: boolean;
	}
): InformationUnit[] {
	return units
		.filter((u) => !opts.excludeUsed || !u.used_in_article)
		.filter((u) => {
			if (!opts.scoutTypeFilter || opts.scoutTypeFilter === 'all') return true;
			if (opts.scoutTypeFilter === 'page-scout') return u.scout_type === 'web';
			if (opts.scoutTypeFilter === 'smart-scout') return u.scout_type === 'pulse';
			return u.scout_type === opts.scoutTypeFilter;
		})
		.filter((u) => !opts.selectedScoutId || u.scout_id === opts.selectedScoutId);
}

/**
 * Determine the location name for export generation.
 * Falls back to topic or 'Global' when no location filter is active.
 */
export function buildLocationName(
	selectedLocationKey: string | null,
	selectedTopic: string | null
): string {
	if (selectedLocationKey) {
		return parseLocationKey(selectedLocationKey).displayName;
	}
	return selectedTopic || 'Global';
}

/**
 * Check whether export generation should proceed.
 * Returns true when at least one unit is selected.
 */
export function canExport(selectedUnitCount: number): boolean {
	return selectedUnitCount > 0;
}

/**
 * Count units per scout type (excluding used units).
 */
export function countByType(units: InformationUnit[]): Record<string, number> {
	const unused = units.filter((u) => !u.used_in_article);
	return {
		all: unused.length,
		'page-scout': unused.filter((u) => u.scout_type === 'web').length,
		'smart-scout': unused.filter((u) => u.scout_type === 'pulse').length
	};
}
