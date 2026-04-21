import { describe, it, expect } from 'vitest';
import { SCOUT_COSTS, getScoutCost } from '$lib/utils/scouts';

describe('Civic Scout costs', () => {
	it('has civic cost of 10', () => {
		expect(SCOUT_COSTS.civic).toBe(10);
	});
	it('getScoutCost returns 10 for civic', () => {
		expect(getScoutCost('civic')).toBe(10);
	});
});
