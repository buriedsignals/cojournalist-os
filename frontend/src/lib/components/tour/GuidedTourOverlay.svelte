<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	export let targetSelector: string;

	let spotlightRect = { top: 0, left: 0, width: 0, height: 0 };
	let viewportSize = { width: 0, height: 0 };
	let mounted = false;
	let retryCount = 0;
	const MAX_RETRIES = 10;
	const RETRY_DELAY = 100;

	// Unique mask ID to prevent collisions
	const maskId = `spotlight-mask-${Math.random().toString(36).slice(2, 9)}`;

	function updateViewportSize() {
		if (typeof window !== 'undefined') {
			viewportSize = {
				width: window.innerWidth,
				height: window.innerHeight
			};
		}
	}

	function calculateSpotlight() {
		if (typeof document === 'undefined') return;

		const target = document.querySelector(targetSelector);
		if (!target) {
			// Retry if element not found yet (might still be rendering)
			if (retryCount < MAX_RETRIES) {
				retryCount++;
				setTimeout(calculateSpotlight, RETRY_DELAY);
			}
			return;
		}

		retryCount = 0; // Reset retry count on success
		const rect = target.getBoundingClientRect();
		const padding = 4; // Small padding around the button

		spotlightRect = {
			top: rect.top - padding,
			left: rect.left - padding,
			width: rect.width + padding * 2,
			height: rect.height + padding * 2
		};
	}

	function handleResize() {
		updateViewportSize();
		calculateSpotlight();
	}

	onMount(() => {
		mounted = true;
		updateViewportSize();
		calculateSpotlight();
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('resize', handleResize);
		}
	});

	// Recalculate when target changes
	$: if (targetSelector && mounted) {
		retryCount = 0; // Reset retry count when selector changes
		calculateSpotlight();
	}
</script>

{#if viewportSize.width > 0}
<div class="overlay">
	<!-- Semi-transparent backdrop with cutout -->
	<svg class="backdrop" viewBox="0 0 {viewportSize.width} {viewportSize.height}" preserveAspectRatio="none">
		<defs>
			<mask id={maskId}>
				<!-- White = visible, black = hidden -->
				<rect x="0" y="0" width="100%" height="100%" fill="white" />
				<rect
					x={spotlightRect.left}
					y={spotlightRect.top}
					width={spotlightRect.width}
					height={spotlightRect.height}
					rx="8"
					ry="8"
					fill="black"
				/>
			</mask>
		</defs>
		<rect
			x="0"
			y="0"
			width="100%"
			height="100%"
			fill="rgba(15, 23, 42, 0.5)"
			mask="url(#{maskId})"
		/>
	</svg>

	<!-- Highlight ring around spotlight -->
	<div
		class="spotlight-ring"
		style="
			top: {spotlightRect.top}px;
			left: {spotlightRect.left}px;
			width: {spotlightRect.width}px;
			height: {spotlightRect.height}px;
		"
	></div>
</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 55;
		pointer-events: none;
		animation: fadeIn 0.2s ease-out;
	}

	@media (prefers-reduced-motion: reduce) {
		.overlay {
			animation: none;
		}
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	.backdrop {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}

	.spotlight-ring {
		position: absolute;
		border: 2px solid rgba(150, 139, 223, 0.6);
		border-radius: 8px;
		box-shadow: 0 0 0 4px rgba(150, 139, 223, 0.2);
		animation: pulse 2s ease-in-out infinite;
	}

	@media (prefers-reduced-motion: reduce) {
		.spotlight-ring {
			animation: none;
		}
	}

	@keyframes pulse {
		0%, 100% {
			box-shadow: 0 0 0 4px rgba(150, 139, 223, 0.2);
		}
		50% {
			box-shadow: 0 0 0 8px rgba(150, 139, 223, 0.1);
		}
	}
</style>
