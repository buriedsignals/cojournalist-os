<script lang="ts">
	import type { InformationUnit } from '$lib/api-client';
	import { Newspaper, Search } from 'lucide-svelte';
	import UnitCard from './UnitCard.svelte';
	import PanelPlaceholder from '$lib/components/ui/PanelPlaceholder.svelte';
	import ConstellationGraphic from '$lib/components/ui/ConstellationGraphic.svelte';
	import * as m from '$lib/paraglide/messages';

	export let units: InformationUnit[];
	export let selectedUnitIds: Set<string>;
	export let loading = false;
	export let hasFilters = false;
	export let hasUnfilteredUnits = false;
	export let similarityScores: Map<string, number> = new Map();
	export let dimmed = false;
	export let showDemoBadge = false;

	export let onToggleUnit: (unitId: string) => void;

	let gridEl: HTMLDivElement;

	function handleCardEnter(e: MouseEvent) {
		const wrapper = e.currentTarget as HTMLElement;
		const top = Math.round(wrapper.getBoundingClientRect().top);
		if (!gridEl) return;
		for (let i = 0; i < gridEl.children.length; i++) {
			const child = gridEl.children[i] as HTMLElement;
			const childTop = Math.round(child.getBoundingClientRect().top);
			if (Math.abs(childTop - top) < 2) {
				child.classList.add('row-hovered');
			} else {
				child.classList.remove('row-hovered');
			}
		}
	}

	function handleGridLeave() {
		if (!gridEl) return;
		for (let i = 0; i < gridEl.children.length; i++) {
			(gridEl.children[i] as HTMLElement).classList.remove('row-hovered');
		}
	}

	function handleScroll() {
		handleGridLeave();
	}
</script>

<div class="unit-grid-container" class:dimmed on:scroll={handleScroll}>
	{#if loading}
		<PanelPlaceholder loading loadingText={m.feed_loadingUnits()} />
	{:else if hasFilters && units.length === 0 && !hasUnfilteredUnits}
		<PanelPlaceholder title={m.feed_noUnitsLocation()} hint={m.feed_runScoutsHint()}>
			<ConstellationGraphic slot="graphic" />
		</PanelPlaceholder>
	{:else if hasFilters && units.length === 0 && hasUnfilteredUnits}
		<PanelPlaceholder title={m.feed_noMatchingUnits()} hint={m.feed_adjustFiltersHint()}>
			<ConstellationGraphic slot="graphic" />
		</PanelPlaceholder>
	{:else if units.length > 0}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="grid" bind:this={gridEl} on:mouseleave={handleGridLeave}>
			{#each units as unit (unit.unit_id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="card-wrapper" on:mouseenter={handleCardEnter}>
					{#if showDemoBadge}
						<span class="demo-badge">{m.tour_demoBadge()}</span>
					{/if}
					<UnitCard
						{unit}
						selected={selectedUnitIds.has(unit.unit_id)}
						similarityScore={similarityScores.get(unit.unit_id)}
						onToggle={onToggleUnit}
					/>
				</div>
			{/each}
		</div>
	{:else}
		<PanelPlaceholder title={m.feed_noDataYet()} subtitle="{m.feed_searchAllUnits()} {m.feed_orSelectFilter()}">
			<ConstellationGraphic slot="graphic" />
		</PanelPlaceholder>
	{/if}
</div>

<style>
	.unit-grid-container {
		flex: 1;
		overflow-y: auto;
		padding-bottom: 2rem;
		transition: opacity 0.3s ease;
	}

	.unit-grid-container.dimmed {
		opacity: 0.4;
		pointer-events: none;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 0.625rem;
		padding: 1rem 1.25rem;
	}

	.card-wrapper {
		display: flex;
		min-width: 0;
		position: relative;
	}

	.demo-badge {
		position: absolute;
		top: 0.375rem;
		left: 50%;
		transform: translateX(-50%);
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

	.card-wrapper :global(.unit-card) {
		flex: 1;
	}

	/* Unclamp text when row is hovered (row-hovered added via JS) */
	:global(.card-wrapper.row-hovered .statement) {
		-webkit-line-clamp: unset;
		line-clamp: unset;
	}

	/* Hide truncation gradient when expanded */
	:global(.card-wrapper.row-hovered .statement.truncated::after) {
		display: none;
	}

</style>
