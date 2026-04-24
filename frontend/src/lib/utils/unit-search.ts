import type { Unit } from '$lib/types/workspace';

export type SearchMatchCategory = NonNullable<Unit['search_match']>['category'];
export type SearchMatch = NonNullable<Unit['search_match']>;

function formatSimilarity(similarity: number | null): string | null {
	if (typeof similarity !== 'number' || !Number.isFinite(similarity)) return null;
	return `${Math.round(similarity * 100)}%`;
}

export function searchMatchLabel(match: SearchMatch): string {
	switch (match.category) {
		case 'direct':
			return 'DIRECT MATCH';
		case 'related':
			return formatSimilarity(match.semantic_similarity)
				? `SEMANTIC MATCH ${formatSimilarity(match.semantic_similarity)}`
				: 'SEMANTIC MATCH';
		case 'loose':
			return 'LOW CONFIDENCE';
	}
}

export function searchMatchClass(category: SearchMatchCategory): string {
	return category;
}
