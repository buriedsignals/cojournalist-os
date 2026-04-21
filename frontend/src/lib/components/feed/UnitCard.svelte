<script lang="ts">
	import type { InformationUnit } from '$lib/api-client';
	import { CheckSquare, Square, ExternalLink, Clock } from 'lucide-svelte';
	import { onMount, tick } from 'svelte';
	import * as m from '$lib/paraglide/messages';

	export let unit: InformationUnit;
	export let selected = false;
	export let similarityScore: number | undefined = undefined;
	export let onToggle: (unitId: string) => void;

	let statementEl: HTMLParagraphElement;
	let isTruncated = false;

	function checkTruncation() {
		if (statementEl) {
			isTruncated = statementEl.scrollHeight > statementEl.clientHeight + 1;
		}
	}

	onMount(() => checkTruncation());
	$: if (unit && statementEl) { tick().then(checkTruncation); }

	const MAX_ENTITIES = 3;

	function formatScoutType(scoutType: string): string {
		switch (scoutType) {
			case 'pulse': return m.feed_smartMonitor();
			case 'web': return m.feed_pageMonitor();
			case 'social': return m.scoutType_socialMonitor();
			case 'civic': return m.scoutType_civicMonitor();
			default: return scoutType;
		}
	}

	function getTypeTagClass(scoutType: string): string {
		switch (scoutType) {
			case 'web': return 'type-tag-web';
			case 'pulse': return 'type-tag-pulse';
			case 'social': return 'type-tag-social';
			case 'civic': return 'type-tag-civic';
			default: return '';
		}
	}

	function formatRelativeTime(isoString: string): string {
		const date = new Date(isoString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);
		const diffDays = Math.floor(diffMs / 86400000);

		if (diffMins < 60) return m.feed_timeMinutesAgo({ count: diffMins });
		if (diffHours < 24) return m.feed_timeHoursAgo({ count: diffHours });
		if (diffDays < 7) return m.feed_timeDaysAgo({ count: diffDays });
		return date.toLocaleDateString();
	}

	$: visibleEntities = (unit.entities || []).slice(0, MAX_ENTITIES);
	$: overflowCount = Math.max(0, (unit.entities || []).length - MAX_ENTITIES);
</script>

<button
	class="unit-card"
	class:selected
	on:click={() => onToggle(unit.unit_id)}
>
	<div class="card-header">
		<div class="check">
			{#if selected}
				<CheckSquare size={14} />
			{:else}
				<Square size={14} />
			{/if}
		</div>
		<span class="type-tag {getTypeTagClass(unit.scout_type)}">{formatScoutType(unit.scout_type)}</span>
	</div>

	<p class="statement" class:truncated={isTruncated} bind:this={statementEl}>{unit.statement}</p>

	{#if visibleEntities.length > 0}
		<div class="entities">
			{#each visibleEntities as entity}
				<span class="entity-chip">{entity}</span>
			{/each}
			{#if overflowCount > 0}
				<span class="entity-chip overflow">{m.feed_moreEntities({ count: overflowCount })}</span>
			{/if}
		</div>
	{/if}

	<div class="card-footer">
		<a
			href={unit.source_url}
			target="_blank"
			rel="noopener noreferrer"
			on:click|stopPropagation
			class="source-link"
		>
			<ExternalLink size={10} />
			{unit.source_domain || 'source'}
		</a>
		{#if similarityScore !== undefined}
			<span class="score-pill">{m.feed_matchScore({ score: Math.round(similarityScore * 100) })}</span>
		{/if}
		<span class="time-tag">
			<Clock size={10} />
			{formatRelativeTime(unit.created_at)}
		</span>
	</div>
</button>

<style>
	.unit-card {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		padding: 0.75rem;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 10px;
		text-align: left;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.unit-card:hover {
		border-color: var(--color-border-strong);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
	}

	.unit-card.selected {
		border-color: #818cf8;
		background: var(--color-primary-soft);
		box-shadow: 0 0 0 1px #818cf8;
	}

	.card-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.check {
		color: var(--color-border-strong);
	}

	.unit-card.selected .check {
		color: #6366f1;
	}

	.type-tag {
		font-size: 0.5625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 0.125rem 0.3125rem;
		border-radius: 3px;
		color: var(--color-ink-muted);
		background: var(--color-surface);
	}

	.type-tag-web { color: #1d4ed8; background: var(--color-primary-soft); }
	.type-tag-pulse { color: #ea580c; background: #ffedd5; }
	.type-tag-social { color: var(--color-primary); background: var(--color-primary-soft); }
	.type-tag-civic { color: #059669; background: #d1fae5; }

	.statement {
		position: relative;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-ink);
		margin: 0;
		line-height: 1.45;
		display: -webkit-box;
		-webkit-line-clamp: 4;
		line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
		flex: 1;
	}

	.statement.truncated::after {
		content: '';
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 1.25em;
		background: linear-gradient(transparent, white);
		pointer-events: none;
	}

	.unit-card.selected .statement.truncated::after {
		background: linear-gradient(transparent, #f5f3ff);
	}

	.entities {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}

	.entity-chip {
		font-size: 0.6875rem;
		color: var(--color-ink-muted);
		background: var(--color-surface);
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		white-space: nowrap;
	}

	.entity-chip.overflow {
		color: var(--color-ink-subtle);
		background: transparent;
		padding-left: 0.25rem;
	}

	.card-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.625rem;
		margin-top: auto;
	}

	.source-link {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.6875rem;
		color: var(--color-ink-muted);
		text-decoration: none;
	}

	.source-link:hover {
		color: #6366f1;
	}

	.time-tag {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.6875rem;
		color: var(--color-ink-subtle);
		margin-left: auto;
	}

	.score-pill {
		font-size: 0.625rem;
		font-weight: 600;
		color: #059669;
		background: #d1fae5;
		padding: 0.125rem 0.375rem;
		border-radius: 9999px;
		margin-left: auto;
	}
</style>
