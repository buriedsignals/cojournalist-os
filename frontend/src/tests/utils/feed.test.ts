/**
 * Tests for FeedView utility functions.
 * Pure logic tests — no Svelte rendering needed.
 */
import { describe, it, expect } from 'vitest';
import {
	parseLocationKey,
	deriveScoutNames,
	filterUnits,
	countByType,
	buildLocationName,
	canExport
} from '$lib/utils/feed';
import type { InformationUnit } from '$lib/api-client';

// ===========================================================================
// Fixtures
// ===========================================================================

function makeUnit(overrides: Partial<InformationUnit> = {}): InformationUnit {
	return {
		unit_id: 'u1',
		pk: 'pk',
		sk: 'sk',
		statement: 'Test statement',
		unit_type: 'fact',
		entities: [],
		source_url: 'https://example.com',
		source_domain: 'example.com',
		source_title: 'Example',
		scout_type: 'pulse',
		scout_id: 'scout-1',
		created_at: '2026-02-17',
		used_in_article: false,
		...overrides
	};
}

// ===========================================================================
// parseLocationKey
// ===========================================================================

describe('parseLocationKey', () => {
	it('full key: country#state#city', () => {
		const result = parseLocationKey('CH#Zürich#Winterthur');
		expect(result).toEqual({
			displayName: 'Winterthur, Zürich, CH',
			country: 'CH',
			state: 'Zürich',
			city: 'Winterthur'
		});
	});

	it('country only', () => {
		const result = parseLocationKey('FR#_#_');
		expect(result).toEqual({
			displayName: 'FR',
			country: 'FR',
			state: null,
			city: null
		});
	});

	it('country and state, no city', () => {
		const result = parseLocationKey('US#California#_');
		expect(result).toEqual({
			displayName: 'California, US',
			country: 'US',
			state: 'California',
			city: null
		});
	});

	it('country and city, no state', () => {
		const result = parseLocationKey('SG#_#Singapore');
		expect(result).toEqual({
			displayName: 'Singapore, SG',
			country: 'SG',
			state: null,
			city: 'Singapore'
		});
	});

	it('empty string falls back to key', () => {
		const result = parseLocationKey('');
		expect(result.displayName).toBe('');
	});

	it('simple string without separators', () => {
		const result = parseLocationKey('MyLocation');
		expect(result).toEqual({
			displayName: 'MyLocation',
			country: 'MyLocation',
			state: null,
			city: null
		});
	});
});

// ===========================================================================
// deriveScoutNames
// ===========================================================================

describe('deriveScoutNames', () => {
	it('returns empty for no units', () => {
		expect(deriveScoutNames([])).toEqual([]);
	});

	it('extracts unique scout IDs', () => {
		const units = [
			makeUnit({ scout_id: 'alpha' }),
			makeUnit({ scout_id: 'beta' }),
			makeUnit({ scout_id: 'alpha' }) // duplicate
		];
		const result = deriveScoutNames(units);
		expect(result).toHaveLength(2);
		expect(result.map((s) => s.id)).toEqual(['alpha', 'beta']);
	});

	it('filters out "UI Search" scout ID', () => {
		const units = [makeUnit({ scout_id: 'UI Search' }), makeUnit({ scout_id: 'real-scout' })];
		const result = deriveScoutNames(units);
		expect(result).toHaveLength(1);
		expect(result[0].id).toBe('real-scout');
	});

	it('sorts alphabetically', () => {
		const units = [
			makeUnit({ scout_id: 'zebra' }),
			makeUnit({ scout_id: 'apple' }),
			makeUnit({ scout_id: 'mango' })
		];
		const result = deriveScoutNames(units);
		expect(result.map((s) => s.id)).toEqual(['apple', 'mango', 'zebra']);
	});
});

// ===========================================================================
// filterUnits
// ===========================================================================

