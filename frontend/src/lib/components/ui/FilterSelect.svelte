<script lang="ts">
	import { ChevronDown } from 'lucide-svelte';
	import type { ComponentType } from 'svelte';

	type Option = { value: string; label: string; count?: number };

	export let options: Option[];
	export let value: string;
	export let onChange: (value: string) => void;
	export let icon: ComponentType | undefined = undefined;
	export let disabled: boolean = false;

	$: selectedLabel = options.find((o) => o.value === value);
	$: displayText = selectedLabel
		? `${selectedLabel.label}${selectedLabel.count !== undefined ? ` (${selectedLabel.count})` : ''}`
		: '';
</script>

<div class="filter-select" class:disabled>
	{#if icon}
		<svelte:component this={icon} size={14} class="filter-icon" />
	{/if}
	<span class="label">{displayText}</span>
	<ChevronDown size={12} class="chevron" />
	<select {value} {disabled} on:change={(e) => onChange(e.currentTarget.value)}>
		{#each options as opt}
			<option value={opt.value}>
				{opt.label}{opt.count !== undefined ? ` (${opt.count})` : ''}
			</option>
		{/each}
	</select>
</div>

<style>
	.filter-select {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		position: relative;
		padding: 0.375rem 0.625rem;
		padding-right: 1.5rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 6px;
		font-size: 0.8125rem;
		color: #374151;
		cursor: pointer;
		transition: all 0.15s ease;
		max-width: min(250px, 40vw);
		min-width: 0;
	}

	.filter-select.disabled {
		opacity: 0.45;
		cursor: default;
		pointer-events: none;
	}

	.filter-select:hover:not(.disabled) {
		border-color: #d1d5db;
	}

	.filter-select:focus-within {
		border-color: #6366f1;
		box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
	}

	.filter-select .label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		pointer-events: none;
	}

	.filter-select :global(.filter-icon) {
		color: #6b7280;
		flex-shrink: 0;
	}

	.filter-select select {
		position: absolute;
		inset: 0;
		border: none;
		background: transparent;
		font-size: inherit;
		font-family: inherit;
		color: transparent;
		cursor: pointer;
		outline: none;
		appearance: none;
		opacity: 0;
		width: 100%;
		height: 100%;
	}

	.filter-select :global(.chevron) {
		position: absolute;
		right: 0.5rem;
		top: 50%;
		transform: translateY(-50%);
		color: #9ca3af;
		pointer-events: none;
	}
</style>
