export interface TopicCount {
	topic: string;
	count: number;
}

export function parseTopicTags(raw: string | null | undefined): string[] {
	if (!raw) return [];

	const seen = new Set<string>();
	const tags: string[] = [];

	for (const part of raw.split(',')) {
		const tag = part.trim().replace(/\s+/g, ' ');
		const key = tag.toLocaleLowerCase();
		if (!tag || seen.has(key)) continue;
		seen.add(key);
		tags.push(tag);
	}

	return tags;
}

export function topicMatches(raw: string | null | undefined, selected: string | null | undefined): boolean {
	const normalized = (selected ?? '').trim().toLocaleLowerCase();
	if (!normalized) return true;
	return parseTopicTags(raw).some((tag) => tag.toLocaleLowerCase() === normalized);
}

export function collectTopicCounts(scouts: Array<{ topic?: string | null }>): TopicCount[] {
	const labels = new Map<string, string>();
	const counts = new Map<string, number>();

	for (const scout of scouts) {
		for (const tag of parseTopicTags(scout.topic)) {
			const key = tag.toLocaleLowerCase();
			labels.set(key, labels.get(key) ?? tag);
			counts.set(key, (counts.get(key) ?? 0) + 1);
		}
	}

	return [...counts.entries()]
		.map(([key, count]) => ({ topic: labels.get(key) ?? key, count }))
		.sort((a, b) => a.topic.localeCompare(b.topic, undefined, { sensitivity: 'base' }));
}
