/**
 * Tests for UnitDrawer tab-state helpers.
 * Pure logic — tab transitions.
 */
import { describe, it, expect } from 'vitest';
import {
	DRAWER_TABS,
	DEFAULT_TAB,
	isDrawerTab,
	nextTab,
	prevTab,
	resolveTab
} from '$lib/utils/workspace-tabs';

describe('DRAWER_TABS', () => {
	it('lists the three known tabs in canonical order', () => {
		expect(DRAWER_TABS).toEqual(['content', 'entities', 'reflections']);
	});

	it('DEFAULT_TAB is content', () => {
		expect(DEFAULT_TAB).toBe('content');
	});
});

describe('isDrawerTab', () => {
	it.each(DRAWER_TABS)('accepts %s', (tab) => {
		expect(isDrawerTab(tab)).toBe(true);
	});

	it('rejects unknown strings and non-string values', () => {
		expect(isDrawerTab('promote')).toBe(false);
		expect(isDrawerTab('')).toBe(false);
		expect(isDrawerTab(null)).toBe(false);
		expect(isDrawerTab(undefined)).toBe(false);
		expect(isDrawerTab(0)).toBe(false);
		expect(isDrawerTab({ tab: 'content' })).toBe(false);
	});
});

describe('nextTab / prevTab', () => {
	it('advances forward through the list and wraps', () => {
		expect(nextTab('content')).toBe('entities');
		expect(nextTab('entities')).toBe('reflections');
		expect(nextTab('reflections')).toBe('content');
	});

	it('advances backward through the list and wraps', () => {
		expect(prevTab('content')).toBe('reflections');
		expect(prevTab('entities')).toBe('content');
		expect(prevTab('reflections')).toBe('entities');
	});
});

describe('resolveTab', () => {
	it('returns the known tab unchanged', () => {
		expect(resolveTab('entities')).toBe('entities');
	});

	it('falls back to DEFAULT_TAB on unknown values', () => {
		expect(resolveTab('unknown')).toBe(DEFAULT_TAB);
		expect(resolveTab(null)).toBe(DEFAULT_TAB);
		expect(resolveTab(undefined)).toBe(DEFAULT_TAB);
	});
});
