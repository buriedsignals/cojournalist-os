<script lang="ts">
	import * as m from '$lib/paraglide/messages';

	export let value = '';
	export let placeholder = '';
	export let rows = 2;
	export let examples: { label: string; value: string }[] = [];
</script>

<div class="criteria-field">
	<textarea
		bind:value
		{placeholder}
		{rows}
		class="criteria-textarea"
	></textarea>
	{#if !value.trim() && examples.length > 0}
		<div class="criteria-pills">
			<span class="criteria-pills-label">{m.webScout_criteriaExamplesLabel()}</span>
			{#each examples as ex}
				<button type="button" class="criteria-pill" on:click={() => value = ex.value}>{ex.label}</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.criteria-field {
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-secondary);
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
		overflow: hidden;
	}

	.criteria-field:focus-within {
		border-color: var(--color-accent);
		box-shadow: 0 0 0 3px rgba(150, 139, 223, 0.1);
	}

	.criteria-field:hover:not(:focus-within) {
		border-color: var(--color-border-hover);
	}

	.criteria-textarea {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: none;
		background: transparent;
		font-size: 0.875rem;
		font-family: 'DM Sans', sans-serif;
		color: var(--color-text-primary);
		resize: none;
		outline: none;
	}

	.criteria-textarea::placeholder { color: #94a3b8; }

	.criteria-pills {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.375rem;
		padding: 0 0.75rem 0.5rem;
	}

	.criteria-pills-label {
		font-size: 0.6875rem;
		color: var(--color-text-tertiary);
	}

	.criteria-pill {
		padding: 0.2rem 0.5rem;
		font-size: 0.6875rem;
		font-family: 'DM Sans', sans-serif;
		background: #f3f4f6;
		border: 1px solid #e5e7eb;
		border-radius: 9999px;
		cursor: pointer;
		transition: all 0.15s ease;
		color: var(--color-text-secondary);
	}

	.criteria-pill:hover {
		background: #eff6ff;
		border-color: #3b82f6;
		color: #2563eb;
	}
</style>
