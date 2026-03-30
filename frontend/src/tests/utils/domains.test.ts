import { describe, it, expect } from 'vitest';
import { parseExcludedDomains } from '$lib/utils/domains';

describe('parseExcludedDomains', () => {
	it('parses simple domain list', () => {
		expect(parseExcludedDomains('example.com\nnews.org')).toEqual(['example.com', 'news.org']);
	});

	it('strips protocols and www', () => {
		expect(parseExcludedDomains('https://www.example.com\nhttp://news.org')).toEqual([
			'example.com',
			'news.org'
		]);
	});

	it('strips paths', () => {
		expect(parseExcludedDomains('example.com/some/path\nnews.org/')).toEqual([
			'example.com',
			'news.org'
		]);
	});

	it('filters empty lines and whitespace', () => {
		expect(parseExcludedDomains('example.com\n\n  \nnews.org\n')).toEqual([
			'example.com',
			'news.org'
		]);
	});

	it('filters entries without a dot', () => {
		expect(parseExcludedDomains('example.com\ncom\njusttext\nnews.org')).toEqual([
			'example.com',
			'news.org'
		]);
	});

	it('returns empty array for empty input', () => {
		expect(parseExcludedDomains('')).toEqual([]);
	});

	it('trims whitespace from each line', () => {
		expect(parseExcludedDomains('  example.com  \n  news.org  ')).toEqual([
			'example.com',
			'news.org'
		]);
	});
});
