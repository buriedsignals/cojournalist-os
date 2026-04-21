<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import UnitRow from './UnitRow.svelte';
	import type { Unit, Scout } from '$lib/types/workspace';

	export let units: Unit[];
	export let loading: boolean;
	export let hasMore: boolean;
	export let filter: 'needs_review' | 'all' = 'needs_review';
	export let scopedToScout: Scout | null = null;
	export let totalCount = 0;
	export let needsReviewCount = 0;

	const dispatch = createEventDispatcher<{
		openUnit: { unit: Unit };
		verify: { id: string };
		reject: { id: string };
		filterChange: { filter: 'needs_review' | 'all' };
		loadMore: void;
	}>();

	$: headerTitle = scopedToScout ? `${scopedToScout.name} · Inbox` : 'Inbox';

	function handleFilter(next: 'needs_review' | 'all') {
		if (next === filter) return;
		dispatch('filterChange', { filter: next });
	}

	function handleOpen(event: CustomEvent<{ unit: Unit }>) {
		dispatch('openUnit', { unit: event.detail.unit });
	}

	function handleVerify(event: CustomEvent<{ id: string }>) {
		dispatch('verify', { id: event.detail.id });
	}

	function handleReject(event: CustomEvent<{ id: string }>) {
		dispatch('reject', { id: event.detail.id });
	}

	// --- IntersectionObserver infinite scroll ---

	let sentinel: HTMLDivElement | null = null;
	let observer: IntersectionObserver | null = null;

	function attachObserver(node: HTMLDivElement) {
		sentinel = node;
		if (typeof IntersectionObserver === 'undefined') return;
		observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting && hasMore && !loading) {
						dispatch('loadMore');
					}
				}
			},
			{ rootMargin: '200px 0px' }
		);
		observer.observe(node);
		return {
			destroy() {
				if (observer) {
					observer.disconnect();
					observer = null;
				}
				sentinel = null;
			}
		};
	}

	onDestroy(() => {
		if (observer) {
			observer.disconnect();
			observer = null;
		}
	});

	$: showEmpty = !loading && units.length === 0;
	$: showInitialSpinner = loading && units.length === 0;
</script>

<div class="inbox-wrapper">
	<div class="inbox-header">
		<div class="inbox-title-row">
			<h2 class="inbox-title">{headerTitle}</h2>
			<span class="inbox-subtitle">
				· {totalCount} {totalCount === 1 ? 'unit' : 'units'} · {needsReviewCount} need review
			</span>
		</div>
		<div class="inbox-filter">
			<button
				type="button"
				class="filter-pill needs-review"
				class:active={filter === 'needs_review'}
				on:click={() => handleFilter('needs_review')}
			>
				Needs review · {needsReviewCount}
			</button>
			<button
				type="button"
				class="filter-pill all"
				class:active={filter === 'all'}
				on:click={() => handleFilter('all')}
			>
				All · {totalCount}
			</button>
		</div>
	</div>

	<div class="inbox-list">
		{#if showInitialSpinner}
			<div class="list-loading">
				<Spinner size="md" />
			</div>
		{:else if showEmpty}
			<div class="empty-state">
				<span class="eyebrow eyebrow--secondary">Inbox</span>
				<div class="empty-illustration" aria-hidden="true">
					<svg class="empty-illustration__svg" width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
						<rect class="ill-tray" x="10" y="18" width="52" height="40" stroke-width="1.5" />
						<path class="ill-tray-lip" d="M10 40h14l3 6h18l3-6h14" stroke-width="1.5" stroke-linejoin="round" />
						<path class="ill-lines" d="M24 28h24M24 34h16" stroke-width="1.5" stroke-linecap="round" />
						<circle class="ill-badge" cx="54" cy="20" r="7" stroke-width="1.5" />
						<path class="ill-badge-hand" d="M54 17v3l2 1.5" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
					</svg>
				</div>
				<h3 class="empty-title">Your inbox is quiet</h3>
				<p class="empty-subtitle">
					Units will land here as your scouts collect them.<br />
					Kick off a run anytime from the <strong>Scouts</strong> panel.
				</p>
			</div>
		{:else}
			{#each units as unit (unit.id)}
				<UnitRow
					{unit}
					on:open={handleOpen}
					on:verify={handleVerify}
					on:reject={handleReject}
				/>
			{/each}
			<div class="scroll-sentinel" use:attachObserver></div>
			{#if loading}
				<div class="list-loading small">
					<Spinner size="sm" />
				</div>
			{/if}
		{/if}
	</div>
</div>

<style>
	.inbox-wrapper {
		display: flex;
		flex-direction: column;
	}

	.inbox-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1.5rem 2rem 0.75rem;
		flex-wrap: wrap;
	}

	.inbox-title-row {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		min-width: 0;
	}

	.inbox-title {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
	}

	.inbox-subtitle {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-ink-muted);
	}

	.inbox-filter {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
	}

	.filter-pill {
		display: inline-flex;
		align-items: center;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		font-weight: 500;
		padding: 0.3125rem 0.75rem;
		border-radius: var(--radius-pill);
		border: 1px solid var(--color-border);
		background: var(--color-surface-alt);
		color: var(--color-ink-muted);
		cursor: pointer;
		transition: background 150ms ease, border-color 150ms ease, color 150ms ease;
		white-space: nowrap;
	}

	.filter-pill:hover {
		background: var(--color-bg);
		border-color: var(--color-border-strong);
	}

	.filter-pill.needs-review.active {
		background: var(--color-secondary-soft);
		color: var(--color-secondary);
		border-color: var(--color-secondary);
	}

	.filter-pill.all.active {
		background: var(--color-primary-soft);
		color: var(--color-primary-deep);
		border-color: var(--color-primary);
	}

	.inbox-list {
		margin: 0 2rem 2rem;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 0;
		overflow: hidden;
	}

	.list-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 6rem;
	}

	.list-loading.small {
		height: 3rem;
	}

	.scroll-sentinel {
		height: 1px;
		width: 100%;
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		min-height: 22rem;
		padding: 3rem 2rem 3.5rem;
		gap: 0.5rem;
	}

	.empty-illustration {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-top: 0.75rem;
		margin-bottom: 1rem;
	}

	.ill-tray       { fill: var(--color-surface); stroke: var(--color-border); }
	.ill-tray-lip   { fill: var(--color-bg); stroke: var(--color-border-strong); }
	.ill-lines      { stroke: var(--color-border-strong); }
	.ill-badge      { fill: var(--color-secondary-soft); stroke: var(--color-secondary); }
	.ill-badge-hand { stroke: var(--color-secondary); }

	.empty-title {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
	}

	.empty-subtitle {
		font-family: var(--font-body);
		font-size: 0.875rem;
		line-height: 1.55;
		color: var(--color-ink-muted);
		margin: 0.375rem 0 0;
		max-width: 28rem;
	}

	.empty-subtitle strong {
		color: var(--color-ink);
		font-weight: 600;
	}
</style>
