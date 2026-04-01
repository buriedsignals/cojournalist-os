<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import * as m from '$lib/paraglide/messages';

	const dispatch = createEventDispatcher();

	function openBugReport() {
		dispatch('open');
	}
</script>

<button
	on:click={openBugReport}
	class="bug-report-button"
	aria-label={m.bugReport_label()}
	title={m.bugReport_label()}
>
	<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
		<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
	</svg>
</button>

<style>
	.bug-report-button {
		position: fixed;
		bottom: 1.65rem;
		right: 1.25rem;
		z-index: 50;

		width: 48px;
		height: 48px;
		border-radius: 14px;

		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		border: none;
		color: white;
		box-shadow: 0 4px 16px rgba(124, 111, 199, 0.4);

		display: flex;
		align-items: center;
		justify-content: center;

		cursor: pointer;
		transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
	}

	.bug-report-button:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 24px rgba(124, 111, 199, 0.5);
	}

	.bug-report-button:active {
		transform: translateY(0);
		box-shadow: 0 2px 8px rgba(124, 111, 199, 0.3);
	}

	.bug-report-button:focus-visible {
		outline: none;
		box-shadow: 0 0 0 3px rgba(150, 139, 223, 0.4), 0 4px 16px rgba(124, 111, 199, 0.4);
	}

	.bug-report-button svg {
		flex-shrink: 0;
	}
</style>
