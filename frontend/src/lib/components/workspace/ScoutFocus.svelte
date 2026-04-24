<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { MapPin, Tag, Calendar, Play, Trash2, ArrowLeft, X, Check } from 'lucide-svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import DemoBadge from '$lib/components/ui/DemoBadge.svelte';
	import { getScoutTypeDisplay } from '$lib/utils/scouts';
	import type { Scout } from '$lib/types/workspace';

	export let scout: Scout;
	export let running = false;
	export let confirmingDelete = false;
	export let deleting = false;
	export let totalScouts = 0;
	export let demo = false;

	const dispatch = createEventDispatcher<{
		back: void;
		run: { id: string };
		requestDelete: { id: string };
		confirmDelete: { id: string };
		cancelDelete: { id: string };
	}>();

	$: cfg = getScoutTypeDisplay(scout.type);

	function locationDisplay(loc: unknown): string | null {
		if (!loc || typeof loc !== 'object') return null;
		const rec = loc as Record<string, unknown>;
		const dn = rec.displayName ?? rec.display_name;
		return typeof dn === 'string' ? dn : null;
	}

	$: locDisplay = locationDisplay(scout.location);

	function timeSince(iso: string | null | undefined): string | null {
		if (!iso) return null;
		const then = new Date(iso).getTime();
		if (!Number.isFinite(then)) return null;
		const seconds = Math.floor((Date.now() - then) / 1000);
		if (seconds < 60) return `${seconds}s ago`;
		if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
		if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
		const days = Math.floor(seconds / 86400);
		return days === 1 ? '1d ago' : `${days}d ago`;
	}

	$: lastRunLabel = scout.last_run?.started_at ? `Last run ${timeSince(scout.last_run.started_at)}` : 'Awaiting first run';
	$: articleCount = scout.last_run?.articles_count ?? null;

	$: scheduleLabel = (() => {
		if (!scout.regularity) return null;
		const r = scout.regularity.toLowerCase();
		if (r === 'daily') return 'Daily';
		if (r === 'weekly') return 'Weekly';
		if (r === 'monthly') return 'Monthly';
		return r.charAt(0).toUpperCase() + r.slice(1);
	})();

	$: status = (() => {
		if (!scout.last_run?.started_at) return { variant: 'waiting' as const, label: 'Awaiting first run' };
		if (scout.last_run.status === 'failed' || scout.last_run.status === 'error')
			return { variant: 'error' as const, label: 'Run failed' };
		if ((scout.last_run.articles_count ?? 0) > 0)
			return { variant: 'success' as const, label: 'New findings' };
		return { variant: 'neutral' as const, label: 'No new findings' };
	})();

	function handleBack() { dispatch('back'); }
</script>

