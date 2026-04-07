/**
 * Domain Parsing Utilities -- clean and normalize user-entered domain lists.
 *
 * USED BY: SmartScoutView.svelte, tests/utils/domains.test.ts
 * DEPENDS ON: (none)
 */

/**
 * Parse a newline-separated string of domains into a clean array.
 * Strips protocols, www prefixes, and paths. Filters out invalid entries.
 */
export function parseExcludedDomains(text: string): string[] {
	return text
		.split('\n')
		.map(d => d.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, ''))
		.filter(d => d.length > 0 && d.includes('.'));
}

/**
 * Parse a newline-separated string of priority source domains into a clean array.
 * Strips protocols, www prefixes, and paths. Filters out invalid entries.
 */
export function parsePrioritySources(text: string): string[] {
	return text
		.split('\n')
		.map(d => d.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, ''))
		.filter(d => d.length > 0 && d.includes('.'));
}
