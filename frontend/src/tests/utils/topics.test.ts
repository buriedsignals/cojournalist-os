import { describe, expect, it } from 'vitest';
import { collectTopicCounts, parseTopicTags, topicMatches } from '$lib/utils/topics';

describe('topic tag utilities', () => {
	it('parses comma-separated scout topics as independent tags', () => {
		expect(parseTopicTags('housing, real-estate, Pontresina')).toEqual([
			'housing',
			'real-estate',
			'Pontresina'
		]);
	});

	it('trims, collapses whitespace, and deduplicates case-insensitively', () => {
		expect(parseTopicTags(' housing , Housing, real   estate, ')).toEqual([
			'housing',
			'real estate'
		]);
	});

	it('counts each topic independently across scouts', () => {
		expect(
			collectTopicCounts([
				{ topic: 'housing, real estate, Pontresina' },
				{ topic: 'real estate, housing, Zuoz' },
				{ topic: 'Hyrox' }
			])
		).toEqual([
			{ topic: 'housing', count: 2 },
			{ topic: 'Hyrox', count: 1 },
			{ topic: 'Pontresina', count: 1 },
			{ topic: 'real estate', count: 2 },
			{ topic: 'Zuoz', count: 1 }
		]);
	});

	it('matches a selected topic against any tag on a scout', () => {
		expect(topicMatches('real estate, housing, Pontresina', 'housing')).toBe(true);
		expect(topicMatches('real estate, housing, Pontresina', 'Pontresina')).toBe(true);
		expect(topicMatches('real estate, housing, Pontresina', 'Samedan')).toBe(false);
		expect(topicMatches('real estate, housing, Pontresina', '')).toBe(true);
	});
});
