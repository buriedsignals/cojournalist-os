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
	let showPreferencesModal = false;

</script>

{#if $authStore.authenticated}
<div class="h-screen flex bg-gray-50">
	<!-- Unified Sidebar -->
	<aside class="sidebar-container">
		<UnifiedSidebar on:openPreferences={() => showPreferencesModal = true} />
	</aside>

	<!-- Main Content Area - All views mounted, visibility toggled for state persistence -->
	<main class="main-content">
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'scouts'}>
			<ScoutsPanel />
		</div>
		<div class="view-container" class:hidden={$sidebarNav.activeView !== 'pulse'}>
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
</style>
