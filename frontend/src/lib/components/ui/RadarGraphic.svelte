<script lang="ts">
	import { Radar } from 'lucide-svelte';
</script>

<div class="radar-container">
	<div class="sonar-ring"></div>
	<div class="sonar-ring delay-1"></div>
	<div class="sonar-ring delay-2"></div>
	<div class="radar-icon-wrapper">
		<Radar size={28} />
	</div>
</div>

<style>
	.radar-container {
		position: relative;
		width: 100%;
		height: 100%;
	}

	.radar-icon-wrapper {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #4E2C78;
	}

	.sonar-ring {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 24px;
		height: 24px;
		margin: -12px 0 0 -12px;
		border-radius: 50%;
		border: 1.5px solid #a78bfa;
		opacity: 0;
		animation: sonar-expand 3s ease-out infinite;
	}

	.sonar-ring.delay-1 {
		animation-delay: 1s;
	}

	.sonar-ring.delay-2 {
		animation-delay: 2s;
	}

	@keyframes sonar-expand {
		0% {
			width: 24px;
			height: 24px;
			margin: -12px 0 0 -12px;
			opacity: 0.6;
		}
		100% {
			width: 100px;
			height: 100px;
			margin: -50px 0 0 -50px;
			opacity: 0;
		}
	}
</style>
