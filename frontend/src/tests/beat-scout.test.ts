import { describe, expect, it } from 'vitest';

import {
	buildBeatScoutScheduleDraft,
	buildBeatScoutSearchRequest
} from '$lib/components/news/beat-scout';
import type { GeocodedLocation } from '$lib/types';

const london: GeocodedLocation = {
	displayName: 'London, United Kingdom',
	city: 'London',
	country: 'GB',
	locationType: 'city'
};

describe('beat scout helpers', () => {
	it('builds a beat-mode preview request with criteria only', () => {
		expect(
			buildBeatScoutSearchRequest({
				mode: 'beat',
				sourceMode: 'reliable',
				topicInput: 'housing policy',
				selectedLocation: null,
				excludedDomains: [],
				prioritySources: []
			})
		).toEqual({
			criteria: 'housing policy'
		});
	});

	it('builds a beat-mode preview request with optional location', () => {
		expect(
			buildBeatScoutSearchRequest({
				mode: 'beat',
				sourceMode: 'reliable',
				topicInput: 'housing policy',
				selectedLocation: london,
				excludedDomains: ['example.com'],
				prioritySources: ['https://cityhall.example.com']
			})
		).toEqual({
			location: london,
			criteria: 'housing policy',
			excludedDomains: ['example.com'],
			prioritySources: ['https://cityhall.example.com']
		});
	});

	it('omits criteria for niche location searches', () => {
		expect(
			buildBeatScoutSearchRequest({
				mode: 'location',
				sourceMode: 'niche',
				topicInput: 'housing policy',
				selectedLocation: london,
				excludedDomains: [],
				prioritySources: []
			})
		).toEqual({
			location: london
		});
	});

	it('builds the schedule draft with optional location preserved', () => {
		expect(buildBeatScoutScheduleDraft(london, ' housing policy ')).toEqual({
			location: london,
			criteria: 'housing policy'
		});
	});
});
