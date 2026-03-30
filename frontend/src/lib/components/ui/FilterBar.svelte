<script lang="ts">
	import { Search, X, RefreshCw } from 'lucide-svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import * as m from '$lib/paraglide/messages';

	export let onRefresh: (() => void) | undefined = undefined;
	export let isRefreshing = false;

	// Search (optional)
	export let searchEnabled = false;
	export let searchQuery = '';
	export let searchPlaceholder = 'Search...';
	export let onSearch: ((query: string) => void) | undefined = undefined;
	export let isSearching = false;

	let searchTimer: ReturnType<typeof setTimeout>;

	function handleSearchInput(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		searchQuery = value;
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => onSearch?.(value), 300);
	}

	function clearSearch() {
		searchQuery = '';
		onSearch?.('');
	}
</script>

{#if searchEnabled}
	<div class="filter-bar">
		<div class="filters-left"><slot /></div>

		<div class="search-divider"></div>

		<div class="search-field" class:searching={isSearching}>
			<Search size={14} class="search-icon" />
			<input
				type="text"
				value={searchQuery}
				on:input={handleSearchInput}
				placeholder={searchPlaceholder}
			/>
			{#if searchQuery}
				<button class="clear-btn" on:click={clearSearch} aria-label={m.filterBar_clearSearch()}>
					<X size={12} />
				</button>
			{/if}
			{#if isSearching}
				<Spinner size="sm" />
			{/if}
		</div>

		{#if $$slots.toolbar}
			<div class="filters-right"><slot name="toolbar" /></div>
		{/if}
	</div>
{:else}
	<div class="filter-bar">
		{#if onRefresh}
			<button
				class="refresh-btn"
				on:click={onRefresh}
				disabled={isRefreshing}
				aria-label={m.filterBar_refresh()}
			>
				{#if isRefreshing}
				<Spinner size="sm" />
			{:else}
				<RefreshCw size={14} />
			{/if}
			</button>
		{/if}

		<div class="filters-inline">
			<slot />
		</div>
	</div>
{/if}

<style>
	.filter-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0 1.25rem;
		height: 53px;
		box-sizing: border-box;
		background: #fafbfc;
		border-bottom: 1px solid #e5e7eb;
		position: relative;
		overflow: visible;
	}

	.filters-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.filters-right {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-shrink: 0;
	}

	/* Single row inline filters (no search) */
	.filters-inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.filters-inline :global(.filter-select) {
		max-width: min(220px, 35vw);
	}

	.refresh-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 6px;
		color: #6b7280;
		cursor: pointer;
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.refresh-btn:hover:not(:disabled) {
		background: #f3f4f6;
		color: #374151;
		border-color: #d1d5db;
	}

	.refresh-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.search-divider {
		width: 1px;
		height: 20px;
		background: #d1d5db;
		flex-shrink: 0;
	}

	/* Inline search field */
	.search-field {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		flex: 1;
		max-width: 440px;
		min-width: 180px;
		min-width: 0;
		padding: 0.375rem 0.625rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 6px;
		transition: all 0.15s ease;
	}

	.search-field:focus-within {
		border-color: #6366f1;
		box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
	}

	.search-field.searching {
		border-color: #6366f1;
	}

	.search-field :global(.search-icon) {
		color: #9ca3af;
		flex-shrink: 0;
	}

	.search-field input {
		flex: 1;
		min-width: 0;
		border: none;
		background: transparent;
		font-size: 0.8125rem;
		color: #374151;
		outline: none;
	}

	.search-field input::placeholder {
		color: #9ca3af;
	}

	.clear-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		background: #f3f4f6;
		border: none;
		border-radius: 50%;
		color: #6b7280;
		cursor: pointer;
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.clear-btn:hover {
		background: #e5e7eb;
		color: #374151;
	}

</style>
