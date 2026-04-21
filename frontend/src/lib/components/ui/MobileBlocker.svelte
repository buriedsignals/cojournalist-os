<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { Monitor } from 'lucide-svelte';
	import * as m from '$lib/paraglide/messages';

	let showBlocker = false;

	onMount(() => {
		checkScreenSize();
		window.addEventListener('resize', checkScreenSize);
		return () => window.removeEventListener('resize', checkScreenSize);
	});

	function checkScreenSize() {
		if (typeof window !== 'undefined') {
			showBlocker = window.innerWidth < 1024;
		}
	}

	// Skip blocker on public pages
	$: isExemptPage = $page.url.pathname === '/login' || $page.url.pathname === '/faq' || $page.url.pathname === '/terms';
</script>

{#if showBlocker && !isExemptPage}
	<div class="mobile-blocker">
		<div class="mobile-blocker-content">
			<div class="icon-wrapper">
				<Monitor class="monitor-icon" />
			</div>

			<h1 class="title">
				co<span class="gradient-text">Journalist</span>
			</h1>

			<h2 class="heading">{m.mobile_title()}</h2>

			<p class="message">
				{m.mobile_description()}
			</p>

			<p class="submessage">
				{m.mobile_hint()}
			</p>
		</div>
	</div>
{/if}

<style>
	.mobile-blocker {
		position: fixed;
		inset: 0;
		background: linear-gradient(135deg, #fafaf9 0%, #f5f5f4 100%);
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem;
	}

	.mobile-blocker-content {
		max-width: 480px;
		text-align: center;
		animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
	}

	@keyframes fadeInUp {
		from {
			opacity: 0;
			transform: translateY(20px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.icon-wrapper {
		margin-bottom: 2rem;
		display: flex;
		justify-content: center;
	}

	.title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 2.5rem;
		font-weight: 700;
		margin-bottom: 2rem;
		color: var(--color-ink);
		letter-spacing: -0.02em;
	}

	.gradient-text {
		background: linear-gradient(135deg, #6B3FA0 0%, #4E2C78 100%);
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
		display: inline-block;
	}

	.heading {
		font-family: 'DM Sans', sans-serif;
		font-size: 1.5rem;
		font-weight: 600;
		margin-bottom: 1rem;
		color: var(--color-ink);
	}

	.message {
		font-family: 'DM Sans', sans-serif;
		font-size: 1rem;
		line-height: 1.6;
		color: var(--color-ink-muted);
		margin-bottom: 1rem;
	}

	.submessage {
		font-family: 'DM Sans', sans-serif;
		font-size: 0.875rem;
		line-height: 1.6;
		color: var(--color-ink-subtle);
		margin-bottom: 2rem;
	}
</style>
