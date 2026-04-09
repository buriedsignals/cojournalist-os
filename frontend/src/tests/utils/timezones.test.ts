import { describe, it, expect } from 'vitest';
import {
	normalizeTimezone,
	formatTz,
	getTimezoneOptions,
	POPULAR_TIMEZONES
} from '$lib/utils/timezones';

describe('normalizeTimezone', () => {
	it('maps deprecated Americas names', () => {
		expect(normalizeTimezone('America/Buenos_Aires')).toBe('America/Argentina/Buenos_Aires');
		expect(normalizeTimezone('America/Indianapolis')).toBe('America/Indiana/Indianapolis');
		expect(normalizeTimezone('America/Louisville')).toBe('America/Kentucky/Louisville');
	});

	it('maps deprecated Asia names', () => {
		expect(normalizeTimezone('Asia/Calcutta')).toBe('Asia/Kolkata');
		expect(normalizeTimezone('Asia/Saigon')).toBe('Asia/Ho_Chi_Minh');
	});

	it('maps deprecated Europe names', () => {
		expect(normalizeTimezone('Europe/Kiev')).toBe('Europe/Kyiv');
	});

	it('passes through canonical names', () => {
		expect(normalizeTimezone('America/New_York')).toBe('America/New_York');
		expect(normalizeTimezone('Asia/Kolkata')).toBe('Asia/Kolkata');
		expect(normalizeTimezone('UTC')).toBe('UTC');
	});

	it('passes through unknown names', () => {
		expect(normalizeTimezone('Mars/Olympus_Mons')).toBe('Mars/Olympus_Mons');
	});
});

describe('formatTz', () => {
	it('replaces underscores with spaces', () => {
		expect(formatTz('America/New_York')).toBe('America/New York');
		expect(formatTz('America/Indiana/Indianapolis')).toBe('America/Indiana/Indianapolis');
	});
});

describe('getTimezoneOptions', () => {
	it('returns popular timezones when no current timezone', () => {
		expect(getTimezoneOptions(null)).toEqual(POPULAR_TIMEZONES);
		expect(getTimezoneOptions(undefined)).toEqual(POPULAR_TIMEZONES);
	});

	it('does not duplicate a timezone already in popular list', () => {
		const result = getTimezoneOptions('America/New_York');
		const count = result.filter((tz) => tz === 'America/New_York').length;
		expect(count).toBe(1);
	});

	it('prepends a timezone not in popular list', () => {
		const result = getTimezoneOptions('Pacific/Auckland');
		expect(result[0]).toBe('Pacific/Auckland');
		expect(result.length).toBe(POPULAR_TIMEZONES.length + 1);
	});

	it('normalizes deprecated timezone and checks against popular list', () => {
		// Asia/Calcutta normalizes to Asia/Kolkata which IS in POPULAR_TIMEZONES
		const result = getTimezoneOptions('Asia/Calcutta');
		expect(result).not.toContain('Asia/Calcutta');
		expect(result).toContain('Asia/Kolkata');
		expect(result.length).toBe(POPULAR_TIMEZONES.length);
	});

	it('normalizes deprecated timezone not in popular list and prepends', () => {
		// America/Indianapolis normalizes to America/Indiana/Indianapolis — NOT in popular list
		const result = getTimezoneOptions('America/Indianapolis');
		expect(result[0]).toBe('America/Indiana/Indianapolis');
		expect(result).not.toContain('America/Indianapolis');
	});
});
