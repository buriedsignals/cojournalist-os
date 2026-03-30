<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { MapPin, X, Loader2, Clock, Globe } from 'lucide-svelte';
	import { env } from '$env/dynamic/public';
	import type { GeocodedLocation } from '$lib/types';
	import { getRecentLocations, addRecentLocation } from '$lib/stores/recent-locations';
	import * as m from '$lib/paraglide/messages';

	const dispatch = createEventDispatcher<{
		select: GeocodedLocation;
		clear: void;
		global: void;
	}>();

	export let selectedLocation: GeocodedLocation | null = null;
	export let placeholder: string = 'Search for a city or country...';
	export let showGlobalOption: boolean = false;
	export let isGlobal: boolean = false;

	let searchQuery = '';
	let suggestions: MapTilerFeature[] = [];
	let recentLocations: GeocodedLocation[] = [];
	let isLoading = false;
	let showDropdown = false;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let inputElement: HTMLInputElement;

	interface MapTilerFeature {
		id: string;
		place_name: string;
		place_type: string[];
		text: string;
		context?: Array<{
			id: string;
			text: string;
			short_code?: string;
		}>;
		properties: {
			country_code?: string;
		};
		center?: [number, number]; // [lon, lat]
	}

	interface MapTilerResponse {
		features: MapTilerFeature[];
	}

	function debounce(fn: () => void, delay: number) {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(fn, delay);
	}

	async function searchLocations(query: string) {
		if (!query || query.length < 2) {
			suggestions = [];
			showDropdown = false;
			return;
		}

		isLoading = true;
		showDropdown = true;

		try {
			const url = new URL(`https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json`);
			url.searchParams.set('key', env.PUBLIC_MAPTILER_API_KEY || '');
			url.searchParams.set('types', 'address,road,neighbourhood,postal_code,poi,major_landform');
			url.searchParams.set('excludeTypes', 'true');
			url.searchParams.set('limit', '5');

			const response = await fetch(url.toString());
			if (!response.ok) throw new Error('Geocoding request failed');

			const data: MapTilerResponse = await response.json();
			suggestions = data.features || [];
		} catch (error) {
			console.error('Geocoding error:', error);
			suggestions = [];
		} finally {
			isLoading = false;
		}
	}

	function handleInput() {
		debounce(() => searchLocations(searchQuery), 300);
	}

	function mapFeatureToLocation(feature: MapTilerFeature): GeocodedLocation {
		const placeType = feature.place_type[0];

		// Extract country code from properties or context
		let countryCode = feature.properties?.country_code?.toUpperCase() || '';

		// If not in properties, try to find in context
		if (!countryCode && feature.context) {
			const countryContext = feature.context.find((c) => c.id.startsWith('country'));
			if (countryContext?.short_code) {
				countryCode = countryContext.short_code.toUpperCase();
			}
		}

		// For country-level selections, use the feature's short_code
		if (placeType === 'country' && !countryCode) {
			// MapTiler uses lowercase country codes in the id like "country.ch"
			const idParts = feature.id.split('.');
			if (idParts.length > 1) {
				countryCode = idParts[1].toUpperCase();
			}
		}

		// Extract state/region code from context
		let stateCode: string | undefined;
		if (feature.context) {
			const regionContext = feature.context.find((c) => c.id.startsWith('region'));
			if (regionContext?.short_code) {
				// MapTiler returns state codes like "CH-ZH" - extract just the state part
				const shortCode = regionContext.short_code;
				stateCode = shortCode.includes('-') ? shortCode.split('-')[1] : shortCode;
			}
		}

		// Determine location type
		let locationType: 'city' | 'state' | 'country';
		let city: string | undefined;

		if (placeType === 'country') {
			locationType = 'country';
		} else if (placeType === 'region' || placeType === 'subregion') {
			locationType = 'state';
		} else {
			// municipality, county, locality, place, joint_municipality, etc.
			locationType = 'city';
			city = feature.text;
		}

		return {
			displayName: feature.place_name,
			city,
			state: stateCode,
			country: countryCode,
			locationType,
			maptilerId: feature.id,
			coordinates: feature.center ? {
				lon: feature.center[0],
				lat: feature.center[1]
			} : undefined
		};
	}

	function selectSuggestion(feature: MapTilerFeature) {
		const location = mapFeatureToLocation(feature);
		selectLocation(location);
	}

	function selectLocation(location: GeocodedLocation) {
		selectedLocation = location;
		searchQuery = '';
		suggestions = [];
		showDropdown = false;
		addRecentLocation(location);
		recentLocations = getRecentLocations();
		dispatch('select', location);
	}

	/**
	 * Filter recent locations by query (case-insensitive match on displayName).
	 */
	function getFilteredRecents(): GeocodedLocation[] {
		if (!searchQuery) return recentLocations;
		const query = searchQuery.toLowerCase();
		return recentLocations.filter((loc) => loc.displayName.toLowerCase().includes(query));
	}

	function clearLocation() {
		selectedLocation = null;
		searchQuery = '';
		suggestions = [];
		showDropdown = false;
		dispatch('clear');
	}

	function selectGlobal() {
		selectedLocation = null;
		searchQuery = '';
		suggestions = [];
		showDropdown = false;
		isGlobal = true;
		dispatch('global');
	}

	function clearGlobal() {
		isGlobal = false;
		dispatch('clear');
	}

	function handleClickOutside(event: MouseEvent) {
		const target = event.target as Node;
		if (!inputElement?.parentElement?.contains(target)) {
			showDropdown = false;
		}
	}

	function handleFocus() {
		if (searchQuery.length >= 2 || filteredRecents.length > 0) {
			showDropdown = true;
		}
	}

	// Reactive filtered recents based on search query
	$: filteredRecents = getFilteredRecents();

	onMount(() => {
		recentLocations = getRecentLocations();
		document.addEventListener('click', handleClickOutside);
		return () => {
			document.removeEventListener('click', handleClickOutside);
			clearTimeout(debounceTimer);
		};
	});
