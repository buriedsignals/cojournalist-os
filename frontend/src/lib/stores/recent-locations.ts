/**
 * Recent Locations Store -- MRU cache of geocoded locations.
 *
 * USED BY: BeatScoutView.svelte, LocationAutocomplete.svelte
 * DEPENDS ON: $lib/types (GeocodedLocation)
 *
 * Stores the 5 most recently selected locations in localStorage
 * (key: 'cojournalist:recent-locations') for quick re-selection
 * without re-searching. Deduplicates by maptilerId.
 * Not a Svelte store -- exports plain functions (getRecentLocations,
 * addRecentLocation).
 */
import type { GeocodedLocation } from '$lib/types';

const STORAGE_KEY = 'cojournalist:recent-locations';
const MAX_RECENT_LOCATIONS = 5;

interface StoredLocations {
	locations: GeocodedLocation[];
}

/**
 * Get recent locations from localStorage.
 * Returns empty array if SSR or no stored locations.
 */
export function getRecentLocations(): GeocodedLocation[] {
	if (typeof window === 'undefined') return [];

	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (!stored) return [];

		const parsed: StoredLocations = JSON.parse(stored);
		return parsed.locations || [];
	} catch {
		return [];
	}
}

/**
 * Add a location to recent locations.
 * Deduplicates by maptilerId and keeps max 5 locations.
 * Most recent location is placed at the front.
 */
export function addRecentLocation(location: GeocodedLocation): void {
	if (typeof window === 'undefined') return;

	const current = getRecentLocations();

	// Remove any existing entry with the same maptilerId
	const filtered = current.filter((loc) => loc.maptilerId !== location.maptilerId);

	// Add new location at the front
	const updated = [location, ...filtered].slice(0, MAX_RECENT_LOCATIONS);

	const stored: StoredLocations = { locations: updated };
	localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
}
