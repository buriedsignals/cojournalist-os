/**
 * Export Formatting Utilities -- HTML rendering for article draft display.
 *
 * USED BY: ExportSlideOver.svelte
 * DEPENDS ON: (none)
 *
 * Converts markdown bold to <strong> tags and [domain.com] citation
 * brackets to clickable hyperlinks using a source URL map.
 * All output is XSS-safe (HTML entities are escaped).
 */

/**
 * Convert **bold** markdown to <strong> tags (HTML-safe).
 */
export function boldify(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

/**
 * Convert [domain.com] citations and full markdown [text](url) links to hyperlinks.
 *
 * Handles two formats:
 * 1. Full markdown links: [link text](https://url) → <a href="url">link text</a>
 * 2. Citation brackets: [domain.com] → superscript numbered reference matching source list
 */
export function linkifySources(text: string, sources: { url: string; domain?: string }[]): string {
	// Build domain → {url, index} map (1-based index matching the source list)
	const sourceMap = new Map<string, { url: string; index: number }>();
	for (let i = 0; i < sources.length; i++) {
		const s = sources[i];
		const domain = s.domain || new URL(s.url).hostname.replace('www.', '');
		if (!sourceMap.has(domain)) sourceMap.set(domain, { url: s.url, index: i + 1 });
	}

	const escapeAttr = (str: string) =>
		str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

	// Pass 1: full markdown links [text](url) — text already HTML-escaped via boldify
	const withLinks = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (_, linkText, url) => {
		const safeUrl = escapeAttr(url);
		return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="citation-link">${linkText}</a>`;
	});

	// Pass 2: bare citation brackets [domain.com] → superscript numbered reference
	return withLinks.replace(/\[([^\]]+)\]/g, (match, domain) => {
		const normalizedDomain = domain.replace(/^www\./, '');
		const entry = sourceMap.get(domain) || sourceMap.get(normalizedDomain);
		if (entry && entry.url.startsWith('http')) {
			const safeUrl = escapeAttr(entry.url);
			return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="citation-ref"><sup>${entry.index}</sup></a>`;
		}
		return match;
	});
}
