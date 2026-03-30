<script lang="ts">
	import * as m from '$lib/paraglide/messages';

	const TALLY_FORM_URL = 'https://tally.so/r/aQdDKW';

	function openBugReport() {
		window.open(TALLY_FORM_URL, '_blank', 'noopener,noreferrer');
	}
</script>

<button
	on:click={openBugReport}
	class="bug-report-button"
	aria-label={m.bugReport_label()}
	title={m.bugReport_label()}
>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		width="20"
		height="20"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<!-- Bug icon -->
		<path d="m8 2 1.88 1.88" />
		<path d="M14.12 3.88 16 2" />
		<path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
		<path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6" />
		<path d="M12 20v-9" />
		<path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
		<path d="M6 13H2" />
		<path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
		<path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
		<path d="M22 13h-4" />
		<path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
	</svg>
</button>

<style>
	.bug-report-button {
		position: fixed;
		bottom: 1.65rem;
		right: 1.25rem;
		z-index: 50;

		/* Size and shape */
		width: 44px;
		height: 44px;
		border-radius: 50%;

		/* Appearance */
		background: white;
		border: 1px solid #e5e7eb;
		color: #9ca3af;
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.10);

		/* Layout */
		display: flex;
		align-items: center;
		justify-content: center;

		/* Interaction */
		cursor: pointer;
		transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
	}

	.bug-report-button:hover {
		background: #f9fafb;
		border-color: #d1d5db;
		color: #6b7280;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
		transform: translateY(-2px);
	}

	.bug-report-button:active {
		transform: translateY(0);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
	}

	.bug-report-button:focus-visible {
		outline: none;
		border-color: #6366f1;
		box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15), 0 4px 24px rgba(0, 0, 0, 0.10);
	}

	.bug-report-button svg {
		flex-shrink: 0;
	}
</style>
