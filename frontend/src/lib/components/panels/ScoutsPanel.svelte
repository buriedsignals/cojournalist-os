<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { apiClient } from '$lib/api-client';
	import type { ActiveJob, ActiveJobsResponse, ScoutType } from '$lib/types';
	import { authStore } from '$lib/stores/auth';
	import { scoutsRefreshSignal } from '$lib/stores/scouts-refresh';
	import { triggerFeedRefresh } from '$lib/stores/feed-refresh';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import PanelPlaceholder from '$lib/components/ui/PanelPlaceholder.svelte';
	import FilterBar from '$lib/components/ui/FilterBar.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { RefreshCw, Trash2, X, Check, Globe, Radar, MapPin, Calendar, ExternalLink, Tag, Play, Radio, Users, Landmark } from 'lucide-svelte';
	import RadarGraphic from '$lib/components/ui/RadarGraphic.svelte';
	import * as m from '$lib/paraglide/messages';
	import { SCOUT_COSTS, getScoutCost, truncateUrl, getScoutStatus, stripMarkdown, type StatusKey } from '$lib/utils/scouts';
	import { isTourActive } from '$lib/stores/onboarding-tour';
	import { tooltip } from '$lib/utils/tooltip';
	import { PLACEHOLDER_SCOUTS } from '$lib/data/onboarding-placeholders';

	interface TypedActiveJob extends ActiveJob {
		type: ScoutType;
		schedule?: string;
	}

	let isLoading = true;
	let allScouts: TypedActiveJob[] = [];
	let error: string | null = null;

	let scoutToDelete: string | null = null;
	let isDeleting = false;

	// Run Now state
	let runningScout: string | null = null;

	// Upgrade modal state for Run Now credit validation
	let upgradeRequiredCredits = 0;
	let upgradeOperationType: 'extraction' | 'monitoring' | 'export' | 'scout scheduling' = 'monitoring';

	// Expansion state - only one card can be expanded at a time
	let expandedScoutName: string | null = null;

	function toggleExpand(scoutName: string) {
		expandedScoutName = expandedScoutName === scoutName ? null : scoutName;
	}

	// Filter state
	let selectedLocation: string | null = null;
	let selectedTopic: string | null = null;
	let selectedScoutName: string | null = null;

	$: locationOptions = (() => {
		const counts: Record<string, number> = {};
		for (const s of allScouts) {
			const name = s.location?.displayName;
			if (name) counts[name] = (counts[name] || 0) + 1;
		}
		const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
		if (entries.length === 0) return [{ value: '', label: m.scouts_noLocations() }];
		return [
			{ value: '', label: m.scouts_allLocations() },
			...entries.map(([loc, count]) => ({ value: loc, label: loc, count }))
		];
	})();

	$: topicOptions = (() => {
		const counts: Record<string, number> = {};
		for (const s of allScouts) {
			if (s.topic) counts[s.topic] = (counts[s.topic] || 0) + 1;
		}
		const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
		if (entries.length === 0) return [{ value: '', label: m.scouts_noCategories() }];
		return [
			{ value: '', label: m.scouts_allCategories() },
			...entries.map(([t, count]) => ({ value: t, label: t, count }))
		];
	})();

	$: dimensionFiltered = allScouts
		.filter(s => !selectedLocation || s.location?.displayName === selectedLocation)
		.filter(s => !selectedTopic || s.topic === selectedTopic);

	$: scoutOptions = [
		{ value: '', label: m.feed_allScouts() },
		...[...new Set(dimensionFiltered.map(s => s.scraper_name))].sort().map(n => ({ value: n, label: n }))
	];

	$: filteredScouts = dimensionFiltered.filter(
		scout => !selectedScoutName || scout.scraper_name === selectedScoutName
	);

	async function handleRefresh() {
		isLoading = true;
		error = null;

		try {
			// Fetch all scouts from AWS (includes all scout types)
			const response: ActiveJobsResponse = await apiClient.getActiveJobs();
			const realScouts: TypedActiveJob[] = (response.scrapers || []).map(scout => ({
				...scout,
				// Use actual scout_type from API response
				type: (scout.scout_type || 'web') as ScoutType,
				// Convert regularity to display-friendly schedule with time
				schedule: scout.regularity ? formatRegularity(scout.regularity, scout.time) : undefined
			}));

			// All scouts come from AWS now
			allScouts = realScouts;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load active scouts';
			console.error('Error loading active scouts:', err);
			allScouts = [];
		} finally {
			isLoading = false;
		}
	}

	function initiateDelete(scoutName: string) {
		scoutToDelete = scoutName;
	}

	function cancelDelete() {
		scoutToDelete = null;
	}

	async function confirmDelete() {
		if (!scoutToDelete) return;

		isDeleting = true;

		try {
			// Delete via API for ALL scout types
			await apiClient.deleteActiveJob(scoutToDelete);
			scoutToDelete = null;
			await handleRefresh();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to delete scout';
			console.error('Error deleting scout:', err);
			scoutToDelete = null;
		} finally {
			isDeleting = false;
		}
	}

	async function handleRunNow(scoutName: string) {
		// Find the scout to get its type
		const scout = allScouts.find(s => s.scraper_name === scoutName);
		if (!scout) {
			error = 'Scout not found';
			return;
		}

		// Get the cost for this scout type (platform-aware for social)
		const perRunCost = getScoutCost(scout.type, scout.platform);

		// Show spinner immediately for better UX
		runningScout = scoutName;

		// Validate credits before running
		try {
			await apiClient.validateCredits(perRunCost, 'monitoring');
		} catch (err: unknown) {
			runningScout = null; // Clear spinner on validation failure
			// Check if it's an insufficient credits error (402)
			if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 402) {
				// Show upgrade modal
				upgradeRequiredCredits = perRunCost;
				upgradeOperationType = 'monitoring';
				showUpgradeModal = true;
				return;
			}
			// Other validation errors
			error = err instanceof Error ? err.message : 'Failed to validate credits';
			console.error('Credit validation error:', err);
			return;
		}

		// Credits validated - run the scout
		try {
			await apiClient.runScoutNow(scoutName);
			await handleRefresh();
			triggerFeedRefresh();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to run scout';
			console.error('Error running scout:', err);
		} finally {
			runningScout = null;
		}
	}

	$: SCOUT_TYPE_CONFIG = {
		'web':    { icon: Globe,     colorClass: 'bg-blue-100 text-blue-700',   label: m.scoutType_pageMonitor() },
		'pulse':  { icon: Radar,     colorClass: 'bg-purple-100 text-purple-700', label: m.scoutType_smartMonitor() },
		'social': { icon: Users,     colorClass: 'bg-pink-100 text-pink-700',   label: m.scoutType_socialMonitor() },
		'civic':  { icon: Landmark,  colorClass: 'bg-green-100 text-green-700', label: m.scoutType_civicMonitor() }
	} as Record<ScoutType, { icon: typeof Globe; colorClass: string; label: string }>;

	function formatRegularity(regularity: string, time?: string): string {
		// Weekly and Monthly: just the label, no time
		if (regularity === 'weekly') return m.schedule_weekly();
		if (regularity === 'monthly') return m.schedule_monthly();

		// Daily: include time
		if (regularity === 'daily' && time) {
			const [hourStr, minuteStr] = time.split(':');
			const hour = parseInt(hourStr, 10);
			const minute = parseInt(minuteStr, 10);
			const period = hour >= 12 ? 'PM' : 'AM';
			const displayHour = hour % 12 || 12;
			const displayTime = minute === 0
				? `${displayHour}${period}`
				: `${displayHour}:${minuteStr}${period}`;
			return m.scouts_scheduleDaily({ time: displayTime });
		}

		// Fallback
		return regularity.charAt(0).toUpperCase() + regularity.slice(1);
	}

	/** Map status key from getScoutStatus to localized text. */
	const STATUS_LABELS: Record<StatusKey, () => string> = {
		awaitingFirstRun: () => m.scouts_awaitingFirstRun(),
		runFailed: () => m.scouts_runFailed(),
		newFindings: () => m.scouts_newFindings(),
		match: () => m.scouts_match(),
		noChanges: () => m.scouts_noChanges(),
		noMatch: () => m.scouts_noMatch(),
	};

	/**
	 * Get the display text for the scout scope (topic or location).
	 */
	function getScopeDisplay(scout: TypedActiveJob): string {
		if (scout.topic && scout.location?.displayName) {
			return `'${scout.topic}' in ${scout.location.displayName}`;
		}
		if (scout.topic) {
			return `'${scout.topic}'`;
		}
		if (scout.location?.displayName) {
			return scout.location.displayName;
		}
		return 'this search';
	}

	let showingPlaceholders = false;

	function loadPlaceholders() {
		allScouts = PLACEHOLDER_SCOUTS.map(scout => ({
			...scout,
			type: (scout.scout_type || 'web') as ScoutType,
			schedule: scout.regularity ? formatRegularity(scout.regularity, scout.time) : undefined
		}));
		showingPlaceholders = true;
		isLoading = false;
	}

	onMount(() => {
		if ($isTourActive) {
			loadPlaceholders();
		} else {
			void handleRefresh();
		}
	});

	// Tour started after mount (e.g. replay button) — load placeholders reactively
	$: if ($isTourActive && !showingPlaceholders) {
		loadPlaceholders();
	}

	// When tour ends, replace placeholders with real data
	$: if (!$isTourActive && showingPlaceholders) {
		showingPlaceholders = false;
		void handleRefresh();
	}

	// Re-fetch when a scout is created elsewhere
	$: if ($scoutsRefreshSignal) {
		void handleRefresh();
	}
