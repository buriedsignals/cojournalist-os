<script lang="ts">
	import Spinner from './Spinner.svelte';

	export let loading = false;
	export let loadingText = '';
	export let title = '';
	export let subtitle = '';
	export let hint = '';
</script>

<div class="panel-placeholder">
	{#if loading}
		<Spinner size="md" />
		<p class="ph-loading-text">{loadingText}</p>
	{:else}
		{#if $$slots.graphic}
			<div class="ph-graphic-wrapper">
				<slot name="graphic" />
			</div>
		{/if}
		{#if title}
			<p class="ph-title">{title}</p>
		{/if}
		{#if subtitle}
			<p class="ph-subtitle">{@html subtitle}</p>
		{/if}
		{#if hint}
			<span class="ph-hint">{hint}</span>
		{/if}
	{/if}
</div>

<style>
	.panel-placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		margin-top: 6rem;
		padding: 0 1.5rem;
		text-align: center;
		color: #6b7280;
	}

	.ph-graphic-wrapper {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100px;
		height: 100px;
		flex-shrink: 0;
	}

	/* Consistent gap between graphic slot and text */
	.ph-loading-text,
	.ph-title {
		margin-top: 0.75rem;
	}

	.ph-loading-text {
		font-size: 0.875rem;
		font-weight: 500;
	}

	.ph-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: #111827;
		margin-bottom: 0.25rem;
	}

	.ph-subtitle {
		font-size: 0.8125rem;
		color: #6b7280;
		margin: 0;
	}

	.ph-hint {
		font-size: 0.75rem;
		color: #9ca3af;
		margin-top: 0.25rem;
	}
</style>
