<script lang="ts">
import { authStore } from '$lib/stores/auth';
import { sidebarNav } from '$lib/stores/sidebar-nav';
import Spinner from '$lib/components/ui/Spinner.svelte';
import UnifiedSidebar from '$lib/components/sidebars/UnifiedSidebar.svelte';
import ScoutsPanel from '$lib/components/panels/ScoutsPanel.svelte';
import ScrapeView from '$lib/components/views/ScrapeView.svelte';
import SmartScoutView from '$lib/components/news/SmartScoutView.svelte';
import PageScoutView from '$lib/components/news/PageScoutView.svelte';
import SocialScoutView from '$lib/components/news/SocialScoutView.svelte';
import CivicScoutView from '$lib/components/news/CivicScoutView.svelte';
import FeedView from '$lib/components/feed/FeedView.svelte';
import ApiView from '$lib/components/views/ApiView.svelte';
import PreferencesModal from '$lib/components/modals/PreferencesModal.svelte';
import * as m from '$lib/paraglide/messages';
	let showPreferencesModal = false;
	let disclaimerDismissed = typeof localStorage !== 'undefined' && localStorage.getItem('ai-disclaimer-dismissed') === 'true';

	function dismissDisclaimer() {
		disclaimerDismissed = true;
		localStorage.setItem('ai-disclaimer-dismissed', 'true');
	}

</script>

{#if $authStore.authenticated}
<div class="h-screen flex bg-gray-50">
	<!-- Unified Sidebar -->
	<aside class="sidebar-container">
		<UnifiedSidebar on:openPreferences={() => showPreferencesModal = true} />
	</aside>

	<!-- Main Content Area - All views mounted, visibility toggled for state persistence -->
	<main class="main-content">
		{#if !disclaimerDismissed}
		<div class="ai-disclaimer-banner">
			<span>{m.disclaimer_aiGenerated()}</span>
			<button class="dismiss-btn" on:click={dismissDisclaimer}>&times;</button>
		</div>
		{/if}
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'scouts'}>
			<ScoutsPanel />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'location-scout' && $sidebarNav.activeView !== 'beat-scout'}>
			<SmartScoutView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'page-scout'}>
			<PageScoutView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'social-scout'}>
			<SocialScoutView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'civic-scout'}>
			<CivicScoutView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'extract'}>
			<ScrapeView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'feed'}>
			<FeedView />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'api'}>
			<ApiView />
		</div>
	</main>
</div>
{:else}
	<!-- Loading state while auth initializes -->
	<div class="h-screen flex items-center justify-center bg-gray-50">
		<Spinner size="lg" />
	</div>
{/if}

<!-- Preferences Modal -->
<PreferencesModal open={showPreferencesModal} on:close={() => showPreferencesModal = false} />

<style>
	:global(body) {
		font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
	}

	:global(.gradient-text) {
		background: linear-gradient(to right, #968bdf, #7c6fc7);
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
	}

	.sidebar-container {
		flex-shrink: 0;
		height: 100%;
		transition: width 200ms ease;
	}

	.main-content {
		flex: 1;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.view-container {
		display: flex;
		flex-direction: column;
		height: 100%;
		width: 100%;
	}

	.view-container.hidden {
		display: none;
	}

	.ai-disclaimer-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		background: rgba(245, 158, 11, 0.06);
		border: 1px solid rgba(245, 158, 11, 0.15);
		border-radius: 0.5rem;
		font-size: 0.8rem;
		color: #57534e;
		margin-bottom: 1rem;
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: #a8a29e;
		cursor: pointer;
		font-size: 1.1rem;
		padding: 0 0.25rem;
		line-height: 1;
	}

	.dismiss-btn:hover {
		color: #57534e;
	}
</style>
