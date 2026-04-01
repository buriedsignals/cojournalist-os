/**
 * HTML sanitization utilities for safely rendering user/AI-generated content.
 * Uses DOMPurify to prevent XSS attacks.
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize raw HTML content (not markdown).
 * Use this for HTML from external APIs.
 *
 * @param html - Raw HTML string to sanitize
 * @returns Sanitized HTML string safe for use with {@html}
 */
export function safeHtml(html: string): string {
	if (!html) return '';

	return DOMPurify.sanitize(html, {
		// More permissive for rich HTML content (charts, embeds, etc.)
		ADD_TAGS: ['svg', 'path', 'g', 'rect', 'circle', 'line', 'text', 'tspan'],
		ADD_ATTR: ['viewBox', 'd', 'fill', 'stroke', 'transform', 'width', 'height', 'x', 'y', 'href', 'target', 'rel'],
		// Block dangerous attributes
		FORBID_ATTR: ['onclick', 'onerror', 'onload', 'onmouseover', 'onfocus', 'onblur'],
		// Allow data URIs for SVG images only
		ALLOW_DATA_ATTR: false,
		// Block unknown protocols (javascript:, vbscript:, etc.)
		ALLOW_UNKNOWN_PROTOCOLS: false
	});
}
