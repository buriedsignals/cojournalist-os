import { describe, it, expect } from 'vitest';
import { SCOUT_COSTS, getScoutCost } from '$lib/utils/scouts';

describe('Civic Scout costs', () => {
	it('has civic cost of 20', () => {
		expect(SCOUT_COSTS.civic).toBe(20);
	});
	it('getScoutCost returns 20 for civic', () => {
		expect(getScoutCost('civic')).toBe(20);
	});
});
