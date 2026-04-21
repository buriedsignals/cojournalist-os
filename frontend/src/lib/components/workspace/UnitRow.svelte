<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ExternalLink, Check, X } from 'lucide-svelte';
	import type { Unit } from '$lib/types/workspace';
	import { isDemoId } from '$lib/demo/seed';
	import DemoBadge from '$lib/components/ui/DemoBadge.svelte';
	import { cleanUnitStatement, getUnitTypeStyle } from '$lib/utils/units';

	export let unit: Unit;
	export let selected = false;

	$: isDemo = isDemoId(unit.id);

	const dispatch = createEventDispatcher<{
		open: { unit: Unit };
		verify: { id: string };
		reject: { id: string };
	}>();

	// --- Derived state ---

	$: verified = unit.verification?.verified === true;

	$: typeKey = (unit.unit_type ?? '').toUpperCase();

	$: typeStyle = getUnitTypeStyle(typeKey);

	function formatOccurred(iso: string | null | undefined): string | null {
		if (!iso) return null;
		const d = new Date(iso);
		if (!Number.isFinite(d.getTime())) return null;
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
	}

	function formatExtractedRel(iso: string | null | undefined): string | null {
		if (!iso) return null;
		const then = new Date(iso).getTime();
		if (!Number.isFinite(then)) return null;
		const seconds = Math.floor((Date.now() - then) / 1000);
		if (seconds < 60) return `${Math.max(seconds, 0)}s ago`;
		if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
		if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
		const days = Math.floor(seconds / 86400);
		return days === 1 ? '1d ago' : `${days}d ago`;
	}

	$: occurredLabel = formatOccurred(unit.occurred_at);
	$: extractedLabel = formatExtractedRel(unit.extracted_at);

	$: scoutName = unit.scout_name ?? '';
	$: sourceDomain = unit.source?.domain ?? '';
	$: sourceUrl = unit.source?.url ?? '';

	$: topEntities = (unit.entities ?? []).slice(0, 5);

	function handleRowClick() {
		dispatch('open', { unit });
	}

	function handleKey(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			dispatch('open', { unit });
		}
	}

	function handleVerify(event: MouseEvent) {
		event.stopPropagation();
		dispatch('verify', { id: unit.id });
	}

	function handleReject(event: MouseEvent) {
		event.stopPropagation();
		dispatch('reject', { id: unit.id });
	}
</script>

<div
	class="unit-row"
	class:selected
	class:verified
	on:click={handleRowClick}
	on:keydown={handleKey}
	role="button"
	tabindex="0"
>
	<div class="unit-meta">
		<span class="unit-type-badge" style="background:{typeStyle.background};color:{typeStyle.color}">
			{typeKey || 'UNIT'}
		</span>
		{#if scoutName}
			<span class="unit-scout-name">{scoutName}</span>
		{/if}
		{#if sourceDomain || occurredLabel || extractedLabel}
			<span class="unit-dates">
				{#if sourceDomain}
					<span>· {sourceDomain}</span>
				{/if}
				{#if occurredLabel}
					<span>· {occurredLabel}</span>
				{/if}
				{#if extractedLabel}
					<span>· {extractedLabel}</span>
				{/if}
			</span>
		{/if}
		{#if verified}
			<span class="review-pill verified">✓ Verified</span>
		{:else}
			<span class="review-pill">⚠ Needs review</span>
		{/if}
		{#if isDemo}
			<DemoBadge />
		{/if}
	</div>

	{#if unit.statement}
		<p class="unit-statement">{cleanUnitStatement(unit.statement)}</p>
	{/if}

	{#if topEntities.length > 0}
		<div class="unit-entities">
			{#each topEntities as entity (entity.mention_text + (entity.entity_id ?? ''))}
				<span class="entity-chip">{entity.mention_text}</span>
			{/each}
		</div>
	{/if}

	<div class="unit-actions" on:click|stopPropagation on:keydown|stopPropagation role="toolbar" tabindex="-1">
		{#if sourceUrl}
			<a
				class="unit-action-btn"
				href={sourceUrl}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open source"
				title="Open source"
			>
				<ExternalLink size={14} />
			</a>
		{/if}
		<button
			class="unit-action-btn verify"
			on:click={handleVerify}
			aria-label="Mark verified"
			title="Mark verified"
			type="button"
		>
			<Check size={14} strokeWidth={2.5} />
		</button>
		<button
			class="unit-action-btn reject"
			on:click={handleReject}
			aria-label="Mark as false"
			title="Mark as false"
			type="button"
		>
			<X size={14} strokeWidth={2.5} />
		</button>
	</div>
</div>

<style>
	.unit-row {
		display: flex;
		flex-direction: column;
		gap: 0.4375rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
		cursor: pointer;
		transition: background 150ms ease;
		position: relative;
		background: var(--color-surface-alt);
		font-family: var(--font-body);
	}

	.unit-row:hover {
		background: var(--color-bg);
	}

	.unit-row.selected {
		background: var(--color-primary-soft);
		border-left: 3px solid var(--color-primary);
		padding-left: calc(1.5rem - 3px);
	}

	.unit-row.verified {
		opacity: 0.55;
	}

	.unit-row:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}

	.unit-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.75rem;
		color: var(--color-ink-muted);
	}

	.unit-type-badge {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		padding: 0.125rem 0.4375rem;
		text-transform: uppercase;
		border: 1px solid currentColor;
	}

	.unit-scout-name {
		font-family: var(--font-mono);
		font-weight: 500;
		font-size: 0.6875rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--color-ink);
	}

	.unit-dates {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.04em;
		color: var(--color-ink-subtle);
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		flex-wrap: wrap;
	}

	.unit-statement {
		font-family: var(--font-body);
		font-size: 0.9375rem;
		font-weight: 400;
		line-height: 1.55;
		color: var(--color-ink);
		margin: 0;
	}

	.unit-entities {
		display: flex;
		gap: 0.3125rem;
		flex-wrap: wrap;
	}

	.entity-chip {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 400;
		letter-spacing: 0.04em;
		padding: 0.125rem 0.5rem;
		background: var(--color-surface);
		color: var(--color-ink-muted);
		border: 1px solid var(--color-border);
	}

	.review-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		padding: 0.1875rem 0.5rem;
		border-radius: var(--radius-pill);
		background: var(--color-secondary-soft);
		color: var(--color-secondary);
		border: 1px solid var(--color-secondary);
		margin-left: auto;
		white-space: nowrap;
	}

	.review-pill.verified {
		background: rgba(47, 143, 95, 0.12);
		color: var(--color-success);
		border-color: var(--color-success);
	}

	.unit-actions {
		position: absolute;
		top: 0.75rem;
		right: 1rem;
		display: none;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		padding: 0.25rem;
		box-shadow: var(--shadow-md);
		gap: 0.125rem;
	}

	.unit-row:hover .unit-actions {
		display: flex;
	}

	.unit-action-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border: 1px solid transparent;
		background: transparent;
		color: var(--color-ink-muted);
		cursor: pointer;
		transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
		text-decoration: none;
	}

	.unit-action-btn:hover {
		background: var(--color-surface);
		color: var(--color-ink);
	}

	.unit-action-btn.verify:hover {
		background: rgba(47, 143, 95, 0.12);
		color: var(--color-success);
		border-color: var(--color-success);
	}

	.unit-action-btn.reject:hover {
		background: rgba(179, 62, 46, 0.1);
		color: var(--color-error);
		border-color: var(--color-error);
	}
</style>
