<script lang="ts">
	import { apiClient, type InformationUnit } from '$lib/api-client';
	import { sidebarNav } from '$lib/stores/sidebar-nav';
	import { authStore } from '$lib/stores/auth';
	import { feedStore } from '$lib/stores/feed';
	import { feedRefreshSignal } from '$lib/stores/feed-refresh';
	import { parseLocationKey, buildLocationName, deriveScoutNames } from '$lib/utils/feed';
	import { isTourActive } from '$lib/stores/onboarding-tour';
	import { PLACEHOLDER_UNITS, type PlaceholderUnit } from '$lib/data/onboarding-placeholders';
	import FilterBar from '$lib/components/ui/FilterBar.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import { Trash2, FileText, MapPin, Tag, Radio } from 'lucide-svelte';
	import { slide } from 'svelte/transition';
	import UnitGrid from './UnitGrid.svelte';
	import ExportSlideOver from './ExportSlideOver.svelte';
	import * as m from '$lib/paraglide/messages';

	/** Bridge PlaceholderUnit → InformationUnit for tour demo data. */
	function placeholderToInformationUnit(p: PlaceholderUnit): InformationUnit {
		return {
			...p,
			pk: `DEMO#${p.unit_id}`,
			sk: `UNIT#${p.unit_id}`,
			scout_id: 'demo-scout',
			used_in_article: false,
			source_domain: p.source_domain
		};
	}

	let showingPlaceholders = false;

	// Upgrade modal

	// Filter state
	let locations: string[] = [];
	let topics: string[] = [];
	let selectedLocationKey: string | null = null;
	let selectedTopic: string | null = null;
	let selectedScoutId: string | null = null;

	// Units
	let units: InformationUnit[] = [];
	let searchQuery = '';
	let isSearching = false;

	// Loading
	let loadingLocations = false;
	let loadingUnits = false;
	let error: string | null = null;
	let hasLoadedOnce = false;

	// Similarity scores from semantic search
	let similarityScores: Map<string, number> = new Map();

	/** Map units to the shape expected by generateExportDraft. */
	function toExportPayload(sourceUnits: InformationUnit[]) {
		return {
			units: sourceUnits.map(u => ({
				statement: u.statement,
				source_title: u.source_title,
				source_url: u.source_url,
				unit_type: u.unit_type || 'fact',
				entities: u.entities || [],
				source_domain: u.source_domain || null,
				topic: u.topic || null
			})),
			location_name: buildLocationName(selectedLocationKey, selectedTopic),
			language: $authStore.user?.preferred_language || 'en',
			custom_system_prompt: $feedStore.customExportPrompt || undefined
		};
	}

	$: scoutNames = deriveScoutNames(units);

	// Options for filter selects
	$: locationOptions = locations.length === 0
		? [{ value: '', label: m.feed_noLocations() }]
		: [
			{ value: '', label: m.feed_selectLocation() },
			...locations.map(loc => ({ value: loc, label: parseLocationKey(loc).displayName }))
		];

	$: topicOptions = topics.length === 0
		? [{ value: '', label: m.feed_noTopics() }]
		: [
			{ value: '', label: m.feed_allTopics() },
			...topics.map(t => ({ value: t, label: t }))
		];

	$: scoutOptions = [
		{ value: '', label: m.feed_allScouts() },
		...scoutNames.map(s => ({ value: s.id, label: s.label }))
	];

	// Filtered units: apply scout client-side filter
	$: filteredUnits = units
		.filter(u => !u.used_in_article)
		.filter(u => !selectedScoutId || u.scout_id === selectedScoutId);

	$: displayedUnits = filteredUnits;

	// Has any filter been applied
	$: hasFilters = !!(selectedLocationKey || selectedTopic || searchQuery);
	$: hasUnfilteredUnits = units.filter(u => !u.used_in_article).length > 0;

	// Fetch locations, topics, and all units
	async function fetchLocations() {
		loadingLocations = true;
		error = null;
		try {
			const [locResponse, topicResponse, allUnitsResponse] = await Promise.all([
				apiClient.getUserUnitLocations(),
				apiClient.getUserUnitTopics(),
				apiClient.getAllUnusedUnits(50)
			]);
			locations = locResponse.locations;
			topics = topicResponse.topics;
			// Show all units by default when no filter is selected
			if (!selectedLocationKey && !selectedTopic) {
				units = allUnitsResponse.units;
			}
			hasLoadedOnce = true;
		} catch (e) {
			error = e instanceof Error ? e.message : m.feed_failedToLoadLocations();
		} finally {
			loadingLocations = false;
		}
	}

	// Refresh handler
	async function handleRefresh() {
		selectedLocationKey = null;
		selectedTopic = null;
		selectedScoutId = null;
		units = [];
		similarityScores = new Map();
		feedStore.deselectAll();
		feedStore.setGeneratedExport(null);
		await fetchLocations();
	}

	// Fetch when feed view becomes active
	$: if ($sidebarNav.activeView === 'feed' && !hasLoadedOnce && !loadingLocations && !$isTourActive) {
		fetchLocations();
	}

	// Tour started — load placeholders when feed view becomes active during tour
	$: if ($sidebarNav.activeView === 'feed' && $isTourActive && !showingPlaceholders) {
		units = PLACEHOLDER_UNITS.map(placeholderToInformationUnit);
		showingPlaceholders = true;
		hasLoadedOnce = true;
	}

	// When tour ends, replace placeholders with real data
	$: if (!$isTourActive && showingPlaceholders) {
		showingPlaceholders = false;
		hasLoadedOnce = false;
		fetchLocations();
	}

	// Re-fetch when a scout runs or is created elsewhere
	$: if ($feedRefreshSignal && hasLoadedOnce) {
		fetchLocations();
	}

	// Fetch units when location or topic changes
	async function handleFilterChange() {
		loadingUnits = true;
		error = null;
		similarityScores = new Map();
		feedStore.deselectAll();
		feedStore.setGeneratedExport(null);
		searchQuery = '';
		selectedScoutId = null;

		try {
			if (!selectedLocationKey && !selectedTopic) {
				// No filters: show all unused units
				const response = await apiClient.getAllUnusedUnits(50);
				units = response.units;
			} else if (selectedTopic && !selectedLocationKey) {
				const response = await apiClient.getUnitsByTopic({ topic: selectedTopic, limit: 50 });
				units = response.units;
			} else if (selectedLocationKey) {
				const parsed = parseLocationKey(selectedLocationKey);
				const response = await apiClient.getUnusedUnitsByLocation({
					country: parsed.country,
					state: parsed.state || undefined,
					city: parsed.city || undefined,
					displayName: parsed.displayName,
					limit: 50
				});
				units = response.units;
				if (selectedTopic) {
					units = units.filter(u => u.topic === selectedTopic);
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : m.feed_failedToLoadUnits();
			units = [];
		} finally {
			loadingUnits = false;
		}
	}

	// Semantic search handler
	async function handleSemanticSearch(query: string) {
		searchQuery = query;
		const trimmed = query.trim();

		if (!trimmed) {
			similarityScores = new Map();
			handleFilterChange();
			return;
		}

		// Backend requires min_length=2; avoid 422 for short queries
		if (trimmed.length < 2) {
			similarityScores = new Map();
			return;
		}

		isSearching = true;
		error = null;

		try {
			const params: Parameters<typeof apiClient.searchUnitsSemantic>[0] = {
				query: trimmed,
				limit: 30,
			};

			if (selectedLocationKey) {
				const parsed = parseLocationKey(selectedLocationKey);
				params.country = parsed.country;
				params.state = parsed.state || undefined;
				params.city = parsed.city || undefined;
				params.displayName = parsed.displayName;
			}

			if (selectedTopic) {
				params.topic = selectedTopic;
			}

			const response = await apiClient.searchUnitsSemantic(params);
			units = response.units;

			// Build similarity scores map
			const scores = new Map<string, number>();
			for (const u of response.units as (InformationUnit & { similarity_score?: number })[]) {
				if (u.similarity_score !== undefined) {
					scores.set(u.unit_id, u.similarity_score);
				}
			}
			similarityScores = scores;
		} catch (e) {
			error = e instanceof Error ? e.message : m.feed_searchFailed();
		} finally {
			isSearching = false;
		}
	}

	// Toggle unit selection (via store)
	function handleToggleUnit(unitId: string) {
		feedStore.toggleUnit(unitId);
	}

	// Select/deselect all
	function handleToggleSelectAll() {
		if ($feedStore.selectedUnitIds.size === filteredUnits.length) {
			feedStore.deselectAll();
		} else {
			feedStore.selectAll(filteredUnits.map(u => u.unit_id));
		}
	}

	// Delete selected units (soft delete)
	async function handleDeleteSelected() {
		if ($feedStore.selectedUnitIds.size === 0) return;

		const selectedIds = new Set($feedStore.selectedUnitIds);
		const selectedUnits = units.filter(u => selectedIds.has(u.unit_id));
		const unitKeys = selectedUnits.map(u => ({ pk: u.pk, sk: u.sk }));

		// Optimistic update
		units = units.filter(u => !selectedIds.has(u.unit_id));
		feedStore.deselectAll();

		try {
			await apiClient.markUnitsUsed(unitKeys);
		} catch (err) {
			// Restore on failure
			units = [...units, ...selectedUnits];
			console.error('Failed to delete units:', err);
		}
	}

	// Generate article draft
	async function handleGenerate() {
		if ($feedStore.selectedUnitIds.size === 0) return;

		const userCredits = 999999;
		if (userCredits < 1) {
			showUpgradeModal = true;
			return;
		}

		feedStore.setGenerating(true);
		feedStore.setGeneratedExport(null);
		feedStore.openSlideOver();

		try {
			const selectedUnits = units.filter(u => $feedStore.selectedUnitIds.has(u.unit_id));
			feedStore.setUnitsUsedForExport(selectedUnits);

			const draft = await apiClient.generateExportDraft(toExportPayload(selectedUnits));

			feedStore.setGeneratedExport(draft);
			feedStore.setGenerating(false);
			authStore.refreshUser();
		} catch (e) {
			feedStore.setGenerationError(e instanceof Error ? e.message : m.export_failedToGenerate());
		}
	}

	// Regenerate with same units but (possibly) updated prompt
	async function handleRegenerate() {
		const usedUnits = $feedStore.unitsUsedForExport;
		if (usedUnits.length === 0) return;

		const userCredits = 999999;
		if (userCredits < 1) {
			showUpgradeModal = true;
			return;
		}

		feedStore.setGenerating(true);
		feedStore.setGeneratedExport(null);

		try {
			const draft = await apiClient.generateExportDraft(toExportPayload(usedUnits));

			feedStore.setGeneratedExport(draft);
			feedStore.setGenerating(false);
			authStore.refreshUser();
		} catch (e) {
			feedStore.setGenerationError(e instanceof Error ? e.message : m.export_failedToGenerate());
		}
	}

	// Mark units as used only after a real export (download or CMS send)
	function markExportedUnitsUsed() {
		const usedUnits = $feedStore.unitsUsedForExport;
		if (usedUnits.length === 0) return;
		const unitKeys = usedUnits.map(u => ({ pk: u.pk, sk: u.sk }));
		units = units.filter(u => !unitKeys.some(k => k.pk === u.pk && k.sk === u.sk));
		feedStore.deselectAll();
		feedStore.setGeneratedExport(null);
		feedStore.closeSlideOver();
		apiClient.markUnitsUsed(unitKeys).catch(err => {
			console.warn('Failed to mark units as used:', err);
		});
	}

	// Export draft to markdown
	function handleExport() {
		const draft = $feedStore.generatedExport;
		if (!draft) return;

		const sectionsMarkdown = (draft.sections || [])
			.map(s => `## ${s.heading}\n\n${s.content}`)
			.join('\n\n');

		const markdown = `# ${draft.title}\n\n**${draft.headline}**\n\n${sectionsMarkdown}\n\n## Sources\n\n${draft.sources.map(s => `- [${s.title}](${s.url})`).join('\n')}\n`;

		const blob = new Blob([markdown], { type: 'text/markdown' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `draft-${Date.now()}.md`;
		a.click();
		URL.revokeObjectURL(url);

		markExportedUnitsUsed();
	}

</script>

<div class="feed-workspace">
	<FilterBar searchEnabled={true} bind:searchQuery onSearch={handleSemanticSearch} {isSearching} searchPlaceholder={m.feed_searchTopicsPlaceholder()}>
		{#if loadingLocations}
			<div class="loading-inline">
				<Spinner size="sm" />
				<span>{m.common_loading()}</span>
			</div>
		{:else}
			<FilterSelect
				icon={MapPin}
				options={locationOptions}
				value={selectedLocationKey || ''}
				onChange={(v) => { selectedLocationKey = v || null; handleFilterChange(); }}
			/>

			<FilterSelect
				icon={Tag}
				options={topicOptions}
				value={selectedTopic || ''}
				onChange={(v) => { selectedTopic = v || null; handleFilterChange(); }}
			/>

			{#if scoutOptions.length > 1}
				<div class="filter-divider"></div>
				<FilterSelect
					icon={Radio}
					options={scoutOptions}
					value={selectedScoutId || ''}
					onChange={(v) => { selectedScoutId = v || null; }}
				/>
			{/if}
		{/if}

		<svelte:fragment slot="toolbar">
			{#if filteredUnits.length > 0}
				<span class="count-label">
					{searchQuery
						? m.feed_availableForQuery({ count: filteredUnits.length, query: searchQuery })
						: m.feed_availableCount({ count: filteredUnits.length })}
				</span>
				{#if $feedStore.selectedUnitIds.size > 0}
					<button class="delete-selected-btn" on:click={handleDeleteSelected}>
						<Trash2 size={12} />
						{m.common_delete()}
					</button>
				{/if}
				<button class="select-toggle" on:click={handleToggleSelectAll}>
					{$feedStore.selectedUnitIds.size === filteredUnits.length ? m.feed_deselectAll() : m.feed_selectAll()}
				</button>
				{#if $feedStore.selectedUnitIds.size > 0}
					<button class="btn-primary" on:click={handleGenerate}>
						<FileText size={12} />
						{m.export_dropdown()} ({$feedStore.selectedUnitIds.size})
					</button>
				{/if}
			{/if}
		</svelte:fragment>
	</FilterBar>

	{#if error}
		<div class="error-notice">
			<span>{error}</span>
		</div>
	{/if}

	{#if $feedStore.generatedExport && !$feedStore.showExportSlideOver}
		<div class="export-recovery-banner" transition:slide={{ duration: 200 }}>
			<FileText size={14} />
			<span>{m.export_unsaved()}</span>
			<button class="banner-open-btn" on:click={() => feedStore.openSlideOver()}>
				{m.export_open()}
			</button>
		</div>
	{/if}

	<UnitGrid
		units={displayedUnits}
		selectedUnitIds={$feedStore.selectedUnitIds}
		loading={loadingLocations || loadingUnits}
		showDemoBadge={$isTourActive}
		{hasFilters}
		{hasUnfilteredUnits}
		{similarityScores}
		onToggleUnit={handleToggleUnit}
	/>

	<ExportSlideOver
		open={$feedStore.showExportSlideOver}
		draft={$feedStore.generatedExport}
		isGenerating={$feedStore.isGenerating}
		generationError={$feedStore.generationError}
		selectedCount={$feedStore.selectedUnitIds.size || $feedStore.unitsUsedForExport.length}
		customPrompt={$feedStore.customExportPrompt}
		onClose={() => { feedStore.closeSlideOver(); feedStore.deselectAll(); }}
		onRetry={handleGenerate}
		onRegenerate={handleRegenerate}
		onExport={handleExport}
		onDelete={() => {
			feedStore.setGeneratedExport(null);
			feedStore.closeSlideOver();
		}}
	/>
</div>


<style>
	.feed-workspace {
		display: flex;
		flex-direction: column;
		height: 100%;
		background: #f8f9fa;
		font-family: 'DM Sans', system-ui, sans-serif;
		position: relative;
	}

	.loading-inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
		color: var(--color-ink-muted);
	}

	.filter-divider {
		width: 1px;
		height: 20px;
		background: #d1d5db;
		margin: 0 0.25rem;
		flex-shrink: 0;
	}

	.error-notice {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0.75rem 1.25rem 0;
		padding: 0.625rem 0.75rem;
		background: rgba(179, 62, 46, 0.08);
		border-radius: 6px;
		font-size: 0.8125rem;
		color: var(--color-error);
	}

	.count-label {
		font-size: 0.75rem;
		color: var(--color-ink-muted);
	}

	.delete-selected-btn {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--color-error);
		background: transparent;
		border: none;
		cursor: pointer;
		padding: 0;
	}

	.delete-selected-btn:hover {
		color: var(--color-error);
	}

	.select-toggle {
		font-size: 0.75rem;
		font-weight: 500;
		color: #6366f1;
		background: transparent;
		border: none;
		cursor: pointer;
		padding: 0;
	}

	.select-toggle:hover {
		text-decoration: underline;
	}

	.export-recovery-banner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0.75rem 1.25rem 0;
		padding: 0.5rem 0.75rem;
		background: rgba(150, 139, 223, 0.08);
		border: 1px solid rgba(150, 139, 223, 0.2);
		border-radius: 6px;
		font-size: 0.8125rem;
		color: var(--color-primary-deep);
	}

	.export-recovery-banner span {
		flex: 1;
	}

	.banner-open-btn {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-primary);
		background: rgba(124, 58, 237, 0.08);
		border: 1px solid rgba(124, 58, 237, 0.2);
		border-radius: 4px;
		padding: 0.25rem 0.625rem;
		cursor: pointer;
		transition: all 0.15s ease;
		white-space: nowrap;
	}

	.banner-open-btn:hover {
		background: rgba(124, 58, 237, 0.15);
		border-color: rgba(124, 58, 237, 0.3);
	}

</style>
