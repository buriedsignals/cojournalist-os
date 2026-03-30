<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { CheckCircle, Clock, XCircle } from 'lucide-svelte';
	import { fade, slide } from 'svelte/transition';
	import * as m from '$lib/paraglide/messages';

	export let progress = 0;
	export let message = 'Loading...';
	export let state: 'loading' | 'success' | 'error' = 'loading';
	export let successMessage = 'Complete!';
	export let successDetails = '';
	export let errorTitle = '';
	export let errorMessage = '';
	export let showButton = false;
	export let buttonText = 'Continue';
	export let hintText = 'This may take a moment';

	const dispatch = createEventDispatcher<{ action: void }>();

	function handleAction() {
		dispatch('action');
	}
</script>

<div
	class="extraction-progress"
	class:extraction-progress--success={state === 'success'}
	class:extraction-progress--error={state === 'error'}
>
	{#if state === 'loading'}
		<!-- Loading State -->
		{#if hintText}
			<div class="extraction-progress__footer">
				<p class="extraction-progress__hint">
					<Clock class="extraction-progress__icon" />
					{hintText}
				</p>
			</div>
		{/if}
		<div class="extraction-progress__header">
			<span class="extraction-progress__message">{message}</span>
			<span class="extraction-progress__percentage">{progress}%</span>
		</div>
		<div class="extraction-progress__track">
			<div class="extraction-progress__fill" style="width: {progress}%"></div>
			<div class="extraction-progress__shimmer" style="width: {progress}%"></div>
		</div>

	{:else if state === 'success'}
		<!-- Success State -->
		<div class="extraction-progress__success" transition:fade={{ duration: 300 }}>
			<div class="extraction-progress__success-header">
				<div class="extraction-progress__success-icon">
					<CheckCircle class="h-6 w-6" />
				</div>
				<div class="extraction-progress__success-text">
					<span class="extraction-progress__success-title">{successMessage}</span>
					{#if successDetails}
						<span class="extraction-progress__success-details">{successDetails}</span>
					{/if}
				</div>
			</div>

			{#if showButton}
				<button
					class="btn-primary w-full mt-3"
					on:click={handleAction}
					transition:slide={{ duration: 200 }}
				>
					{buttonText}
				</button>
			{/if}
		</div>

	{:else if state === 'error'}
		<!-- Error State -->
		<div class="extraction-progress__error" transition:fade={{ duration: 300 }}>
			<div class="extraction-progress__error-header">
				<div class="extraction-progress__error-icon">
					<XCircle class="h-6 w-6" />
				</div>
				<div class="extraction-progress__error-text">
					<span class="extraction-progress__error-title">{errorTitle || m.progress_error()}</span>
					{#if errorMessage}
						<span class="extraction-progress__error-details">{errorMessage}</span>
					{/if}
				</div>
			</div>

			<!-- Failed progress bar (red) -->
			<div class="extraction-progress__track extraction-progress__track--error">
				<div class="extraction-progress__fill extraction-progress__fill--error" style="width: {progress}%"></div>
			</div>

			{#if showButton}
				<button
					class="btn-secondary w-full mt-3"
					on:click={handleAction}
					transition:slide={{ duration: 200 }}
				>
					{buttonText}
				</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	/* Success state modifiers */
	.extraction-progress--success {
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(5, 150, 105, 0.08) 100%);
		border-color: rgba(16, 185, 129, 0.2);
	}

	.extraction-progress--success::before {
		background: linear-gradient(90deg, #10b981, #059669);
	}

	.extraction-progress__success {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.extraction-progress__success-header {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.extraction-progress__success-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		color: #059669;
	}

	.extraction-progress__success-text {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.extraction-progress__success-title {
		font-family: 'DM Sans', sans-serif;
		font-size: 0.9375rem;
		font-weight: 600;
		color: #065f46;
	}

	.extraction-progress__success-details {
		font-size: 0.8125rem;
		color: #047857;
	}

	/* Error state modifiers */
	.extraction-progress--error {
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, rgba(220, 38, 38, 0.08) 100%);
		border-color: rgba(239, 68, 68, 0.2);
	}

	.extraction-progress--error::before {
		background: linear-gradient(90deg, #ef4444, #dc2626);
	}

	.extraction-progress__error {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.extraction-progress__error-header {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.extraction-progress__error-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		color: #dc2626;
	}

	.extraction-progress__error-text {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.extraction-progress__error-title {
		font-family: 'DM Sans', sans-serif;
		font-size: 0.9375rem;
		font-weight: 600;
		color: #991b1b;
	}

	.extraction-progress__error-details {
		font-size: 0.8125rem;
		color: #b91c1c;
	}

	.extraction-progress__track--error {
		background: rgba(239, 68, 68, 0.1);
	}

	.extraction-progress__fill--error {
		background: linear-gradient(90deg, #ef4444, #dc2626);
	}
</style>