</script>

<div class="location-autocomplete">
	{#if selectedLocation}
		<!-- Selected location pill -->
		<button type="button" class="selected-location" on:click={clearLocation} title={m.locationAutocomplete_changeLocation()}>
			<MapPin size={14} />
			<span class="location-text">{selectedLocation.displayName}</span>
			<X size={14} class="remove-icon" />
		</button>
	{:else if showGlobalOption && isGlobal}
		<!-- Global pill -->
		<button type="button" class="selected-global" on:click={clearGlobal}>
			<Globe size={14} />
			<span class="location-text">Global</span>
			<X size={14} class="remove-icon" />
		</button>
	{:else}
		<!-- Search input -->
		<div class="search-container">
			<div class="input-wrapper">
				<MapPin size={14} class="input-icon" />
				<input
					bind:this={inputElement}
					type="text"
					bind:value={searchQuery}
					on:input={handleInput}
					on:focus={handleFocus}
					{placeholder}
					class="search-input {showGlobalOption ? 'has-global-btn' : ''}"
				/>
				{#if isLoading}
					<Loader2 size={14} class="loading-icon" />
				{/if}
				{#if showGlobalOption && !isLoading}
					<button type="button" class="global-btn" on:click={selectGlobal}>
						<Globe size={12} />
						Global
					</button>
				{/if}
			</div>

			{#if showDropdown && (suggestions.length > 0 || isLoading || filteredRecents.length > 0)}
				<div class="suggestions-dropdown">
					{#if filteredRecents.length > 0}
						<div class="section-label">{m.locationAutocomplete_recent()}</div>
						{#each filteredRecents as recent (recent.maptilerId)}
							<button
								type="button"
								class="suggestion-item"
								on:click={() => selectLocation(recent)}
							>
								<Clock size={14} />
								<span>{recent.displayName}</span>
							</button>
						{/each}
						{#if suggestions.length > 0 || isLoading}
							<div class="section-divider"></div>
						{/if}
					{/if}
					{#if isLoading && suggestions.length === 0}
						<div class="suggestion-loading">{m.locationAutocomplete_searching()}</div>
					{:else if suggestions.length > 0}
						{#each suggestions as suggestion (suggestion.id)}
							<button
								type="button"
								class="suggestion-item"
								on:click={() => selectSuggestion(suggestion)}
							>
								<MapPin size={14} />
								<span>{suggestion.place_name}</span>
							</button>
						{/each}
					{:else if searchQuery.length >= 2 && filteredRecents.length === 0}
						<div class="suggestion-empty">{m.locationAutocomplete_noLocations()}</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.location-autocomplete {
		width: 100%;
	}

	.selected-location {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.625rem 0.75rem;
		background: linear-gradient(135deg, rgba(150, 139, 223, 0.12), rgba(124, 111, 199, 0.08));
		border: 1px solid rgba(150, 139, 223, 0.25);
		border-radius: 0.5rem;
		font-size: 0.8125rem;
		font-weight: 500;
		font-family: 'DM Sans', sans-serif;
		color: #1e293b;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.selected-location:hover {
		background: linear-gradient(135deg, rgba(150, 139, 223, 0.18), rgba(124, 111, 199, 0.14));
		border-color: #968bdf;
	}

	.selected-global {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.625rem 0.75rem;
		background: linear-gradient(135deg, rgba(100, 116, 139, 0.10), rgba(100, 116, 139, 0.06));
		border: 1px solid rgba(100, 116, 139, 0.25);
		border-radius: 0.5rem;
		font-size: 0.8125rem;
		font-weight: 500;
		font-family: 'DM Sans', sans-serif;
		color: #475569;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.selected-global:hover {
		background: linear-gradient(135deg, rgba(100, 116, 139, 0.16), rgba(100, 116, 139, 0.10));
		border-color: #94a3b8;
	}

	.selected-global :global(.remove-icon) {
		opacity: 0.5;
		transition: opacity 0.2s ease;
		flex-shrink: 0;
	}

	.selected-global:hover :global(.remove-icon) {
		opacity: 1;
		color: #ef4444;
	}

	.location-text {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.selected-location :global(.remove-icon) {
		opacity: 0.5;
		transition: opacity 0.2s ease;
		flex-shrink: 0;
	}

	.selected-location:hover :global(.remove-icon) {
		opacity: 1;
		color: #ef4444;
	}

	.search-container {
		position: relative;
	}

	.input-wrapper {
		position: relative;
		display: flex;
		align-items: center;
	}

	.input-wrapper :global(.input-icon) {
		position: absolute;
		left: 0.75rem;
		color: var(--color-accent, #968bdf);
		pointer-events: none;
	}

	.search-input {
		width: 100%;
		padding: 0.625rem 0.75rem 0.625rem 2.25rem;
		background: #fafafa;
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		font-size: 0.8125rem;
		font-family: 'DM Sans', sans-serif;
		color: #1e293b;
		transition: all 0.2s ease;
	}

	.search-input:focus {
		outline: none;
		border-color: #968bdf;
		background: #ffffff;
		box-shadow: 0 0 0 3px rgba(150, 139, 223, 0.1);
	}

	.search-input::placeholder {
		color: #94a3b8;
	}

	.search-input.has-global-btn {
		padding-right: 5.5rem;
	}

	.global-btn {
		position: absolute;
		right: 0.375rem;
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.3rem 0.5rem;
		background: #f1f5f9;
		border: 1px solid #e2e8f0;
		border-radius: 0.375rem;
		font-size: 0.6875rem;
		font-weight: 500;
		font-family: 'DM Sans', sans-serif;
		color: #64748b;
		cursor: pointer;
		transition: all 0.15s ease;
		white-space: nowrap;
	}

	.global-btn:hover {
		background: #e2e8f0;
		border-color: #cbd5e1;
		color: #475569;
	}

	.input-wrapper :global(.loading-icon) {
		position: absolute;
		right: 0.75rem;
		color: #968bdf;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	.suggestions-dropdown {
		position: absolute;
		top: calc(100% + 0.25rem);
		left: 0;
		right: 0;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		padding: 0.5rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
		z-index: 50;
		max-height: 240px;
		overflow-y: auto;
	}

	.suggestion-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 0.75rem;
		border-radius: 0.375rem;
		font-size: 0.8125rem;
		font-family: 'DM Sans', sans-serif;
		color: #1e293b;
		background: transparent;
		border: none;
		text-align: left;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.suggestion-item:hover {
		background: #f8f9fa;
	}

	.suggestion-item :global(svg) {
		color: #64748b;
		flex-shrink: 0;
	}

	.suggestion-loading,
	.suggestion-empty {
		padding: 0.75rem;
		text-align: center;
		font-size: 0.75rem;
		color: #64748b;
		font-style: italic;
	}

	.section-label {
		padding: 0.375rem 0.75rem 0.25rem;
		font-size: 0.6875rem;
		font-weight: 600;
		color: #94a3b8;
		text-transform: uppercase;
		letter-spacing: 0.025em;
	}

	.section-divider {
		height: 1px;
		background: #e5e7eb;
		margin: 0.375rem 0.5rem;
	}
</style>
