import { describe, expect, it } from 'vitest';
import {
	DEMO_SCOUTS,
	DEMO_UNITS,
	isDemoScout,
	isDemoUnit,
	isDemoWorkspace,
	shouldSeedDemoWorkspace,
	shouldRetireDemoWorkspace,
	shouldUseLocalDemoUnits
} from '$lib/demo/seed';

describe('demo seed helpers', () => {
	it('marks all seeded scouts as demo', () => {
		expect(DEMO_SCOUTS.every((scout) => scout.is_demo === true)).toBe(true);
		expect(DEMO_SCOUTS.every((scout) => isDemoScout(scout))).toBe(true);
	});

	it('recognizes backend onboarding demo scouts and units', () => {
		expect(isDemoScout({ id: 'onboarding-demo', name: 'Anything' })).toBe(true);
		expect(isDemoUnit({ id: 'unit-1', scout_id: 'onboarding-demo' })).toBe(true);
	});

	it('marks all seeded units as demo', () => {
		expect(DEMO_UNITS.every((unit) => unit.is_demo === true)).toBe(true);
		expect(DEMO_UNITS.every((unit) => isDemoUnit(unit))).toBe(true);
	});

	it('recognizes a full seeded workspace as demo', () => {
		expect(isDemoWorkspace(DEMO_SCOUTS)).toBe(true);
		expect(shouldSeedDemoWorkspace([])).toBe(true);
		expect(shouldRetireDemoWorkspace([{ id: 'real-1', name: 'Real scout' }])).toBe(true);
	});

	it('keeps demo inbox search local when current units are all demo units', () => {
		expect(
			shouldUseLocalDemoUnits({
				scopeScoutId: null,
				units: DEMO_UNITS
			})
		).toBe(true);
	});
});
