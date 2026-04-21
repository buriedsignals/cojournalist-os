<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		LayoutDashboard,
		Plus,
		Download,
		List,
		Code,
		Settings,
		PanelLeftClose,
		PanelLeftOpen,
		ChevronRight,
		ChevronLeft,
		LogOut
	} from 'lucide-svelte';
	import { sidebarNav, type SidebarView } from '$lib/stores/sidebar-nav';
	import { authStore } from '$lib/stores/auth';
	import { onboardingTour } from '$lib/stores/onboarding-tour';
	import { tooltip } from '$lib/utils/tooltip';
	import * as m from '$lib/paraglide/messages';
	import NewScoutDropdown from '$lib/components/workspace/NewScoutDropdown.svelte';

	let showNewScoutDropdown = false;

	const dispatch = createEventDispatcher<{
		openPreferences: void;
	}>();

	function setView(view: SidebarView) {
		sidebarNav.setView(view);
	}

	function handleBeatScout() {
		showNewScoutDropdown = false;
		sidebarNav.setView('beat-scout');
	}

	function handleTrackPage() {
		showNewScoutDropdown = false;
		sidebarNav.setView('page-scout');
	}

	function handleProfileScout() {
		showNewScoutDropdown = false;
		sidebarNav.setView('social-scout');
	}

	function handleCivicScout() {
		showNewScoutDropdown = false;
		sidebarNav.setView('civic-scout');
	}

	// Check if a view is active
	function isActive(view: SidebarView): boolean {
		return $sidebarNav.activeView === view;
	}

	function handleSignOut() {
		authStore.signOut();
	}

	function replayOnboarding() {
		if (typeof localStorage !== 'undefined') {
			localStorage.removeItem('cojournalist_onboarding_tour_completed');
			localStorage.removeItem('cojournalist_timezone_verified');
		}
		onboardingTour.start();
	}

	$: collapsed = $sidebarNav.collapsed;
</script>

