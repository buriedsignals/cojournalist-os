<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let value: string;
	export let options: { value: string; label: string; description: string }[];

	const dispatch = createEventDispatcher<{ change: string }>();

	function select(option: string) {
		value = option;
		dispatch('change', option);
	}
</script>

<div class="toggle-picker" role="radiogroup">
	{#each options as option}
		<button
			type="button"
			class="toggle-option"
			class:active={value === option.value}
			role="radio"
			aria-checked={value === option.value}
			on:click={() => select(option.value)}
		>
			<span class="toggle-name">{option.label}</span>
			<span class="toggle-desc">{option.description}</span>
		</button>
	{/each}
</div>

<style>
	.toggle-picker { display: flex; padding: 3px; background: #f0f0f3; border-radius: 10px; gap: 3px; }
	.toggle-option { flex: 1; padding: 9px 10px; border-radius: 8px; text-align: center; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; }
	.toggle-option.active { background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
	.toggle-option .toggle-name { display: block; font-size: 0.8125rem; font-weight: 600; color: #374151; }
	.toggle-option.active .toggle-name { color: var(--color-accent, #6c5ce7); }
	.toggle-option .toggle-desc { display: block; font-size: 0.6875rem; color: #6b7280; text-align: center; margin-top: 2px; }
</style>