<div class="scout-focus-wrapper">
	<button class="back-btn" on:click={handleBack}>
		<ArrowLeft size={14} strokeWidth={2.25} />
		<span>All scouts</span>
		{#if totalScouts}
			<span class="back-btn-count">{totalScouts}</span>
		{/if}
	</button>

	<div class="scout-shell scout-focus {cfg.className}">
		<div class="scout-shell-eyebrow-row">
			<span class="scout-shell-eyebrow {cfg.className}">
				<span class="scout-shell-eyebrow-icon">
					<svelte:component this={cfg.icon} size={12} />
				</span>
				<span class="scout-shell-eyebrow-label">{cfg.label}</span>
			</span>
			{#if demo}
				<div class="scout-shell-actions">
					<DemoBadge label="EXAMPLE · READ-ONLY" />
				</div>
			{:else}
			<div class="scout-shell-actions">
				{#if running}
					<div class="scout-shell-spinner"><Spinner size="sm" /></div>
				{:else}
					<button
						class="scout-shell-icon-btn run-btn"
						on:click={() => dispatch('run', { id: scout.id })}
						aria-label="Run now"
					>
						<Play size={14} />
					</button>
				{/if}
				{#if confirmingDelete}
					<div class="scout-shell-confirm">
						{#if deleting}
							<Spinner size="sm" />
						{:else}
							<button class="scout-shell-confirm-btn cancel" on:click={() => dispatch('cancelDelete', { id: scout.id })} aria-label="Cancel">
								<X size={12} />
							</button>
							<span class="scout-shell-confirm-label">Delete?</span>
							<button class="scout-shell-confirm-btn confirm" on:click={() => dispatch('confirmDelete', { id: scout.id })} aria-label="Yes">
								<Check size={12} />
							</button>
						{/if}
					</div>
				{:else}
					<button
						class="scout-shell-icon-btn trash-btn"
						on:click={() => dispatch('requestDelete', { id: scout.id })}
						aria-label="Delete"
					>
						<Trash2 size={14} />
					</button>
				{/if}
			</div>
			{/if}
		</div>

		<h2 class="scout-shell-name scout-focus-name">{scout.name}</h2>

		<div class="focus-meta-row">
			{#if locDisplay}
				<span class="focus-meta-item">
					<MapPin size={12} />
					{locDisplay}
				</span>
				<span class="focus-sep">·</span>
			{/if}
			{#if scout.criteria}
				<span class="focus-meta-item">
					<Tag size={12} />
					{scout.criteria}
				</span>
				<span class="focus-sep">·</span>
			{/if}
			<span class="focus-meta-item">
				<Calendar size={12} />
				{lastRunLabel}
			</span>
			{#if scheduleLabel}
				<span class="focus-sep">·</span>
				<span class="scout-shell-schedule">{scheduleLabel}</span>
			{/if}
		</div>

		{#if scout.last_run?.started_at}
			<div class="summary-strip">
				<p class="summary-label">Last run summary</p>
				{#if scout.last_run.status === 'failed' || scout.last_run.status === 'error'}
					<p class="summary-body error">The last run encountered an error. Check logs or retry.</p>
				{:else if articleCount !== null && articleCount > 0}
					<p class="summary-body">Found <strong>{articleCount}</strong> new {articleCount === 1 ? 'finding' : 'findings'} in the most recent run.</p>
				{:else}
					<p class="summary-body neutral">No new findings in the most recent run.</p>
				{/if}
			</div>
		{/if}

		<div class="focus-footer">
			<span
				class="scout-shell-status"
				class:status-success={status.variant === 'success'}
				class:status-error={status.variant === 'error'}
				class:status-waiting={status.variant === 'waiting'}
				class:status-neutral={status.variant === 'neutral'}
			>
				<span class="scout-shell-status-dot"></span>
				{status.label}
			</span>
			{#if scout.consecutive_failures && scout.consecutive_failures > 0}
				<span class="failure-note">{scout.consecutive_failures} consecutive failure{scout.consecutive_failures === 1 ? '' : 's'}</span>
			{/if}
		</div>
	</div>
</div>

<style>
	/* Focus-specific overrides — shell primitives live in app.css under
	   "Scout display primitives"; this file only carries the larger
	   title size, the meta row, summary strip, and back-chip above. */
	.scout-focus-wrapper {
		padding: 0 2rem;
		margin-top: 1.25rem;
		margin-bottom: 1.5rem;
		font-family: var(--font-body);
	}

	.back-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4375rem;
		height: 32px;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-ink-muted);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		cursor: pointer;
		padding: 0 0.75rem;
		margin-bottom: 0.875rem;
		transition: border-color 150ms ease, color 150ms ease, background 150ms ease;
	}
	.back-btn:hover {
		color: var(--color-primary);
		border-color: var(--color-primary);
		background: var(--color-primary-soft);
	}
	.back-btn-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.25rem;
		padding: 0 0.375rem;
		height: 1.125rem;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--color-ink-muted);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		margin-left: 0.125rem;
	}
	.back-btn:hover .back-btn-count {
		background: var(--color-bg);
		color: var(--color-primary);
	}

	.scout-focus {
		overflow: hidden;
		padding: 0.875rem 1.25rem 1rem;
	}

	.scout-focus-name {
		font-size: 1.5rem;
	}

	.focus-meta-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.04em;
		color: var(--color-ink-muted);
		flex-wrap: wrap;
	}

	.focus-meta-item {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}

	.focus-sep { color: var(--color-border-strong); }

	.summary-strip {
		margin-top: 0.875rem;
		padding: 0.75rem 0.875rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
	}

	.summary-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		color: var(--color-secondary);
		text-transform: uppercase;
		margin: 0 0 0.375rem 0;
	}

	.summary-body {
		font-family: var(--font-body);
		font-size: 0.9375rem;
		color: var(--color-ink);
		line-height: 1.55;
		margin: 0;
	}
	.summary-body.error   { color: var(--color-error); }
	.summary-body.neutral { color: var(--color-ink-muted); font-weight: 300; }

	.focus-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}

	.failure-note {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.05em;
		color: var(--color-error);
		font-weight: 500;
	}
</style>
