<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { MapPin, Tag, Radio, Home, FileText } from 'lucide-svelte';
	import FilterBar from '$lib/components/ui/FilterBar.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import PanelPlaceholder from '$lib/components/ui/PanelPlaceholder.svelte';
	import ScoutCard from '$lib/components/workspace/ScoutCard.svelte';
	import ScoutFocus from '$lib/components/workspace/ScoutFocus.svelte';
	import Inbox from '$lib/components/workspace/Inbox.svelte';
	import UnitDrawer from '$lib/components/workspace/UnitDrawer.svelte';
	import NewScoutDropdown from '$lib/components/workspace/NewScoutDropdown.svelte';
	import BeatScoutView from '$lib/components/news/BeatScoutView.svelte';
	import PageScoutView from '$lib/components/news/PageScoutView.svelte';
	import SocialScoutView from '$lib/components/news/SocialScoutView.svelte';
	import CivicScoutView from '$lib/components/news/CivicScoutView.svelte';
	import { scoutsStore } from '$lib/stores/workspace/scouts';
	import { unitsStore } from '$lib/stores/workspace/units';
	import { selectionStore } from '$lib/stores/workspace/selection';
	import { drawerStore } from '$lib/stores/workspace/drawer';
	import { authStore } from '$lib/stores/auth';
	import { workspaceApi, ApiError } from '$lib/api-client';
	import type { Scout, Unit } from '$lib/types/workspace';
	import PreferencesModal from '$lib/components/modals/PreferencesModal.svelte';
	import AgentsModal from '$lib/components/modals/AgentsModal.svelte';
	import UpgradeModal from '$lib/components/modals/UpgradeModal.svelte';
	import { Bot } from 'lucide-svelte';
	import { getScoutCost } from '$lib/utils/scouts';
	import { isDemoId, demoDismissed, markDemoDismissed } from '$lib/demo/seed';

	let newScoutOpen = false;
	let userMenuOpen = false;
	let preferencesOpen = false;
	let agentsOpen = false;
	let showUpgradeModal = false;
	let upgradeRequired = 0;

	type ActivePanel = 'workspace' | 'pulse' | 'web' | 'social' | 'civic';
	let activePanel: ActivePanel = 'workspace';

	// After scheduling succeeds, views dispatch `scheduled` and we want to
	// (a) jump back to the workspace, (b) show a skeleton card while the
	// refresh lands, (c) kick off an immediate reload. Cleared once the new
	// scout appears or a watchdog expires.
	let pendingNewScoutType: ActivePanel | null = null;
	let pendingWatchdog: ReturnType<typeof setTimeout> | null = null;

	async function handleScheduled(
		event: CustomEvent<{ scoutType: 'pulse' | 'web' | 'social' | 'civic' }>,
	) {
		pendingNewScoutType = event.detail.scoutType;
		activePanel = 'workspace';
		if (pendingWatchdog) clearTimeout(pendingWatchdog);
		pendingWatchdog = setTimeout(() => {
			pendingNewScoutType = null;
			pendingWatchdog = null;
		}, 20000);
		try {
			await scoutsStore.load();
		} finally {
			pendingNewScoutType = null;
			if (pendingWatchdog) {
				clearTimeout(pendingWatchdog);
				pendingWatchdog = null;
			}
		}
	}

	function openPanel(type: ActivePanel) {
		activePanel = type;
		newScoutOpen = false;
	}

	function handleNewScout(event: CustomEvent) {
		const type = event.type as string;
		const panelMap: Record<string, ActivePanel> = {
			trackPage: 'web',
			beatScout: 'pulse',
			profileScout: 'social',
			civicScout: 'civic'
		};
		const panel = panelMap[type];
		if (panel) openPanel(panel);
	}

	function closePanel() {
		activePanel = 'workspace';
	}

	async function handleSignOut() {
		userMenuOpen = false;
		await authStore.signOut();
	}

	function closeMenus(event: MouseEvent) {
		const target = event.target as HTMLElement;
		if (!target.closest('.user-menu-wrap') && !target.closest('.new-scout-wrap')) {
			userMenuOpen = false;
			newScoutOpen = false;
		}
	}
	let selectedLocation: string | null = null;
	let selectedTopic: string | null = null;
	let selectedScoutName: string | null = null;

	// Per-scout action state
	let runningScoutId: string | null = null;
	let deleteCandidateId: string | null = null;
	let deletingId: string | null = null;

	// Feed filter
	let feedFilter: 'needs_review' | 'all' = 'needs_review';

	// Drawer + active unit
	let activeUnit: Unit | null = null;
	let drawerActionLoading: 'verify' | 'reject' | null = null;

	$: scoutsState = $scoutsStore;
	$: unitsState = $unitsStore;
	$: selection = $selectionStore;
	$: drawerOpen = $drawerStore.open;

	// -------- filter computation (location + topic options) --------
	function locationDisplay(loc: unknown): string | null {
		if (!loc || typeof loc !== 'object') return null;
		const rec = loc as Record<string, unknown>;
		const dn = rec.displayName ?? rec.display_name;
		return typeof dn === 'string' ? dn : null;
	}

	$: locationOptions = (() => {
		const counts: Record<string, number> = {};
		for (const s of scoutsState.scouts) {
			const name = locationDisplay(s.location);
			if (name) counts[name] = (counts[name] || 0) + 1;
		}
		const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
		if (entries.length === 0) return [{ value: '', label: 'No locations' }];
		return [
			{ value: '', label: 'All locations' },
			...entries.map(([loc, count]) => ({ value: loc, label: loc, count }))
		];
	})();

	$: topicOptions = (() => {
		const counts: Record<string, number> = {};
		for (const s of scoutsState.scouts) {
			if (s.topic) counts[s.topic] = (counts[s.topic] || 0) + 1;
		}
		const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
		if (entries.length === 0) return [{ value: '', label: 'No topics' }];
		return [
			{ value: '', label: 'All topics' },
			...entries.map(([t, count]) => ({ value: t, label: t, count }))
		];
	})();

	$: dimensionFiltered = scoutsState.scouts
		.filter((s) => !selectedLocation || locationDisplay(s.location) === selectedLocation)
		.filter((s) => !selectedTopic || s.topic === selectedTopic);

	$: scoutNameOptions = [
		{ value: '', label: 'All scouts' },
		...[...new Set(dimensionFiltered.map((s) => s.name))].sort().map((n) => ({ value: n, label: n }))
	];

	// Selected scout (focus mode) derived from selection store
	$: focusedScout = selection.scoutId
		? scoutsState.scouts.find((s) => s.id === selection.scoutId) ?? null
		: null;

	// -------- counts for inbox header --------
	$: needsReviewCount = unitsState.units.filter((u) => !u.verification?.verified).length;
	$: visibleUnits = feedFilter === 'needs_review'
		? unitsState.units.filter((u) => !u.verification?.verified)
		: unitsState.units;

	// -------- mount --------
	let bootstrapped = false;
	$: demoActive =
		!demoDismissed() &&
		scoutsState.scouts.length > 0 &&
		scoutsState.scouts.every((s) => isDemoId(s.id));
	onMount(async () => {
		await Promise.all([scoutsStore.load(), unitsStore.load(null)]);
		if ($scoutsStore.scouts.length === 0 && !demoDismissed()) {
			scoutsStore.seedDemo();
			unitsStore.seedDemo();
		} else if ($scoutsStore.scouts.length > 0 && !demoDismissed()) {
			// Real scouts exist → user has moved past the empty state. Lock the
			// demo so it can never re-seed, and ensure no stale demo rows linger.
			markDemoDismissed();
			scoutsStore.clearDemo();
			unitsStore.clearDemo();
		}
		bootstrapped = true;
	});

	onDestroy(() => {
		selectionStore.clear();
		drawerStore.close();
	});

	// -------- handlers --------
	function handleScoutOpen(e: CustomEvent<{ scout: Scout }>) {
		const scout = e.detail.scout;
		selectionStore.selectScout(scout.id);
		selectedScoutName = scout.name;
		void unitsStore.load(scout.id);
	}

	function handleBackToAll() {
		selectionStore.selectScout(null);
		selectedScoutName = null;
		// In demo mode, the all-scouts inbox is the 12 seed units — the API
		// would return empty and erase them.
		if (demoActive) {
			unitsStore.seedDemo();
		} else {
			void unitsStore.load(null);
		}
	}

	async function handleRunScout(id: string) {
		if (isDemoId(id)) return;
		const scout = scoutsState.scouts.find((s) => s.id === id);
		if (!scout) return;

		// Pre-check credits client-side. The executor also decrements
		// authoritatively (scout-web-execute:119, scout-beat-execute:149,
		// civic-execute:117, social-kickoff:116) — this is UX only.
		const perRunCost = getScoutCost(scout.type, scout.platform ?? undefined);
		const currentCredits = $authStore.user?.credits ?? 0;
		if (currentCredits < perRunCost) {
			upgradeRequired = perRunCost;
			showUpgradeModal = true;
			return;
		}

		runningScoutId = id;
		try {
			await workspaceApi.runScout(id);
			// Poll scout.last_run.status until terminal. runScout returns 202
			// immediately; the actual execution happens async server-side.
			const deadline = Date.now() + 5 * 60_000;
			while (Date.now() < deadline) {
				await new Promise((r) => setTimeout(r, 2000));
				await scoutsStore.load();
				const fresh = $scoutsStore.scouts.find((s) => s.id === id);
				const status = fresh?.last_run?.status;
				if (status && status !== 'running' && status !== 'queued') break;
			}
			await unitsStore.load(selection.scoutId);
			// Refresh credits so the next Run Now click sees the post-decrement
			// balance (mirrors ScoutScheduleModal production behaviour).
			await authStore.refreshUser();
		} catch (err) {
			console.error('Run scout failed:', err);
		} finally {
			runningScoutId = null;
		}
	}

	function handleRequestDelete(id: string) {
		if (isDemoId(id)) return;
		deleteCandidateId = id;
	}

	function handleCancelDelete() {
		deleteCandidateId = null;
	}

	async function handleConfirmDelete(id: string) {
		if (isDemoId(id)) return;
		deletingId = id;
		try {
			await scoutsStore.remove(id);
			if (selection.scoutId === id) handleBackToAll();
		} finally {
			deletingId = null;
			deleteCandidateId = null;
		}
	}

	// -------- filters: changes --------
	async function handleLocationChange(v: string) {
		selectedLocation = v || null;
		selectedScoutName = null;
	}
	async function handleTopicChange(v: string) {
		selectedTopic = v || null;
		selectedScoutName = null;
	}
	function handleScoutFilterChange(v: string) {
		selectedScoutName = v || null;
		if (v) {
			const match = scoutsState.scouts.find((s) => s.name === v);
			if (match) handleScoutOpen(new CustomEvent('open', { detail: { scout: match } }));
		} else {
			handleBackToAll();
		}
	}

	// -------- unit row interactions --------
	async function handleOpenUnit(e: CustomEvent<{ unit: Unit }>) {
		activeUnit = e.detail.unit;
		selectionStore.selectUnit(e.detail.unit.id);
		drawerStore.open();
	}

	async function handleVerify(e: CustomEvent<{ id: string }>) {
		drawerActionLoading = 'verify';
		try {
			const updated = await workspaceApi.promoteUnit(e.detail.id);
			unitsStore.patchUnit(e.detail.id, updated);
			drawerStore.closeAndClear();
			activeUnit = null;
		} catch (err) {
			console.error('Verify failed:', err);
		} finally {
			drawerActionLoading = null;
		}
	}

	async function handleReject(e: CustomEvent<{ id: string }>) {
		drawerActionLoading = 'reject';
		try {
			const updated = await workspaceApi.rejectUnit(e.detail.id);
			unitsStore.patchUnit(e.detail.id, updated);
			drawerStore.closeAndClear();
			activeUnit = null;
		} catch (err) {
			console.error('Reject failed:', err);
		} finally {
			drawerActionLoading = null;
		}
	}

	function handleDrawerClose() {
		drawerStore.closeAndClear();
		activeUnit = null;
	}

	// Load more at scroll bottom
	function handleLoadMore() {
		void unitsStore.loadMore();
	}

	// Search (debounced via FilterBar)
	async function handleSearch(query: string) {
		await unitsStore.search(query, selection.scoutId);
	}
