<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { ChevronDown } from 'lucide-svelte';
	import { AGENTS, type AgentSlug } from '$lib/utils/agent-icons';

	export let value: AgentSlug = 'claude-code';

	let open = false;
	let wrap: HTMLDivElement;

	const dispatch = createEventDispatcher<{ change: AgentSlug }>();

	$: current = AGENTS.find((a) => a.slug === value) ?? AGENTS[0];

	function pick(slug: AgentSlug) {
		open = false;
		if (slug !== value) {
			value = slug;
			dispatch('change', slug);
		}
	}

	function onDocClick(e: MouseEvent) {
		if (!open) return;
		if (wrap && !wrap.contains(e.target as Node)) open = false;
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape') open = false;
	}

	onMount(() => {
		document.addEventListener('click', onDocClick);
		document.addEventListener('keydown', onKey);
		return () => {
			document.removeEventListener('click', onDocClick);
			document.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="agent-select" bind:this={wrap}>
	<button
		type="button"
		class="trigger"
		on:click|stopPropagation={() => (open = !open)}
		aria-haspopup="listbox"
		aria-expanded={open}
	>
		<span class="label">Agent</span>
		<span class="current">
			<svg
				class="icon"
				viewBox="0 0 24 24"
				width="14"
				height="14"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				{@html current.iconInner}
			</svg>
			<span class="name">{current.name}</span>
		</span>
		<ChevronDown size={14} class="chev" />
	</button>

	{#if open}
		<ul class="menu" role="listbox">
			{#each AGENTS as a (a.slug)}
				<li>
					<button
						type="button"
						class="item"
						class:selected={a.slug === value}
						role="option"
						aria-selected={a.slug === value}
						on:click|stopPropagation={() => pick(a.slug)}
					>
						<svg
							class="icon"
							viewBox="0 0 24 24"
							width="14"
							height="14"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							{@html a.iconInner}
						</svg>
						<span class="name">{a.name}</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.agent-select {
		position: relative;
		display: inline-block;
	}

	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem 0.5rem 0.625rem;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 0;
		font-size: 0.875rem;
		color: var(--color-ink);
		cursor: pointer;
		transition:
			border-color 0.15s ease,
			box-shadow 0.15s ease;
		min-width: 14rem;
	}
	.trigger:hover {
		border-color: #c7bdef;
	}
	.trigger[aria-expanded='true'] {
		border-color: #4E2C78;
		box-shadow: 0 0 0 3px rgba(78, 44, 120, 0.12);
	}

	.label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-ink-muted);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding-right: 0.125rem;
	}

	.current {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		flex: 1;
		min-width: 0;
	}

	.current .name {
		font-weight: 600;
		color: var(--color-ink);
	}

	:global(.agent-select .chev) {
		margin-left: auto;
		color: var(--color-ink-subtle);
	}

	.menu {
		position: absolute;
		left: 0;
		top: calc(100% + 4px);
		z-index: 50;
		min-width: 100%;
		margin: 0;
		padding: 0.25rem;
		list-style: none;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: 0;
		box-shadow: 0 10px 25px -10px rgba(15, 23, 42, 0.2);
		max-height: 22rem;
		overflow-y: auto;
	}

	.item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.625rem;
		background: transparent;
		border: none;
		border-radius: 0;
		font-size: 0.875rem;
		color: var(--color-ink);
		cursor: pointer;
		text-align: left;
	}

	.item:hover {
		background: var(--color-primary-soft);
		color: var(--color-primary-deep);
	}

	.item.selected {
		background: var(--color-primary-soft);
		color: var(--color-primary-deep);
		font-weight: 600;
	}

	.icon {
		flex-shrink: 0;
	}
</style>
