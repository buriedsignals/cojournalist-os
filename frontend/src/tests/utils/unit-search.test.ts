import { describe, expect, it } from 'vitest';
import {
	searchMatchClass,
	searchMatchLabel
} from '$lib/utils/unit-search';

describe('unit search UI helpers', () => {
	it('maps each category to the expected label and class', () => {
		expect(
			searchMatchLabel({
				category: 'direct',
				reason: 'Direct text match in statement.',
				keyword_fields: ['statement'],
				semantic_similarity: null,
				below_interest_threshold: false
			})
		).toBe('DIRECT MATCH');
		expect(searchMatchClass('direct')).toBe('direct');

		expect(
			searchMatchLabel({
				category: 'related',
				reason: 'Semantic match.',
				keyword_fields: [],
				semantic_similarity: 0.82,
				below_interest_threshold: false
			})
		).toBe('SEMANTIC MATCH 82%');
		expect(searchMatchClass('related')).toBe('related');

		expect(
			searchMatchLabel({
				category: 'loose',
				reason: 'Low-confidence semantic match shown for recall.',
				keyword_fields: [],
				semantic_similarity: 0.74,
				below_interest_threshold: true
			})
		).toBe('LOW CONFIDENCE');
		expect(searchMatchClass('loose')).toBe('loose');
	});
});
