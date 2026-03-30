/**
 * Location Store -- shared geocoded location for location-aware features.
 *
 * USED BY: SmartScoutView.svelte
 * DEPENDS ON: $lib/types (GeocodedLocation)
 *
 * Holds the currently selected GeocodedLocation for Smart Scout search
 * and criteria-based search. Components read this to pass location context
 * to API calls. No side effects (no localStorage, no API calls).
 */
import { writable } from 'svelte/store';
import type { GeocodedLocation } from '$lib/types';

function createLocationStore() {
	const { subscribe, set } = writable<GeocodedLocation | null>(null);

	return {
		subscribe,
		setLocation: (location: GeocodedLocation | null) => set(location),
		clear: () => set(null)
	};
}

export const locationStore = createLocationStore();