</script>

<svelte:window on:click={closeMenus} />

<div class="workspace">
	<!-- Top nav -->
	<nav class="topnav">
		<div class="topnav-left">
			<div class="logo">
				<span class="logo-dot"></span>
				<span class="logo-text">coJournalist</span>
			</div>
			<div class="new-scout-wrap">
				<button
					class="new-scout-btn"
					on:click|stopPropagation={() => (newScoutOpen = !newScoutOpen)}
					aria-haspopup="menu"
					aria-expanded={newScoutOpen}
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
						<line x1="12" y1="5" x2="12" y2="19" />
						<line x1="5" y1="12" x2="19" y2="12" />
					</svg>
					<span>New Scout</span>
					<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
						<polyline points="6 9 12 15 18 9" />
					</svg>
				</button>
				<NewScoutDropdown
					open={newScoutOpen}
					sidebarCollapsed={false}
					on:close={() => (newScoutOpen = false)}
					on:trackPage={handleNewScout}
					on:beatScout={handleNewScout}
					on:profileScout={handleNewScout}
					on:civicScout={handleNewScout}
				/>
			</div>
			<button
				class="agents-btn"
				on:click|stopPropagation={() => (agentsOpen = true)}
				aria-haspopup="dialog"
			>
				<Bot size={14} />
				<span>Agents</span>
			</button>
			{#if activePanel !== 'workspace'}
				<button class="back-to-workspace" on:click={closePanel} type="button">
					<Home size={14} />
					<span>Back to workspace</span>
				</button>
			{/if}
		</div>
		<div class="topnav-right">
			{#if $authStore.authenticated || $authStore.user}
				<span class="credits-pill" title="Credits remaining this month">
					<span class="credits-value">{$authStore.user?.credits ?? 0}</span>
					<span class="credits-label">credits</span>
				</span>
			{/if}
			<div class="user-menu-wrap">
				<button
					class="user-avatar"
					on:click|stopPropagation={() => (userMenuOpen = !userMenuOpen)}
					aria-haspopup="menu"
					aria-expanded={userMenuOpen}
					aria-label="User menu"
				>
					{($authStore.user?.email ?? 'U').slice(0, 2).toUpperCase()}
				</button>
				{#if userMenuOpen}
					<div class="user-menu" role="menu">
						{#if $authStore.user?.email}
							<p class="user-menu-email">{$authStore.user.email}</p>
						{/if}
						<button class="user-menu-item" role="menuitem" on:click={() => { userMenuOpen = false; preferencesOpen = true; }}>
							Preferences
						</button>
						<a href="/docs" class="user-menu-item" role="menuitem" on:click={() => (userMenuOpen = false)}>Docs</a>
						<a href="/" class="user-menu-item" role="menuitem" on:click={() => (userMenuOpen = false)}>Pricing</a>
						<a href="/terms" class="user-menu-item" role="menuitem" on:click={() => (userMenuOpen = false)}>Terms</a>
						<button class="user-menu-item user-menu-danger" role="menuitem" on:click={handleSignOut}>
							Sign out
						</button>
					</div>
				{/if}
			</div>
		</div>
	</nav>

	<!-- Filter bar -->
	{#if activePanel === 'workspace' && bootstrapped && scoutsState.scouts.length > 0}
	<FilterBar
		searchEnabled
		searchPlaceholder={focusedScout ? `Search in ${focusedScout.name}` : 'Search units'}
		onSearch={handleSearch}
	>
		<FilterSelect
			icon={MapPin}
			options={locationOptions}
			value={selectedLocation || ''}
			onChange={handleLocationChange}
		/>
		<FilterSelect
			icon={Tag}
			options={topicOptions}
			value={selectedTopic || ''}
			onChange={handleTopicChange}
		/>
		<div class="filter-divider"></div>
		<FilterSelect
			icon={Radio}
			disabled={scoutNameOptions.length <= 1}
			options={scoutNameOptions}
			value={selectedScoutName || ''}
			onChange={handleScoutFilterChange}
		/>
	</FilterBar>
	{/if}

	<!-- Body -->
	<div class="workspace-body">
		{#if activePanel !== 'workspace'}
			<!-- Scout creation panel (inline, reactive) -->
			<div class="panel-content">
				{#if activePanel === 'pulse'}
					<BeatScoutView on:scheduled={handleScheduled} />
				{:else if activePanel === 'web'}
					<PageScoutView on:scheduled={handleScheduled} />
				{:else if activePanel === 'social'}
					<SocialScoutView on:scheduled={handleScheduled} />
				{:else if activePanel === 'civic'}
					<CivicScoutView on:scheduled={handleScheduled} />
				{/if}
			</div>
		{:else if !bootstrapped}
			<div class="workspace-bootstrap">
				<Spinner size="md" />
			</div>
		{:else}
		{#if focusedScout}
			<!-- FOCUS MODE -->
			<ScoutFocus
				scout={focusedScout}
				demo={isDemoId(focusedScout.id)}
				running={runningScoutId === focusedScout.id}
				confirmingDelete={deleteCandidateId === focusedScout.id}
				deleting={deletingId === focusedScout.id}
				totalScouts={scoutsState.scouts.length}
				on:back={handleBackToAll}
				on:run={(e) => handleRunScout(e.detail.id)}
				on:requestDelete={(e) => handleRequestDelete(e.detail.id)}
				on:cancelDelete={handleCancelDelete}
				on:confirmDelete={(e) => handleConfirmDelete(e.detail.id)}
			/>
		{:else if scoutsState.scouts.length === 0 && pendingNewScoutType}
			<!-- FIRST-SCOUT LOADING — empty array but we know one is on its way -->
			<div class="scouts-section">
				<div class="section-heading">
					<h2>Scouts</h2>
				</div>
				<div class="scouts-grid">
					<div class="scout-card-pending" role="status" aria-live="polite">
						<Spinner size="sm" />
						<span>Creating your new scout…</span>
					</div>
				</div>
			</div>
		{:else if scoutsState.scouts.length === 0}
			<!-- RETURNING-USER EMPTY: single centered card, not two stacked placeholders -->
			<div class="workspace-empty">
				<div class="workspace-empty-card">
					<h2 class="workspace-empty-title">Your workspace is empty</h2>
					<p class="workspace-empty-body">
						Create a scout to start monitoring a page, a beat, a social profile, or a council website.
					</p>
					<p class="workspace-empty-hint">Click <strong>+ New Scout</strong> above to begin.</p>
				</div>
			</div>
		{:else}
			<!-- SCOUTS GRID -->
			<div class="scouts-section">
				<div class="section-heading">
					<h2>Scouts · {scoutsState.scouts.length}</h2>
					<span class="hint">Click a scout to scope the feed.</span>
				</div>
				{#if demoActive}
					<div class="demo-banner" role="note">
						<span class="demo-banner-label">Example data</span>
						<span class="demo-banner-text">
							These 4 scouts are a preview — not running, not billed. Click them to explore.
							They'll vanish the moment you create your first real scout.
						</span>
					</div>
				{/if}
				{#if dimensionFiltered.length === 0}
					<PanelPlaceholder
						title="No scouts match your filters"
						subtitle="Adjust the filters above or clear them to see all scouts."
					/>
				{:else}
					<div class="scouts-grid">
						{#if pendingNewScoutType}
							<div class="scout-card-pending" role="status" aria-live="polite">
								<Spinner size="sm" />
								<span>Creating your new scout…</span>
							</div>
						{/if}
						{#each dimensionFiltered as scout (scout.id)}
							<ScoutCard
								{scout}
								demo={isDemoId(scout.id)}
								running={runningScoutId === scout.id}
								confirmingDelete={deleteCandidateId === scout.id}
								deleting={deletingId === scout.id}
								on:open={handleScoutOpen}
								on:run={(e) => handleRunScout(e.detail.id)}
								on:requestDelete={(e) => handleRequestDelete(e.detail.id)}
								on:cancelDelete={handleCancelDelete}
								on:confirmDelete={(e) => handleConfirmDelete(e.detail.id)}
							/>
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		{#if scoutsState.scouts.length > 0}
			<!-- FEED / INBOX -->
			<Inbox
				units={visibleUnits}
				loading={unitsState.loading}
				hasMore={unitsState.hasMore}
				filter={feedFilter}
				scopedToScout={focusedScout}
				totalCount={unitsState.units.length}
				{needsReviewCount}
				on:filterChange={(e) => (feedFilter = e.detail.filter)}
				on:openUnit={handleOpenUnit}
				on:verify={handleVerify}
				on:reject={handleReject}
				on:loadMore={handleLoadMore}
			/>
		{/if}
	{/if}
	</div>

	<!-- Unit drawer -->
	<UnitDrawer
		unit={activeUnit}
		open={drawerOpen}
		loading={false}
		actionLoading={drawerActionLoading}
		on:close={handleDrawerClose}
		on:verify={handleVerify}
		on:reject={handleReject}
	/>

	<PreferencesModal
		open={preferencesOpen}
		on:close={() => preferencesOpen = false}
	/>

	<AgentsModal
		open={agentsOpen}
		on:close={() => (agentsOpen = false)}
	/>

	<UpgradeModal
		open={showUpgradeModal}
		currentCredits={$authStore.user?.credits ?? 0}
		requiredCredits={upgradeRequired}
		operationType="monitoring"
		on:close={() => (showUpgradeModal = false)}
	/>
</div>

<style>
	/* ──────────────────────────────────────────────────────────
	   Dashboard shell + topnav — plum + ochre on cream
	   ────────────────────────────────────────────────────────── */
	.workspace {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		background: var(--color-bg);
		font-family: var(--font-body);
	}

	.topnav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.625rem 1.25rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface-alt);
	}

	.topnav-left {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.logo {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.logo-dot {
		width: 0.5rem;
		height: 0.5rem;
		background: var(--color-primary);
	}

	.logo-text {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--color-ink);
		letter-spacing: -0.01em;
	}

	.new-scout-wrap {
		position: relative;
	}

	.new-scout-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4375rem;
		height: 32px;
		padding: 0 0.875rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-bg);
		background: var(--color-ink);
		border: 1px solid var(--color-ink);
		border-radius: 0;
		cursor: pointer;
		transition: background 150ms ease, border-color 150ms ease;
	}

	.new-scout-btn:hover {
		background: var(--color-primary-deep);
		border-color: var(--color-primary-deep);
	}

	.topnav-right {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.credits-pill {
		display: inline-flex;
		align-items: baseline;
		gap: 0.375rem;
		height: 32px;
		padding: 0 0.75rem;
		background: var(--color-secondary-soft);
		border: 1px solid var(--color-secondary);
		white-space: nowrap;
	}

	.credits-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		line-height: 1;
		color: var(--color-ink);
	}

	.credits-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		line-height: 1;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-secondary);
		transform: translateY(-1px);
	}

	.agents-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4375rem;
		height: 32px;
		padding: 0 0.75rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-ink-muted);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		cursor: pointer;
		transition: border-color 150ms ease, color 150ms ease, background 150ms ease;
	}

	.agents-btn:hover {
		color: var(--color-primary);
		border-color: var(--color-primary);
		background: var(--color-primary-soft);
	}

	.user-menu-wrap {
		position: relative;
	}
	.user-avatar {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border-radius: 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border-strong);
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: var(--color-ink-muted);
		cursor: pointer;
		transition: border-color 150ms ease, color 150ms ease, background 150ms ease;
	}
	.user-avatar:hover {
		background: var(--color-primary-soft);
		border-color: var(--color-primary);
		color: var(--color-primary);
	}
	.user-menu {
		position: absolute;
		top: calc(100% + 0.5rem);
		right: 0;
		min-width: 13rem;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		box-shadow: var(--shadow-modal);
		padding: 0.375rem;
		z-index: 30;
	}
	.user-menu-email {
		padding: 0.5rem 0.625rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.04em;
		color: var(--color-ink-muted);
		border-bottom: 1px solid var(--color-border);
		margin: 0 0 0.25rem 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.user-menu-item {
		display: block;
		width: 100%;
		padding: 0.5rem 0.625rem;
		font-family: var(--font-body);
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-ink);
		text-decoration: none;
		text-align: left;
		background: transparent;
		border: none;
		cursor: pointer;
		transition: background 150ms ease, color 150ms ease;
	}
	.user-menu-item:hover {
		background: var(--color-primary-soft);
		color: var(--color-primary-deep);
	}
	.user-menu-danger {
		color: var(--color-error);
	}
	.user-menu-danger:hover {
		background: var(--color-surface);
		color: var(--color-error);
	}

	.filter-divider {
		width: 1px;
		height: 20px;
		background: var(--color-border);
		margin: 0 0.25rem;
		flex-shrink: 0;
	}

	.workspace-body {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}

	.workspace-bootstrap {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 60vh;
	}

	.workspace-empty {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 3rem 2rem;
		min-height: 60vh;
	}

	.workspace-empty-card {
		max-width: 32rem;
		text-align: center;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 0;
		padding: 2.5rem 2rem;
	}

	.workspace-empty-title {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 0.75rem;
		letter-spacing: -0.01em;
	}

	.workspace-empty-body {
		font-size: 0.9375rem;
		font-weight: 300;
		line-height: 1.55;
		color: var(--color-ink-muted);
		margin: 0 0 1rem;
	}

	.workspace-empty-hint {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.06em;
		color: var(--color-ink-subtle);
		margin: 0;
	}

	.workspace-empty-hint strong {
		font-weight: 500;
		color: var(--color-primary);
		text-transform: uppercase;
	}

	.scouts-section {
		padding: 1.5rem 2rem 0.5rem;
	}

	.section-heading {
		display: flex;
		align-items: baseline;
		justify-content: flex-start;
		gap: 0.75rem;
		margin-left: 15px;
		margin-bottom: 0.875rem;
	}

	.section-heading h2 {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
		letter-spacing: -0.01em;
	}

	.section-heading .hint {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-ink-subtle);
	}

	.demo-banner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.625rem 0.875rem;
		margin-bottom: 0.875rem;
		background: var(--color-secondary-soft);
		border: 1px solid var(--color-secondary);
		border-left-width: 3px;
	}

	.demo-banner-label {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		color: var(--color-bg);
		background: var(--color-secondary);
		padding: 0.25rem 0.5rem;
	}

	.demo-banner-text {
		font-size: 0.8125rem;
		color: var(--color-ink);
		line-height: 1.4;
	}

	.scouts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 1rem;
	}

	.scout-card-pending {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		min-height: 120px;
		padding: 1rem;
		border: 1px dashed var(--color-border-strong);
		background: var(--color-surface-alt);
		color: var(--color-ink-muted);
		font-size: 0.875rem;
		border-radius: 4px;
	}

	.back-to-workspace {
		display: inline-flex;
		align-items: center;
		gap: 0.4375rem;
		height: 32px;
		padding: 0 0.75rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-ink-muted);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		cursor: pointer;
		transition: border-color 150ms ease, color 150ms ease;
	}

	.back-to-workspace:hover {
		color: var(--color-primary);
		border-color: var(--color-primary);
		background: var(--color-primary-soft);
	}

	.panel-content {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}
</style>
