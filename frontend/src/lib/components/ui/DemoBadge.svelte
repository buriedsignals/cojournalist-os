<script lang="ts">
	export let variant: 'ribbon' | 'pill' = 'pill';
	export let label = 'DEMO';
</script>

<span class="demo-badge {variant}" aria-label="Example data — read-only">{label}</span>

<style>
	.demo-badge {
		display: inline-flex;
		align-items: center;
		font-weight: 800;
		letter-spacing: 0.1em;
		color: white;
		background: linear-gradient(135deg, #6B3FA0, #4E2C78);
		border-radius: 0;
		box-shadow: 0 1px 3px rgba(78, 44, 120, 0.3);
		white-space: nowrap;
		pointer-events: none;
	}

	.demo-badge.pill {
		font-size: 0.625rem;
		padding: 0.1875rem 0.5rem;
	}

	.demo-badge.ribbon {
		position: absolute;
		top: 0.625rem;
		right: 0.625rem;
		font-size: 0.625rem;
		padding: 0.1875rem 0.5rem;
		z-index: 1;
	}
</style>