describe('filterUnits', () => {
	const units = [
		makeUnit({ unit_id: 'u1', scout_type: 'pulse', scout_id: 's1', used_in_article: false }),
		makeUnit({ unit_id: 'u2', scout_type: 'pulse', scout_id: 's2', used_in_article: false }),
		makeUnit({ unit_id: 'u3', scout_type: 'pulse', scout_id: 's1', used_in_article: true }),
		makeUnit({ unit_id: 'u4', scout_type: 'web', scout_id: 's3', used_in_article: false })
	];

	it('no filters returns all', () => {
		const result = filterUnits(units, {});
		expect(result).toHaveLength(4);
	});

	it('excludeUsed removes used units', () => {
		const result = filterUnits(units, { excludeUsed: true });
		expect(result).toHaveLength(3);
		expect(result.every((u) => !u.used_in_article)).toBe(true);
	});

	it('scoutTypeFilter "page-scout" returns only web units', () => {
		const result = filterUnits(units, { scoutTypeFilter: 'page-scout' });
		expect(result).toHaveLength(1);
		expect(result.every((u) => u.scout_type === 'web')).toBe(true);
	});

	it('scoutTypeFilter "smart-scout" returns pulse units', () => {
		const result = filterUnits(units, { scoutTypeFilter: 'smart-scout' });
		expect(result).toHaveLength(3);
		expect(result.every((u) => u.scout_type === 'pulse')).toBe(true);
	});

	it('scoutTypeFilter "all" returns everything', () => {
		const result = filterUnits(units, { scoutTypeFilter: 'all' });
		expect(result).toHaveLength(4);
	});

	it('selectedScoutId filters by scout', () => {
		const result = filterUnits(units, { selectedScoutId: 's1' });
		expect(result).toHaveLength(2);
		expect(result.every((u) => u.scout_id === 's1')).toBe(true);
	});

	it('combined filters stack', () => {
		const result = filterUnits(units, {
			scoutTypeFilter: 'smart-scout',
			excludeUsed: true,
			selectedScoutId: 's1'
		});
		expect(result).toHaveLength(1);
		expect(result[0].unit_id).toBe('u1');
	});
});

// ===========================================================================
// countByType
// ===========================================================================

describe('countByType', () => {
	it('empty units returns all zeros', () => {
		expect(countByType([])).toEqual({
			all: 0,
			'page-scout': 0,
			'smart-scout': 0
		});
	});

	it('counts only unused units', () => {
		const units = [
			makeUnit({ scout_type: 'pulse', used_in_article: false }),
			makeUnit({ scout_type: 'pulse', used_in_article: true }), // excluded
			makeUnit({ scout_type: 'pulse', used_in_article: false }),
			makeUnit({ scout_type: 'web', used_in_article: false })
		];
		const result = countByType(units);
		expect(result.all).toBe(3);
		expect(result['page-scout']).toBe(1);
		expect(result['smart-scout']).toBe(2);
	});
});

// ===========================================================================
// canExport
// ===========================================================================

describe('canExport', () => {
	it('returns true when units are selected (no filter active)', () => {
		expect(canExport(3)).toBe(true);
	});

	it('returns false when zero units selected', () => {
		expect(canExport(0)).toBe(false);
	});

	it('returns true with exactly one unit selected', () => {
		expect(canExport(1)).toBe(true);
	});
});

// ===========================================================================
// buildLocationName
// ===========================================================================

describe('buildLocationName', () => {
	it('uses parsed location when locationKey is set', () => {
		expect(buildLocationName('CH#Zürich#Winterthur', null)).toBe('Winterthur, Zürich, CH');
	});

	it('falls back to topic when no location', () => {
		expect(buildLocationName(null, 'Climate')).toBe('Climate');
	});

	it('falls back to "Global" when neither location nor topic', () => {
		expect(buildLocationName(null, null)).toBe('Global');
	});

	it('prefers location over topic when both set', () => {
		expect(buildLocationName('US#California#_', 'Climate')).toBe('California, US');
	});
});
