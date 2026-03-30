<script lang="ts">
	export let muted = false;
</script>

<svg viewBox="0 0 120 80" class="constellation-svg" class:muted>
	<line class="c-line ln-1" x1="20" y1="25" x2="55" y2="15" />
	<line class="c-line ln-2" x1="55" y1="15" x2="95" y2="30" />
	<line class="c-line ln-3" x1="35" y1="55" x2="55" y2="15" />
	<line class="c-line ln-4" x1="35" y1="55" x2="75" y2="60" />
	<line class="c-line ln-5" x1="75" y1="60" x2="95" y2="30" />
	<circle class="c-dot d-1" cx="20" cy="25" r="3" />
	<circle class="c-dot d-2" cx="55" cy="15" r="3.5" />
	<circle class="c-dot d-3" cx="95" cy="30" r="2.5" />
	<circle class="c-dot d-4" cx="35" cy="55" r="3" />
	<circle class="c-dot d-5" cx="75" cy="60" r="2.5" />
	<circle class="c-dot d-6" cx="105" cy="55" r="2" />
	<circle class="c-dot d-7" cx="10" cy="50" r="2" />
</svg>

<style>
	.constellation-svg {
		width: 100%;
		height: 100%;
		overflow: visible;
	}

	.constellation-svg.muted {
		opacity: 0.5;
	}

	.c-dot {
		fill: #a78bfa;
		animation: dot-drift 4s ease-in-out infinite;
	}

	.c-line {
		stroke: #c4b5fd;
		stroke-width: 0.8;
		opacity: 0;
		animation: line-fade 5s ease-in-out infinite;
	}

	.d-1 { animation-delay: 0s; animation-duration: 4.5s; }
	.d-2 { animation-delay: 0.6s; animation-duration: 3.8s; }
	.d-3 { animation-delay: 1.2s; animation-duration: 4.2s; }
	.d-4 { animation-delay: 0.3s; animation-duration: 5s; }
	.d-5 { animation-delay: 0.9s; animation-duration: 4s; }
	.d-6 { animation-delay: 1.5s; animation-duration: 4.8s; fill: #c4b5fd; }
	.d-7 { animation-delay: 0.4s; animation-duration: 5.2s; fill: #c4b5fd; }

	.ln-1 { animation-delay: 0.5s; animation-duration: 4s; }
	.ln-2 { animation-delay: 1.5s; animation-duration: 5s; }
	.ln-3 { animation-delay: 2.5s; animation-duration: 4.5s; }
	.ln-4 { animation-delay: 0.8s; animation-duration: 5.5s; }
	.ln-5 { animation-delay: 2s; animation-duration: 4.8s; }

	@keyframes dot-drift {
		0%, 100% { transform: translate(0, 0); }
		25% { transform: translate(1.5px, -2px); }
		50% { transform: translate(-1px, 1.5px); }
		75% { transform: translate(2px, 1px); }
	}

	@keyframes line-fade {
		0%, 15% { opacity: 0; }
		30%, 70% { opacity: 0.45; }
		85%, 100% { opacity: 0; }
	}
</style>