</script>

<div class="scouts-view">
	<!-- Header -->
	<div class="scouts-header">
		<FilterBar>
			{#if isLoading}
				<div class="loading-inline">
					<Spinner size="sm" />
					<span>{m.common_loading()}</span>
				</div>
			{:else}
				<FilterSelect
					icon={MapPin}
					options={locationOptions}
					value={selectedLocation || ''}
					onChange={(v) => { selectedLocation = v || null; selectedScoutName = null; }}
				/>

				<FilterSelect
					icon={Tag}
					options={topicOptions}
					value={selectedTopic || ''}
					onChange={(v) => { selectedTopic = v || null; selectedScoutName = null; }}
				/>

				<div class="filter-divider"></div>
				<FilterSelect
					icon={Radio}
					disabled={scoutOptions.length <= 1}
					options={scoutOptions}
					value={selectedScoutName || ''}
					onChange={(v) => { selectedScoutName = v; }}
				/>
			{/if}

			<svelte:fragment slot="toolbar">
				<slot name="toolbar" />
			</svelte:fragment>
		</FilterBar>
	</div>

	<!-- Content -->
	<div class="scouts-content">
		{#if error}
			<div class="error-card">
				<p class="error-title">{m.scouts_errorLoading()}</p>
				<p class="error-detail">{error}</p>
				<button on:click={handleRefresh} class="retry-button">
					<RefreshCw class="h-3 w-3" />
					{m.common_retry()}
				</button>
			</div>
		{:else if isLoading}
			<PanelPlaceholder loading loadingText={m.scouts_loadingScouts()} />
		{:else if filteredScouts.length === 0}
			<PanelPlaceholder
				title={m.scouts_noScoutsYet()}
				subtitle={m.scouts_createFromSidebar()}
			>
				<RadarGraphic slot="graphic" />
			</PanelPlaceholder>
		{:else}
			<div class="scouts-grid">
				{#each filteredScouts as scout (scout.scraper_name)}
					{@const status = getScoutStatus(scout)}
					<div
						class="scout-card"
						class:deleting={scoutToDelete === scout.scraper_name && isDeleting}
						class:expanded={expandedScoutName === scout.scraper_name}
						on:click={() => toggleExpand(scout.scraper_name)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleExpand(scout.scraper_name)}
						role="button"
						tabindex="0"
						aria-expanded={expandedScoutName === scout.scraper_name}
					>
						<div class="scout-card-header">
							{#if $isTourActive}
								<span class="demo-badge">{m.tour_demoBadge()}</span>
							{/if}
							<div class="scout-type-icon {scout.type}">
								<svelte:component this={SCOUT_TYPE_CONFIG[scout.type].icon} size={18} />
							</div>
							<div class="scout-header-info">
								<h3 class="scout-name">{scout.scraper_name}</h3>
								<span class="scout-type-badge {SCOUT_TYPE_CONFIG[scout.type].colorClass}">
									{SCOUT_TYPE_CONFIG[scout.type].label}
								</span>
							</div>
							<div class="card-actions">
							{#if $isTourActive}
								<!-- Buttons disabled during tour -->
							{:else if runningScout === scout.scraper_name}
								<div class="run-spinner" on:click|stopPropagation on:keydown|stopPropagation role="presentation">
									<Spinner size="sm" />
								</div>
							{:else}
								<button
									on:click|stopPropagation={() => handleRunNow(scout.scraper_name)}
									class="card-icon-btn run-btn"
									aria-label={m.scouts_runNow()}
									use:tooltip={m.scouts_runNowCost({ cost: getScoutCost(scout.type, scout.platform) })}
								>
									<Play size={16} />
								</button>
							{/if}
								{#if $isTourActive}
									<!-- Delete disabled during tour -->
								{:else if scoutToDelete === scout.scraper_name}
									<div class="confirm-strip" on:click|stopPropagation on:keydown|stopPropagation role="toolbar" tabindex="0">
										{#if isDeleting}
											<Spinner size="sm" />
										{:else}
											<button on:click|stopPropagation={cancelDelete} class="action-btn cancel-btn" aria-label={m.common_cancel()}>
												<X size={14} />
											</button>
											<span class="confirm-label">{m.scouts_deleteConfirm()}</span>
											<button on:click|stopPropagation={confirmDelete} class="action-btn confirm-btn" aria-label={m.common_yes()}>
												<Check size={14} />
											</button>
										{/if}
									</div>
								{:else}
									<button
										on:click|stopPropagation={() => initiateDelete(scout.scraper_name)}
										class="card-icon-btn trash-btn"
										aria-label={m.scouts_deleteScout()}
									>
										<Trash2 size={16} />
									</button>
								{/if}
							</div>
						</div>

						<div class="scout-card-body">
							{#if scout.location}
								<div class="scout-meta-item">
									<MapPin size={14} />
									<span>{scout.location.displayName}</span>
								</div>
							{/if}
							{#if scout.topic}
								<div class="scout-meta-item">
									<Tag size={14} />
									<span>{scout.topic}</span>
								</div>
							{/if}
							{#if scout.type === 'web' && (scout.url || scout.last_run?.url)}
								{@const displayUrl = scout.url || scout.last_run?.url || ''}
								<div class="scout-meta-item scout-url">
									<Globe size={14} />
									<span class="scout-url-text" title={displayUrl}>{truncateUrl(displayUrl)}</span>
								</div>
							{/if}
							<div class="scout-meta-item">
								<Calendar size={14} />
								<span>{m.scouts_lastRun({ time: scout.last_run?.last_run || m.scouts_awaitingFirstRun() })}</span>
							</div>
						</div>

						<!-- Expanded Content (unified across all scout types) -->
						{#if expandedScoutName === scout.scraper_name}
							<div class="scout-expanded" transition:slide={{ duration: 200 }}>
								{#if scout.last_run?.scraper_status === false}
									<p class="expanded-message error">{m.scouts_errorDuringExec()}</p>
								{:else if scout.last_run?.criteria_status === false}
									<p class="expanded-message neutral">
										{#if (scout.type === 'web' || scout.type === 'social') && scout.last_run?.card_summary}
											{scout.last_run.card_summary}
										{:else if scout.type === 'pulse'}
											{m.scouts_noNewResults({ scope: getScopeDisplay(scout) })}
										{:else if scout.type === 'web'}
											{m.scouts_changesNotMatched()}
										{:else}
											{m.scouts_noMatchingResults()}
										{/if}
									</p>
								{:else if scout.last_run?.card_summary}
									<p class="expanded-summary">{scout.last_run.card_summary}</p>
								{:else if scout.last_run?.summary}
									<p class="expanded-summary">{stripMarkdown(scout.last_run.summary)}</p>
								{:else}
									<p class="expanded-message neutral">{m.scouts_waitingFirstRun()}</p>
								{/if}

								{#if scout.last_run?.url}
									<a
										href={scout.last_run.url}
										target="_blank"
										rel="noopener noreferrer"
										class="expanded-link"
										on:click|stopPropagation
									>
										<span class="link-text">{scout.last_run.url}</span>
										<ExternalLink size={14} />
									</a>
								{/if}
							</div>
						{/if}

						<div class="scout-card-footer">
							<span
								class="status-badge"
								class:status-success={status.variant === 'success'}
								class:status-error={status.variant === 'error'}
								class:status-neutral={status.variant === 'neutral'}
								class:status-warning={status.variant === 'warning'}
								class:status-waiting={status.variant === 'waiting'}
							>
								<span class="status-dot"></span>
								{STATUS_LABELS[status.key]?.() ?? status.key}
							</span>
							{#if scout.schedule}
								<span class="schedule-badge">{scout.schedule}</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<!-- Upgrade Modal for Run Now credit validation -->

<style>
	.scouts-view {
		display: flex;
		flex-direction: column;
		height: 100%;
		background: #f9fafb;
	}

	.scouts-header {
		background: white;
	}

	.loading-inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
		color: #6b7280;
	}

	.filter-divider {
		width: 1px;
		height: 20px;
		background: #d1d5db;
		margin: 0 0.25rem;
		flex-shrink: 0;
	}

	.scouts-content {
		flex: 1;
		overflow-y: auto;
		padding: 0 2rem;
	}

	/* Error State */
	.error-card {
		border-radius: 0.75rem;
		background: #fef2f2;
		padding: 1.5rem;
		text-align: center;
		margin-top: 1.5rem;
	}

	.error-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: #7f1d1d;
		margin-bottom: 0.25rem;
	}

	.error-detail {
		font-size: 0.8125rem;
		color: #b91c1c;
	}

	.retry-button {
		margin-top: 0.75rem;
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 1rem;
		background: #fee2e2;
		border: none;
		border-radius: 0.5rem;
		font-size: 0.8125rem;
		font-weight: 500;
		color: #7f1d1d;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.retry-button:hover {
		background: #fecaca;
	}

	/* Scouts Grid */
	.scouts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 1rem;
		padding-top: 1.5rem;
	}

	.scout-card {
		display: flex;
		flex-direction: column;
		position: relative;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 0.75rem;
		padding: 1rem;
		transition: all 0.15s ease;
		cursor: pointer;
		min-height: 180px;
	}

	.scout-card:hover {
		border-color: #d1d5db;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
	}

	.scout-card.expanded {
		border-color: #7c6fc7;
		box-shadow: 0 4px 16px rgba(124, 111, 199, 0.15);
		z-index: 2;
		border-radius: 0.75rem 0.75rem 0 0;
	}

	.scout-card.deleting {
		opacity: 0.5;
		pointer-events: none;
	}

	.demo-badge {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		font-size: 0.625rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: #7c3aed;
		background: #ede9fe;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		z-index: 1;
	}

	.scout-card-header {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.scout-type-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.scout-type-icon.web {
		background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
		color: #2563eb;
	}

	.scout-type-icon.pulse {
		background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
		color: #7c3aed;
	}

	.scout-type-icon.social {
		background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%);
		color: #db2777;
	}

	.scout-type-icon.civic {
		background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
		color: #16a34a;
	}

	.scout-header-info {
		flex: 1;
		min-width: 0;
		margin-top: -0.125rem;
	}

	.scout-name {
		font-size: 0.9375rem;
		font-weight: 600;
		color: #111827;
		margin: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.scout-type-badge {
		display: block;
		width: fit-content;
		font-size: 0.625rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		margin-top: 0.0625rem;
	}

	.scout-card-body {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		margin-bottom: 0.75rem;
	}

	.scout-meta-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
		color: #6b7280;
	}

	.scout-url {
		color: #7c6fc7;
	}

	.scout-url-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 200px;
	}

	.scout-card-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid #f3f4f6;
		margin-top: auto;
	}

	.status-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 500;
		background: #f3f4f6;
		color: #6b7280;
		border-radius: 9999px;
	}

	.status-badge.status-success {
		background: #d1fae5;
		color: #065f46;
	}

	.status-badge.status-error {
		background: #fee2e2;
		color: #b91c1c;
	}

	.status-badge.status-warning,
	.status-badge.status-waiting {
		background: #fef3c7;
		color: #92400e;
	}

	.status-badge.status-neutral {
		background: #f3f4f6;
		color: #6b7280;
	}

	.status-dot {
		width: 0.375rem;
		height: 0.375rem;
		border-radius: 9999px;
		background: #9ca3af;
	}

	.status-success .status-dot {
		background: #10b981;
	}

	.status-error .status-dot {
		background: #dc2626;
	}

	.status-warning .status-dot,
	.status-waiting .status-dot {
		background: #f59e0b;
	}

	.status-neutral .status-dot {
		background: #9ca3af;
	}

	.schedule-badge {
		font-size: 0.75rem;
		font-weight: 600;
		color: #7c6fc7;
	}

	/* Card Actions */
	.card-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		flex-shrink: 0;
		position: relative;
	}

	.card-icon-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border-radius: 0.375rem;
		background: transparent;
		border: none;
		color: #9ca3af;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.run-btn:hover {
		background: #eff6ff;
		color: #2563eb;
	}

	.run-spinner {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
	}

	.trash-btn:hover {
		background: #fef2f2;
		color: #dc2626;
	}

	.confirm-strip {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 0.5rem;
		animation: slideIn 0.2s ease;
		position: absolute;
		right: 0;
		white-space: nowrap;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateX(8px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	.confirm-label {
		font-size: 0.6875rem;
		font-weight: 600;
		color: #b91c1c;
		text-transform: uppercase;
		padding: 0 0.25rem;
	}

	.action-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 0.25rem;
		border: none;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.cancel-btn {
		background: white;
		color: #6b7280;
	}

	.cancel-btn:hover {
		background: #f9fafb;
		color: #374151;
	}

	.confirm-btn {
		background: #dc2626;
		color: white;
	}

	.confirm-btn:hover {
		background: #b91c1c;
	}

	/* Expanded Content — drops below the card as an overlay panel */
	.scout-expanded {
		position: absolute;
		left: -1px;
		right: -1px;
		top: 100%;
		background: white;
		border: 1px solid #7c6fc7;
		border-top: 1px solid #f3f4f6;
		border-radius: 0 0 0.75rem 0.75rem;
		padding: 0.75rem 1rem;
		box-shadow: 0 8px 16px rgba(124, 111, 199, 0.15);
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
	}

	.expanded-summary {
		font-size: 0.8125rem;
		line-height: 1.5;
		color: #4b5563;
		margin: 0 0 0.5rem 0;
		/* Overflow protection for long summaries */
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
		word-break: break-word;
	}

	.expanded-message {
		font-size: 0.8125rem;
		line-height: 1.4;
		padding: 0.5rem 0.75rem;
		border-radius: 0.375rem;
		margin: 0 0 0.75rem 0;
	}

	.expanded-message.error {
		background: #fef2f2;
		color: #991b1b;
		border-left: 3px solid #ef4444;
	}

	.expanded-message.neutral {
		background: #f3f4f6;
		color: #4b5563;
		border-left: 3px solid #9ca3af;
	}

	.expanded-link {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: #7c6fc7;
		text-decoration: none;
		padding: 0.375rem 0.5rem;
		background: #f5f3ff;
		border-radius: 0.375rem;
		transition: all 0.15s ease;
		max-width: 100%;
	}

	.expanded-link:hover {
		background: #ede9fe;
		color: #5b4bbd;
	}

	.expanded-link .link-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}

	.expanded-link :global(svg) {
		flex-shrink: 0;
	}
</style>
