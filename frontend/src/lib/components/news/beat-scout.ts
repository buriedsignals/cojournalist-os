import type { GeocodedLocation } from '$lib/types';

export type BeatScoutMode = 'location' | 'beat';
export type BeatScoutSourceMode = 'reliable' | 'niche';

interface BuildBeatScoutSearchRequestInput {
	mode: BeatScoutMode;
	sourceMode: BeatScoutSourceMode;
	topicInput: string;
	selectedLocation: GeocodedLocation | null;
	excludedDomains: string[];
	prioritySources: string[];
}

export interface BeatScoutSearchRequest {
	location?: GeocodedLocation;
	criteria?: string;
	excludedDomains?: string[];
	prioritySources?: string[];
}

export interface BeatScoutScheduleDraft {
	location: GeocodedLocation | null;
	criteria: string;
}

export function buildBeatScoutSearchRequest({
	mode,
	sourceMode,
	topicInput,
	selectedLocation,
	excludedDomains,
	prioritySources
}: BuildBeatScoutSearchRequestInput): BeatScoutSearchRequest | null {
	const trimmedTopic = topicInput.trim();
	const canSearch = mode === 'location' ? Boolean(selectedLocation) : Boolean(trimmedTopic);

	if (!canSearch) return null;

	return {
		location: selectedLocation ?? undefined,
		criteria: mode === 'location' && sourceMode === 'niche' ? undefined : trimmedTopic || undefined,
		excludedDomains: excludedDomains.length ? excludedDomains : undefined,
		prioritySources: prioritySources.length ? prioritySources : undefined
	};
}

export function buildBeatScoutScheduleDraft(
	selectedLocation: GeocodedLocation | null,
	topicInput: string
): BeatScoutScheduleDraft {
	return {
		location: selectedLocation,
		criteria: topicInput.trim()
	};
}
