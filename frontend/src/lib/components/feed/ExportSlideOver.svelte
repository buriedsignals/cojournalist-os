<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { onDestroy } from 'svelte';
	import type { ExportDraft } from '$lib/api-client';
	import { ChevronRight, AlertCircle, RefreshCw, PenTool, RotateCcw, ChevronDown, ChevronUp, Download, Info, Trash2 } from 'lucide-svelte';
	import ProgressIndicator from '$lib/components/ui/ProgressIndicator.svelte';
	import { feedStore } from '$lib/stores/feed';
	import { boldify, linkifySources } from '$lib/utils/export-formatting';
	import { tooltip } from '$lib/utils/tooltip';
	import * as m from '$lib/paraglide/messages';

	export let open = false;
	export let draft: ExportDraft | null = null;
	export let isGenerating = false;
	export let generationError: string | null = null;
	export let selectedCount = 0;
	export let customPrompt: string | null = null;

	export let onClose: () => void;
	export let onRetry: () => void;
	export let onRegenerate: () => void;
	export let onExport: () => void;
	export let onDelete: () => void;

	// Regeneration prompt editor
	let showRegenPrompt = false;
	let regenPrompt = customPrompt || '';

	const DEFAULT_PROMPT = `WRITING GUIDELINES:
- Lead EVERY section with the most important fact
- Bold **key numbers, names, dates, and data**
- Sentences: SHORT and PUNCHY. Max 15-20 words per sentence.
- Cite sources inline using [source.com] format
- Include a "gaps" list: what's missing, who to interview`;

	function saveAndRegenerate() {
		const prompt = regenPrompt.trim() || null;
		feedStore.setCustomExportPrompt(prompt);
		onRegenerate();
	}

	function resetPrompt() {
		regenPrompt = '';
		feedStore.resetCustomExportPrompt();
	}

	// Progress simulation
	let generateProgress = 0;
	let generateProgressState: 'loading' | 'success' | 'error' = 'loading';
	let progressInterval: ReturnType<typeof setInterval> | null = null;

	function startProgressSimulation() {
		stopProgressInterval();
		generateProgress = 0;
		generateProgressState = 'loading';
		progressInterval = setInterval(() => {
			if (generateProgress < 30) {
				generateProgress += Math.random() * 8 + 2; // Fast initial ramp
			} else if (generateProgress < 60) {
				generateProgress += Math.random() * 4 + 1;
			} else if (generateProgress < 85) {
				generateProgress += Math.random() * 2 + 0.5;
			} else if (generateProgress < 90) {
				generateProgress += Math.random() * 0.5;
			}
			generateProgress = Math.min(generateProgress, 90);
		}, 500);
	}

	function stopProgressSimulation(success: boolean) {
		stopProgressInterval();
		if (success) {
			generateProgress = 100;
			generateProgressState = 'success';
		} else {
			generateProgressState = 'error';
		}
	}

	function stopProgressInterval() {
		if (progressInterval) {
			clearInterval(progressInterval);
			progressInterval = null;
		}
	}

	// React to generation state changes
	let wasGenerating = false;
	$: {
		if (isGenerating && !wasGenerating) {
			startProgressSimulation();
		} else if (!isGenerating && wasGenerating) {
			stopProgressSimulation(!generationError);
		}
		wasGenerating = isGenerating;
	}

	onDestroy(() => {
		stopProgressInterval();
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			onClose();
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<!-- Backdrop -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="backdrop" transition:fade={{ duration: 200 }} on:click={onClose}></div>

	<!-- Panel -->
	<div class="slide-over" transition:fly={{ x: 400, duration: 300 }}>
		<!-- Header: [> chevron] [Draft] left, [Export] [Regen toggle] right -->
		<div class="panel-header">
			<button class="collapse-btn" on:click={onClose} aria-label={m.export_closePanel()}>
				<ChevronRight size={16} />
			</button>
			<h2>{m.export_panelTitle()}</h2>
			<div class="header-actions">
				{#if draft && !isGenerating && !generationError}
					<div class="action-group">
						<button
							class="action-icon-btn"
							class:active={showRegenPrompt}
							on:click={() => showRegenPrompt = !showRegenPrompt}
							type="button"
						>
							<PenTool size={12} />
							{#if showRegenPrompt}
								<ChevronUp size={10} />
							{:else}
								<ChevronDown size={10} />
							{/if}
						</button>
						<button
							class="action-icon-btn"
							on:click={onDelete}
							type="button"
							aria-label={m.common_delete()}
						>
							<Trash2 size={12} />
						</button>
						<button class="btn-primary" on:click={() => { onExport(); }}>
							<Download size={12} />
							{m.export_asMarkdown()}
						</button>
					</div>
				{/if}
			</div>
		</div>

		<!-- Collapsible regen drawer below header -->
		{#if showRegenPrompt && draft}
			<div class="regen-drawer">
				<textarea
					class="prompt-textarea"
					bind:value={regenPrompt}
					placeholder={DEFAULT_PROMPT}
					rows="5"
				></textarea>
				<div class="regen-actions">
					<button class="reset-button" on:click={resetPrompt} type="button">
						<RotateCcw size={12} />
						{m.export_resetToDefaults()}
					</button>
					<button class="regen-btn" on:click={saveAndRegenerate}>
						<RefreshCw size={14} />
						{m.export_regenerate()}
					</button>
				</div>
			</div>
		{/if}

		{#if draft || isGenerating}
			<div class="disclaimer-banner">
				<span class="disclaimer-icon" use:tooltip={m.export_disclaimerTooltip()}>
					<Info size={14} />
				</span>
				<span>{m.export_disclaimer()}</span>
			</div>
		{/if}

		<div class="panel-body">
			{#if isGenerating}
				<div class="progress-container">
					<ProgressIndicator
						progress={Math.round(generateProgress)}
						message={m.export_preparing()}
						state={generateProgressState}
						hintText={selectedCount !== 1
							? m.export_analyzingSourcesPlural({ count: selectedCount })
							: m.export_analyzingSources({ count: selectedCount })}
					/>
				</div>
			{:else if generationError}
				<div class="state-centered error">
					<AlertCircle size={24} />
					<h3>{m.export_generationFailed()}</h3>
					<p>{generationError}</p>
					<button class="retry-btn" on:click={onRetry}>
						<RefreshCw size={14} />
						{m.common_tryAgain()}
					</button>
				</div>
			{:else if draft}
				<!-- Inlined article content -->
				<article class="document-content">
					<h1>{draft.title}</h1>
					<p class="lede">{draft.headline}</p>

					{#if draft.sections && draft.sections.length > 0}
						{#each draft.sections as section}
							<section class="draft-section">
								<h2>{section.heading}</h2>
								<p>{@html linkifySources(boldify(section.content), draft.sources)}</p>
							</section>
						{/each}
					{/if}

					<section class="sources-section">
						<h2>{m.export_sources()}</h2>
						<ul class="source-list">
							{#each draft.sources as source, i}
								<li>
									<span class="source-num">{i + 1}</span>
									<a href={source.url} target="_blank" rel="noopener noreferrer">
										{source.title}
									</a>
								</li>
							{/each}
						</ul>
					</section>
				</article>
			{/if}
		</div>
	</div>
{/if}

<style>
	@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=DM+Sans:wght@400;500;600&display=swap');

	:global(.citation-link) {
		color: inherit;
		text-decoration: underline;
		text-decoration-style: dotted;
	}
	:global(.citation-link:hover) {
		color: var(--color-primary);
	}
	:global(.citation-ref) {
		color: var(--color-primary);
		text-decoration: none;
		cursor: pointer;
	}
	:global(.citation-ref:hover) {
		text-decoration: underline;
	}
	:global(.citation-ref sup) {
		font-size: 0.7em;
		font-weight: 600;
	}

	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 60;
	}

	.slide-over {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		width: 65%;
		min-width: 500px;
		max-width: 900px;
		background: var(--color-surface-alt);
		z-index: 70;
		display: flex;
		flex-direction: column;
		box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
	}

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.625rem;
		padding: 1rem 1.5rem;
		background: var(--color-surface-alt);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.panel-header h2 {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
		flex: 1;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.action-group {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.action-icon-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.125rem;
		padding: 0.625rem 0.625rem;
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1;
		color: var(--color-ink-muted);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 0;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.action-icon-btn:hover {
		background: var(--color-surface);
		color: var(--color-ink);
	}

	.action-icon-btn.active {
		background: var(--color-surface);
		border-color: var(--color-border-strong);
		color: var(--color-ink);
	}

	/* Disclaimer banner */
	.disclaimer-banner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1.5rem;
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		font-size: 0.75rem;
		color: var(--color-ink-muted);
		flex-shrink: 0;
	}

	.disclaimer-icon {
		display: flex;
		align-items: center;
		color: var(--color-ink-subtle);
		cursor: help;
		flex-shrink: 0;
	}


	.collapse-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 6px;
		border: 1px solid var(--color-border);
		background: transparent;
		color: var(--color-ink-subtle);
		cursor: pointer;
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.collapse-btn:hover {
		background: var(--color-surface);
		color: var(--color-ink);
		border-color: var(--color-border-strong);
	}

	/* Regen drawer below header */
	.regen-drawer {
		padding: 1rem 1.5rem;
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.prompt-textarea {
		width: 100%;
		padding: 0.625rem;
		font-size: 0.75rem;
		line-height: 1.5;
		font-family: 'Monaco', 'Menlo', monospace;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		background: var(--color-surface-alt);
		resize: vertical;
		min-height: 80px;
		margin-bottom: 0.75rem;
	}

	.prompt-textarea:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
	}

	.prompt-textarea::placeholder {
		color: var(--color-ink-subtle);
		font-size: 0.6875rem;
	}

	.regen-actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.reset-button {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.625rem;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--color-ink-muted);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.reset-button:hover {
		background: rgba(179, 62, 46, 0.1);
		border-color: var(--color-error);
		color: var(--color-error);
	}

	.regen-btn {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 1rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: white;
		background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-deep) 100%);
		border: none;
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.2s ease;
		box-shadow: 0 1px 3px rgba(99, 102, 241, 0.3);
	}

	.regen-btn:hover {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
	}

	.panel-body {
		flex: 1;
		overflow-y: auto;
	}

	/* States */
	.state-centered {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 300px;
		text-align: center;
		padding: 1.5rem;
	}

	.progress-container {
		display: flex;
		flex-direction: column;
		justify-content: center;
		min-height: 300px;
		padding: 2rem 2.5rem;
		width: 100%;
		box-sizing: border-box;
	}

	.state-centered h3 {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 0.25rem 0;
	}

	.state-centered p {
		font-size: 0.875rem;
		color: var(--color-ink-muted);
		margin: 0;
	}

	.state-centered.error {
		color: var(--color-error);
	}

	.state-centered.error h3 {
		color: var(--color-error);
		margin-top: 0.75rem;
	}

	.state-centered.error p {
		margin-bottom: 1rem;
	}

	.retry-btn {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 1rem;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-error);
		background: rgba(179, 62, 46, 0.08);
		border: 1px solid var(--color-error);
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.retry-btn:hover {
		background: rgba(179, 62, 46, 0.1);
	}

	/* Article content */
	.document-content {
		padding: 2rem 2.5rem;
		font-family: 'Source Serif 4', Georgia, serif;
	}

	.document-content h1 {
		font-size: 1.625rem;
		font-weight: 700;
		line-height: 1.25;
		color: var(--color-ink);
		margin: 0 0 1rem 0;
		letter-spacing: -0.01em;
	}

	.document-content .lede {
		font-size: 1.125rem;
		font-style: italic;
		color: var(--color-ink-muted);
		line-height: 1.6;
		margin: 0 0 2rem 0;
		padding-bottom: 1.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.document-content h2 {
		font-family: 'DM Sans', system-ui, sans-serif;
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-ink-muted);
		margin: 0 0 0.75rem 0;
	}

	.draft-section {
		margin-bottom: 1.5rem;
	}

	.draft-section h2 {
		font-family: 'DM Sans', system-ui, sans-serif;
		font-size: 0.8125rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-ink);
		margin: 0 0 0.5rem 0;
	}

	.draft-section p {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-ink);
		margin: 0;
	}

	.sources-section {
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
	}

	.source-list {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.source-list li {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		font-size: 0.875rem;
		line-height: 1.6;
		margin-bottom: 0.375rem;
	}

	.source-num {
		font-family: 'DM Sans', system-ui, sans-serif;
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--color-ink-subtle);
		flex-shrink: 0;
	}

	.source-list a {
		color: var(--color-primary);
		text-decoration: none;
	}

	.source-list a:hover {
		text-decoration: underline;
	}

	@media (max-width: 768px) {
		.slide-over {
			width: 100%;
			min-width: unset;
		}
	}
</style>
