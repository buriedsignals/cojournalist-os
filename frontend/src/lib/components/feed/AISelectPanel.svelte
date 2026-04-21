<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { MapPin, Tag, Calendar } from 'lucide-svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import * as m from '$lib/paraglide/messages';

	export let location: string | null = null;
	export let topic: string | null = null;
	export let loading = false;

	let prompt = '';
	let activeButton: 'location' | 'topic' | 'date' | null = null;
	let tooltipMessage: string | null = null;

	const dispatch = createEventDispatcher<{
		run: { prompt: string };
		close: void;
	}>();

	function handleButtonClick(type: 'location' | 'topic' | 'date') {
		if (loading) return;
		tooltipMessage = null;

		// Guard: location/topic buttons require their respective data
		if (type === 'location' && !location) {
			tooltipMessage = m.export_aiSelectNoLocation();
			activeButton = null;
			prompt = '';
			return;
		}
		if (type === 'topic' && !topic) {
			tooltipMessage = m.export_aiSelectNoTopic();
			activeButton = null;
			prompt = '';
			return;
		}

		activeButton = type;
		if (type === 'location') {
			prompt = m.export_aiSelectLocationPrompt();
		} else if (type === 'topic') {
			prompt = m.export_aiSelectTopicPrompt();
		} else {
			prompt = m.export_aiSelectDefaultPrompt();
		}
	}

	function handleRun() {
		dispatch('run', { prompt });
	}

	function handleReset() {
		prompt = '';
		activeButton = null;
		tooltipMessage = null;
	}
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="backdrop" on:click={() => dispatch('close')}></div>
<div class="ai-prompt-dropdown">
	<div class="button-row">
		<button
			class="quick-btn"
			class:active={activeButton === 'location'}
			class:unavailable={!location}
			on:click={() => handleButtonClick('location')}
		>
			<div class="btn-icon location">
				<MapPin size={16} />
			</div>
			<span class="btn-label">{m.export_aiSelectByLocation()}</span>
			<span class="btn-desc">
				{#if location}
					{m.export_aiSelectLocationDesc({ location })}
				{:else}
					{m.export_aiSelectNoLocation()}
				{/if}
			</span>
		</button>

		<button
			class="quick-btn"
			class:active={activeButton === 'topic'}
			class:unavailable={!topic}
			on:click={() => handleButtonClick('topic')}
		>
			<div class="btn-icon topic">
				<Tag size={16} />
			</div>
			<span class="btn-label">{m.export_aiSelectByTopic()}</span>
			<span class="btn-desc">
				{#if topic}
					{m.export_aiSelectTopicDesc({ topic })}
				{:else}
					{m.export_aiSelectNoTopic()}
				{/if}
			</span>
		</button>

		<button
			class="quick-btn"
			class:active={activeButton === 'date'}
			on:click={() => handleButtonClick('date')}
		>
			<div class="btn-icon date">
				<Calendar size={16} />
			</div>
			<span class="btn-label">{m.export_aiSelectByDate()}</span>
			<span class="btn-desc">{m.export_aiSelectDateDesc()}</span>
		</button>
	</div>

	{#if tooltipMessage}
		<div class="tooltip-row">
			<span>{tooltipMessage}</span>
		</div>
	{/if}

	{#if activeButton}
		{#if location || topic}
			<div class="filter-context">
				{#if location}
					<span class="filter-pill">
						<MapPin size={11} />
						{location}
					</span>
				{/if}
				{#if topic}
					<span class="filter-pill">
						<Tag size={11} />
						{topic}
					</span>
				{/if}
			</div>
		{/if}
		<textarea
			id="ai-select-prompt"
			bind:value={prompt}
			rows="3"
			class="prompt-input"
			disabled={loading}
		></textarea>

		<div class="panel-actions">
			<button class="reset-link" on:click={handleReset} disabled={loading}>
				{m.export_aiSelectResetPrompt()}
			</button>
			<button class="btn-primary" on:click={handleRun} disabled={loading}>
				{#if loading}
					<Spinner size="sm" />
				{/if}
				{loading ? m.export_aiSelectRunning() : m.export_aiSelectRun()}
			</button>
		</div>
	{/if}
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 49;
		cursor: pointer;
	}

	.ai-prompt-dropdown {
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 8px;
		width: 420px;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 12px;
		padding: 12px 14px 14px;
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
		z-index: 51;
		animation: slideDown 0.15s ease-out;
	}

	@keyframes slideDown {
		from { opacity: 0; transform: translateY(-4px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.button-row {
		display: flex;
		gap: 8px;
		margin-bottom: 10px;
	}

	.quick-btn {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 14px 8px 12px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 10px;
		cursor: pointer;
		transition: all 0.15s ease;
		text-align: center;
		min-width: 0;
	}

	.quick-btn:hover {
		background: #f3f0ff;
		border-color: #c4b5fd;
	}

	.quick-btn.active {
		background: #f3f0ff;
		border-color: #818cf8;
	}

	.quick-btn.unavailable {
		opacity: 0.55;
	}

	.quick-btn.unavailable:hover {
		background: var(--color-bg);
		border-color: var(--color-border-strong);
	}

	.btn-icon {
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		flex-shrink: 0;
	}

	.btn-icon.location {
		background: #eff6ff;
		color: #3b82f6;
	}

	.btn-icon.topic {
		background: #f0fdf4;
		color: #22c55e;
	}

	.btn-icon.date {
		background: var(--color-secondary-soft);
		color: #9F6016;
	}

	.btn-label {
		font-size: 12px;
		font-weight: 600;
		color: var(--color-ink);
		line-height: 1.2;
	}

	.btn-desc {
		font-size: 10.5px;
		color: var(--color-ink-muted);
		line-height: 1.3;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.tooltip-row {
		margin-bottom: 8px;
		padding: 6px 10px;
		background: var(--color-secondary-soft);
		border-radius: 6px;
		font-size: 11px;
		color: var(--color-secondary);
		text-align: center;
	}

	.filter-context {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 8px;
	}

	.filter-pill {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px 8px;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		font-size: 11px;
		color: var(--color-ink);
	}

	.prompt-input {
		width: 100%;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 8px 10px;
		font-size: 12px;
		line-height: 1.5;
		resize: vertical;
		background: var(--color-bg);
		color: var(--color-ink);
		box-sizing: border-box;
	}

	.prompt-input:focus {
		outline: none;
		border-color: #818cf8;
		box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.15);
	}

	.prompt-input:disabled {
		opacity: 0.6;
	}

	.panel-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 10px;
	}

	.reset-link {
		background: none;
		border: none;
		color: var(--color-ink-muted);
		font-size: 11px;
		cursor: pointer;
		padding: 4px 0;
		text-decoration: underline;
	}

	.reset-link:hover {
		color: var(--color-ink);
	}
</style>
