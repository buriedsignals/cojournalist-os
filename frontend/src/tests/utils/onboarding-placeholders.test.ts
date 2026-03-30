/**
 * Tests for onboarding placeholder data.
 * Validates structure, completeness, and type coverage of the static demo data.
 */
import { describe, it, expect } from 'vitest';
import {
	PLACEHOLDER_SCOUTS,
	PLACEHOLDER_UNITS
} from '$lib/data/onboarding-placeholders';

// ===========================================================================
// PLACEHOLDER_SCOUTS
// ===========================================================================

describe('PLACEHOLDER_SCOUTS', () => {
	it('contains exactly 4 scouts', () => {
		expect(PLACEHOLDER_SCOUTS).toHaveLength(4);
	});

	it('covers both scout types', () => {
		const types = PLACEHOLDER_SCOUTS.map((s) => s.scout_type);
		expect(types).toContain('web');
		expect(types).toContain('pulse');
	});

	it('web scout has criteria_status true', () => {
		const web = PLACEHOLDER_SCOUTS.find((s) => s.scout_type === 'web');
		expect(web).toBeDefined();
		expect(web!.last_run).not.toBeNull();
		expect(web!.last_run!.criteria_status).toBe(true);
	});

	it('pulse scout has criteria_status true', () => {
		const pulse = PLACEHOLDER_SCOUTS.find((s) => s.scout_type === 'pulse');
		expect(pulse).toBeDefined();
		expect(pulse!.last_run).not.toBeNull();
		expect(pulse!.last_run!.criteria_status).toBe(true);
	});

	it('pulse scout with criteria has null last_run (awaiting first run)', () => {
		const withCriteria = PLACEHOLDER_SCOUTS.find((s) => s.criteria && s.scout_type === 'pulse');
		expect(withCriteria).toBeDefined();
		expect(withCriteria!.last_run).toBeNull();
	});

	it('every scout has a scraper_name and regularity', () => {
		for (const scout of PLACEHOLDER_SCOUTS) {
			expect(scout.scraper_name).toBeTruthy();
			expect(scout.regularity).toBeTruthy();
		}
	});
});

// ===========================================================================
// PLACEHOLDER_UNITS
// ===========================================================================

describe('PLACEHOLDER_UNITS', () => {
	it('contains exactly 4 units', () => {
		expect(PLACEHOLDER_UNITS).toHaveLength(4);
	});

	it('every unit has all required fields', () => {
		const requiredKeys = [
			'unit_id',
			'statement',
			'unit_type',
			'entities',
			'source_url',
			'source_domain',
			'source_title',
			'scout_type',
			'created_at'
		];

		for (const unit of PLACEHOLDER_UNITS) {
			for (const key of requiredKeys) {
				expect(unit).toHaveProperty(key);
				expect((unit as unknown as Record<string, unknown>)[key]).toBeDefined();
			}
		}
	});

	it('includes units covering Zurich, Tokyo, Austin, and Seoul', () => {
		const statements = PLACEHOLDER_UNITS.map((u) => u.statement);
		expect(statements.some((s) => s.includes('Zurich'))).toBe(true);
		expect(statements.some((s) => s.includes('Tokyo'))).toBe(true);
		expect(statements.some((s) => s.includes('Austin'))).toBe(true);
		expect(statements.some((s) => s.includes('Seoul'))).toBe(true);
	});

	it('every unit_id is unique', () => {
		const ids = PLACEHOLDER_UNITS.map((u) => u.unit_id);
		expect(new Set(ids).size).toBe(ids.length);
	});
});