<div class="sidebar" class:collapsed>
	<!-- Logo + collapse toggle -->
	<div class="sidebar-header">
		{#if !collapsed}
			<img src="/logo-cojournalist.svg" alt="coJournalist" class="logo-img" />
		{/if}
		<button
			class="collapse-toggle"
			on:click={() => sidebarNav.toggleCollapsed()}
			use:tooltip={collapsed ? m.sidebar_expand() : m.sidebar_collapse()}
		>
			{#if collapsed}
				<PanelLeftOpen size={16} />
			{:else}
				<PanelLeftClose size={16} />
			{/if}
		</button>
	</div>

	<!-- OVERVIEW Section -->
	<div class="section">
		{#if !collapsed}
			<p class="section-label">{m.sidebar_overview()}</p>
		{/if}

		<!-- New Scout Button -->
		<button
			class="sidebar-new-scout"
			on:click={() => showNewScoutDropdown = !showNewScoutDropdown}
			data-tour="new-scout"
		>
			<Plus size={18} />
			{#if !collapsed}
				<span class="nav-text">{m.sidebar_newScout()}</span>
				<span class="chevron-right">
					{#if showNewScoutDropdown}
						<ChevronLeft size={14} />
					{:else}
						<ChevronRight size={14} />
					{/if}
				</span>
			{/if}
		</button>

		<NewScoutDropdown
			open={showNewScoutDropdown}
			sidebarCollapsed={collapsed}
			on:trackPage={handleTrackPage}
			on:beatScout={handleBeatScout}
			on:profileScout={handleProfileScout}
			on:civicScout={handleCivicScout}
			on:close={() => showNewScoutDropdown = false}
		/>

		<button
			class="nav-item"
			class:active={isActive('scouts')}
			on:click={() => setView('scouts')}
			data-tour="your-scouts"
			use:tooltip={collapsed ? m.sidebar_manage() : m.sidebar_manageTooltip()}
		>
			<LayoutDashboard size={18} class="nav-icon" />
			{#if !collapsed}
				<span class="nav-text">{m.sidebar_manage()}</span>
			{/if}
		</button>

		<button
			class="nav-item"
			class:active={isActive('feed')}
			on:click={() => setView('feed')}
			data-tour="feed"
			use:tooltip={collapsed ? m.sidebar_feed() : m.sidebar_feedTooltip()}
		>
			<List size={18} class="nav-icon" />
			{#if !collapsed}
				<span class="nav-text">{m.sidebar_feed()}</span>
			{/if}
		</button>

	</div>

	<!-- EXTRACT Section -->
	<div class="section">
		{#if !collapsed}
			<p class="section-label">{m.sidebar_extract()}</p>
		{/if}

		<button
			class="nav-item"
			class:active={isActive('extract')}
			on:click={() => setView('extract')}
			data-tour="scrape"
			use:tooltip={collapsed ? m.sidebar_scrape() : m.sidebar_scrapeTooltip()}
		>
			<Download size={18} class="nav-icon" />
			{#if !collapsed}
				<span class="nav-text">{m.sidebar_scrape()}</span>
			{/if}
		</button>
	</div>

	<!-- DEVELOP Section -->
	<div class="section">
		{#if !collapsed}
			<p class="section-label">{m.sidebar_develop()}</p>
		{/if}

		<button
			class="nav-item"
			class:active={isActive('api')}
			on:click={() => setView('api')}
			use:tooltip={collapsed ? m.sidebar_api() : m.sidebar_apiTooltip()}
		>
			<Code size={18} class="nav-icon" />
			{#if !collapsed}
				<span class="nav-text">{m.sidebar_api()}</span>
			{/if}
		</button>
	</div>

	<!-- Spacer to push footer to bottom -->
	<div class="spacer"></div>

	<!-- Footer with Credits and Profile -->
	<div class="sidebar-footer">
		{#if $authStore.user && import.meta.env.PUBLIC_DEPLOYMENT_TARGET !== 'supabase'}
			<div class="credits-display" class:hidden={collapsed}>
				<span class="credits-value">{$authStore.user.credits}</span>
				<span class="credits-label">{m.sidebar_credits()}</span>
			</div>
		{/if}

		<div class="profile-actions">
			<button
				class="settings-btn"
				on:click={() => dispatch('openPreferences')}
				use:tooltip={m.sidebar_preferencesTooltip()}
			>
				<Settings size={18} />
			</button>
			<button
				class="settings-btn"
				on:click={handleSignOut}
				use:tooltip={'Sign out'}
			>
				<LogOut size={18} />
			</button>
		</div>
	</div>

	<!-- Replay onboarding (hidden for now)
	{#if !collapsed}
		<div class="dev-replay-row">
			<button class="dev-replay-btn" on:click={replayOnboarding}>
				Replay onboarding
			</button>
		</div>
	{/if}
	-->

	<div class="sidebar-attribution" class:hidden={collapsed}>
		<span>built by <a href="https://buriedsignals.com" target="_blank" rel="noopener noreferrer">Buried Signals</a></span>
		<a href="/terms" class="terms-link">Terms</a>
	</div>
</div>

<style>
	/* Sidebar — editorial, hairline, sharp edges */
	.sidebar {
		display: flex;
		flex-direction: column;
		width: 220px;
		height: 100%;
		background: var(--color-surface-alt);
		border-right: 1px solid var(--color-border);
		padding: 0;
		overflow-y: auto;
		transition: width 200ms ease;
		font-family: var(--font-body);
	}

	.sidebar.collapsed {
		width: 48px;
		overflow: hidden;
	}

	.sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 1rem;
		height: 53px;
		box-sizing: border-box;
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.sidebar.collapsed .sidebar-header {
		padding: 0 0.5rem;
		justify-content: center;
	}

	.logo-img {
		height: 2rem;
		width: auto;
		flex-shrink: 0;
		margin-top: -3px;
	}

	.section {
		padding: 1rem;
		border-bottom: 1px solid var(--color-border);
	}

	.sidebar.collapsed .section {
		padding: 0.5rem;
	}

	.section:last-of-type {
		border-bottom: none;
	}

	.section-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-secondary);
		margin: 0 0 0.75rem 0;
		padding-left: 0.25rem;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		width: 100%;
		padding: 0.5625rem 0.625rem;
		border: 1px solid transparent;
		background: transparent;
		color: var(--color-ink-muted);
		font-family: var(--font-body);
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
		transition: background 150ms ease, border-color 150ms ease, color 150ms ease;
		text-align: left;
		margin-bottom: 0.25rem;
	}

	.sidebar.collapsed .nav-item {
		justify-content: center;
		padding: 0.625rem 0;
		gap: 0;
	}

	.nav-item:hover:not(.disabled):not(.active) {
		background: var(--color-bg);
		border-color: var(--color-border);
		color: var(--color-ink);
	}

	.nav-item.active {
		background: var(--color-primary-soft);
		border-color: var(--color-primary);
		color: var(--color-primary-deep);
		font-weight: 600;
	}

	.nav-item.active :global(.nav-icon) {
		color: var(--color-primary);
	}

	:global(.nav-icon) {
		flex-shrink: 0;
		color: var(--color-ink-subtle);
		transition: color 150ms ease;
	}

	.nav-item:hover:not(.disabled):not(.active) :global(.nav-icon) {
		color: var(--color-ink-muted);
	}

	.nav-text {
		flex: 1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.sidebar-new-scout {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		width: 100%;
		padding: 0.625rem 0.75rem;
		border: 1px solid var(--color-ink);
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		text-align: left;
		cursor: pointer;
		margin-bottom: 0.5rem;
		background: var(--color-ink);
		color: var(--color-bg);
		transition: background 150ms ease, border-color 150ms ease;
	}

	.sidebar-new-scout:hover {
		background: var(--color-primary-deep);
		border-color: var(--color-primary-deep);
	}

	.sidebar.collapsed .sidebar-new-scout {
		justify-content: center;
		padding: 0.625rem 0;
		gap: 0;
	}

	.chevron-right {
		display: flex;
		align-items: center;
		margin-left: auto;
		color: var(--color-bg);
		opacity: 0.7;
	}

	.spacer {
		flex: 1;
	}

	.collapse-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: none;
		background: transparent;
		color: var(--color-ink-subtle);
		cursor: pointer;
		transition: background 150ms ease, color 150ms ease;
		flex-shrink: 0;
	}

	.collapse-toggle:hover {
		background: var(--color-surface);
		color: var(--color-ink);
	}

	.sidebar-footer {
		padding: 1rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.sidebar.collapsed .sidebar-footer {
		flex-direction: column;
		padding: 0.5rem;
		gap: 0.5rem;
	}

	.credits-display {
		display: flex;
		align-items: baseline;
		gap: 0.375rem;
		padding: 0.375rem 0.625rem;
		background: var(--color-secondary-soft);
		border: 1px solid var(--color-secondary);
		overflow: hidden;
		white-space: nowrap;
		opacity: 1;
		max-width: 140px;
		transition: opacity 200ms ease, max-width 200ms ease, padding 200ms ease;
	}

	.credits-display.hidden {
		opacity: 0;
		max-width: 0;
		padding: 0;
	}

	.credits-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-ink);
	}

	.credits-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-secondary);
	}

	.settings-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border: none;
		background: transparent;
		color: var(--color-ink-subtle);
		cursor: pointer;
		transition: background 150ms ease, color 150ms ease;
	}

	.settings-btn:hover {
		background: var(--color-primary-soft);
		color: var(--color-primary);
	}

	.profile-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.sidebar.collapsed .profile-actions {
		flex-direction: column;
		gap: 0.375rem;
	}

	.sidebar-attribution {
		padding: 0 1rem 0.75rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-family: var(--font-mono);
		font-size: 0.625rem;
		letter-spacing: 0.05em;
		color: var(--color-ink-subtle);
		white-space: nowrap;
		overflow: hidden;
		opacity: 1;
		max-height: 2rem;
		transition: opacity 200ms ease, max-height 200ms ease, padding 200ms ease;
	}

	.sidebar-attribution .terms-link {
		font-size: 0.625rem;
		color: var(--color-ink-subtle);
		text-decoration: none;
		font-weight: 500;
	}

	.sidebar-attribution .terms-link:hover {
		color: var(--color-primary);
	}

	.sidebar-attribution.hidden {
		opacity: 0;
		max-height: 0;
		padding: 0;
	}

	.sidebar-attribution a {
		color: var(--color-ink-subtle);
		text-decoration: none;
		font-weight: 500;
		transition: color 150ms ease;
	}

	.sidebar-attribution a:hover {
		color: var(--color-primary);
	}

	.dev-replay-row {
		padding: 0 1rem 0.5rem;
	}

	.dev-replay-btn {
		width: 100%;
		padding: 0.375rem 0.5rem;
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-secondary);
		background: transparent;
		border: 1px dashed var(--color-secondary);
		cursor: pointer;
		transition: background 150ms ease;
	}

	.dev-replay-btn:hover {
		background: var(--color-secondary-soft);
	}
</style>
