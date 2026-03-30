<script lang="ts">
	import { goto } from '$app/navigation';
	import { Check, Zap, ArrowLeft, Sparkles } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth';
	import * as m from '$lib/paraglide/messages';

	// Detect current plan from user tier
	$: currentPlan = $authStore.user?.tier ?? 'free';
	$: isAuthenticated = $authStore.authenticated;
	$: upgradeUrl = $authStore.user?.upgrade_url || 'https://accounts.muckrock.com/plans/70-cojournalist-pro/';
	$: teamUpgradeUrl = $authStore.user?.team_upgrade_url || 'https://accounts.muckrock.com/plans/71-cojournalist-team/';
	$: accountUrl = $authStore.user?.username
		? `https://accounts.muckrock.com/users/${$authStore.user.username}/`
		: 'https://accounts.muckrock.com/accounts/';

	const tierRank: Record<string, number> = { free: 0, pro: 1, team: 2 };
	function isUpgrade(planId: string): boolean {
		return (tierRank[planId] ?? 0) > (tierRank[currentPlan] ?? 0);
	}

	const plans = [
		{
			id: 'free',
			name: 'Free Starter',
			price: 0,
			currency: '$',
			period: '/mo',
			description: 'Just trying it out',
			credits: 100,
			popular: false,
			disabled: false,
			features: [
				{ text: '100 monthly credits', highlight: true },
				{ text: 'Scheduled web monitoring' },
				{ text: 'Location & beat smart tracking with digests' },
				{ text: 'Social media monitoring' },
				{ text: 'Social media & web scraping' },
				{ text: 'Information extraction & CMS export' },
				{ text: 'Email notifications' }
			]
		},
		{
			id: 'pro',
			name: 'Pro Plan',
			price: 10,
			currency: '$',
			period: '/mo',
			description: 'For serious monitoring',
			credits: 1000,
			popular: true,
			disabled: false,
			features: [
				{ text: '1,000 monthly credits', highlight: true },
				{ text: 'Everything in Free' },
				{ text: 'Track the Council' }
			]
		},
		{
			id: 'team',
			name: 'Team',
			price: 50,
			currency: '$',
			period: '/mo',
			description: 'Shared credits, shared scouts across your newsroom',
			credits: 5000,
			popular: false,
			disabled: false,
			features: [
				{ text: '5,000 shared monthly credits', highlight: true },
				{ text: 'Everything in Pro' },
				{ text: 'Unlimited team members' }
			]
		},
		{
			id: 'annual',
			name: 'Self-Hosted',
			price: 180,
			currency: 'CHF',
			period: '/yr',
			description: 'Run coJournalist on your own infrastructure',
			credits: null,
			showCredits: false,
			popular: false,
			disabled: false,
			features: [
				{ text: 'Automated deployment in minutes', highlight: true },
				{ text: 'New features delivered automatically' },
				{ text: 'Deploy on Render, Docker, or any PaaS' },
				{ text: 'Supabase (managed or self-hosted)' },
				{ text: 'All scout types, all features' }
			]
		}
	];

	let error: string | null = null;

	function goBack() {
		goto('/');
	}
</script>

<svelte:head>
	<title>Pricing - coJournalist</title>
</svelte:head>

<div class="pricing-page">
	<!-- Background elements -->
	<div class="bg-pattern"></div>
	<div class="bg-gradient"></div>
	<div class="bg-gradient-secondary"></div>

	<div class="content">
		<!-- Back button -->
		{#if isAuthenticated}
			<button class="back-button" on:click={goBack}>
				<ArrowLeft class="w-4 h-4" />
				<span>Back to app</span>
			</button>
		{:else}
			<a class="back-button" href="/login">
				<ArrowLeft class="w-4 h-4" />
				<span>{m.common_back()}</span>
			</a>
		{/if}

		<!-- Header -->
		<header class="header">
			<div class="badge">PRICING</div>
			<h1 class="title">
				Simple, transparent <span class="gradient-text">pricing</span>
			</h1>
			<p class="subtitle">{m.pricing_subtitle()}</p>
		</header>

		<!-- Credit explainer -->
		<div class="credit-explainer">
			<div class="explainer-icon">
				<Zap class="w-5 h-5" />
			</div>
			<div class="explainer-content">
				<h3>How credits work</h3>
				<p>{m.pricing_creditExplainer()}</p>
			</div>
		</div>

		<!-- Plans grid -->
		<div class="plans-grid">
			{#each plans as plan}
				<div class="plan-card" class:popular={plan.popular && currentPlan !== plan.id} class:current={currentPlan === plan.id} class:disabled-card={plan.disabled}>
					{#if currentPlan === plan.id && !plan.disabled}
						<div class="current-badge">{m.pricing_currentPlan()}</div>
					{:else if plan.popular}
						<div class="popular-badge">
							<Sparkles class="w-3 h-3" />
							Most Popular
						</div>
					{:else if plan.disabled && 'badgeText' in plan}
						<div class="coming-soon-badge">{(plan as any).badgeText}</div>
					{/if}

					<div class="plan-header">
						<h2 class="plan-name">{plan.name}</h2>
						<p class="plan-description">{plan.description}</p>
					</div>

					{#if plan.price !== null}
						<div class="plan-price">
							<span class="price-currency" class:long-currency={plan.currency && plan.currency.length > 1}>
								{plan.currency ?? '$'}
							</span>
							<span class="price-amount">{plan.price?.toLocaleString?.() ?? plan.price}</span>
							<span class="price-period">{plan.period}</span>
						</div>
					{:else}
						<div class="plan-price">
							<span class="price-amount price-free">Free</span>
						</div>
					{/if}

					{#if plan.id === 'annual'}
						<div class="plan-license-label">
							<a href="/faq">Sustainable Use License</a>
						</div>
					{/if}

					{#if plan.showCredits === false}
						<!-- Annual license plan does not display credits -->
					{:else if plan.credits !== null}
						<div class="plan-credits">
							<span class="credits-amount">{plan.credits.toLocaleString()}</span>
							<span class="credits-label">credits/month</span>
						</div>
					{:else}
						<div class="plan-credits">
							<span class="credits-amount">&infin;</span>
							<span class="credits-label">unlimited</span>
						</div>
					{/if}

					<ul class="features-list">
						{#each plan.features as feature}
							<li class="feature-item" class:highlight={feature.highlight}>
								<Check class="feature-check" />
								<span>{feature.text}</span>
							</li>
						{/each}
					</ul>

					{#if plan.id === 'annual'}
						<a class="plan-cta primary" href="https://buy.stripe.com/test_aFadR9cJl42O9L42sta3u00" target="_blank" rel="noopener noreferrer">
							Get Started
						</a>
					{:else if plan.disabled}
						<button class="plan-cta disabled" disabled>{(plan as any).badgeText || m.pricing_comingSoon()}</button>
					{:else if !isAuthenticated && plan.id === 'free'}
						<a class="plan-cta primary" href="/login">{m.pricing_getStarted()}</a>
					{:else if !isAuthenticated && plan.id === 'pro'}
						<a class="plan-cta secondary" href="/login">Start with Pro</a>
					{:else if !isAuthenticated && plan.id === 'team'}
						<a class="plan-cta secondary" href="/login">Start with Team</a>
					{:else if !isAuthenticated}
						<a class="plan-cta secondary" href="/login">{m.pricing_signUpToStart()}</a>
					{:else if isAuthenticated && currentPlan === plan.id}
						<button class="plan-cta disabled" disabled>{m.pricing_currentPlan()}</button>
					{:else if isAuthenticated && plan.id === 'free'}
						<a class="plan-cta secondary" href={accountUrl} target="_blank" rel="noopener noreferrer">
							Manage subscription
						</a>
					{:else if isAuthenticated && plan.id === 'pro'}
						<a class="plan-cta {isUpgrade('pro') ? 'primary' : 'secondary'}" href={isUpgrade('pro') ? upgradeUrl : accountUrl} target="_blank" rel="noopener noreferrer">
							{isUpgrade('pro') ? m.pricing_upgradeToPro() : 'Manage subscription'}
						</a>
					{:else if isAuthenticated && plan.id === 'team'}
						<a class="plan-cta {isUpgrade('team') ? 'primary' : 'secondary'}" href={isUpgrade('team') ? teamUpgradeUrl : accountUrl} target="_blank" rel="noopener noreferrer">
							{isUpgrade('team') ? 'Upgrade to Team' : 'Manage subscription'}
						</a>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Error toast -->
		{#if error}
			<div class="error-toast">
				<span>{error}</span>
			</div>
		{/if}

		<!-- Open source footer -->
		<div class="oss-footer">
			<p class="oss-footer-text">
				coJournalist is open source under the
				<a href="/faq" class="oss-footer-link">Sustainable Use License</a>.
			</p>
			<a href="https://github.com/buriedsignals/cojournalist-os" target="_blank" rel="noopener noreferrer" class="oss-github-button">
				<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
				View on GitHub
			</a>
		</div>

		<!-- Footer note -->
		<p class="footer-note">
			Questions? <a href="mailto:tom@buriedsignals.com">Contact me</a>.
		</p>
	</div>
</div>

<style>
	.pricing-page {
		min-height: 100vh;
		background: var(--color-bg-primary);
		position: relative;
		overflow-x: hidden;
	}

	.bg-pattern {
		position: absolute;
		inset: 0;
		background-image: linear-gradient(to right, #e7e5e4 1px, transparent 1px),
			linear-gradient(to bottom, #e7e5e4 1px, transparent 1px);
		background-size: 60px 60px;
		opacity: 0.25;
	}

	.bg-gradient {
		position: absolute;
		top: -100px;
		left: 50%;
		transform: translateX(-50%);
		width: 900px;
		height: 600px;
		background: radial-gradient(ellipse, rgba(150, 139, 223, 0.12) 0%, transparent 70%);
		pointer-events: none;
	}

	.bg-gradient-secondary {
		position: absolute;
		bottom: 0;
		right: -200px;
		width: 600px;
		height: 600px;
		background: radial-gradient(ellipse, rgba(245, 158, 11, 0.08) 0%, transparent 70%);
		pointer-events: none;
	}

	.content {
		position: relative;
		z-index: 1;
		max-width: 1100px;
		margin: 0 auto;
		padding: 2rem 1.5rem 4rem;
	}

	/* Back button */
	.back-button {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-text-secondary);
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		cursor: pointer;
		margin-bottom: 2rem;
		transition: all 0.2s ease;
		text-decoration: none;
	}

	.back-button:hover {
		border-color: var(--color-accent);
		color: var(--color-accent-dark);
	}

	/* Header */
	.header {
		text-align: center;
		margin-bottom: 3rem;
	}

	.badge {
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.2em;
		color: var(--color-text-tertiary);
		margin-bottom: 1rem;
	}

	.title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: clamp(2rem, 5vw, 3rem);
		font-weight: 700;
		margin-bottom: 1rem;
		color: var(--color-text-primary);
	}

	.gradient-text {
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.subtitle {
		font-size: 1.125rem;
		color: var(--color-text-secondary);
		max-width: 500px;
		margin: 0 auto;
	}

	/* Credit explainer */
	.credit-explainer {
		display: flex;
		gap: 1rem;
		padding: 1.25rem;
		background: linear-gradient(135deg, rgba(251, 191, 36, 0.08), rgba(245, 158, 11, 0.12));
		border: 1px solid rgba(245, 158, 11, 0.2);
		border-radius: 0.75rem;
		margin-bottom: 3rem;
		max-width: 650px;
		margin-left: auto;
		margin-right: auto;
	}

	.explainer-icon {
		flex-shrink: 0;
		width: 2.5rem;
		height: 2.5rem;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		border-radius: 0.5rem;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.explainer-content h3 {
		font-size: 0.9375rem;
		font-weight: 600;
		margin-bottom: 0.25rem;
		color: var(--color-text-primary);
	}

	.explainer-content p {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		margin: 0;
		line-height: 1.5;
	}

	/* Plans grid */
	.plans-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 2rem;
		margin-bottom: 4rem;
	}

	.plan-card {
		position: relative;
		display: flex;
		flex-direction: column;
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 2rem;
		transition: all 0.3s ease;
	}

	.plan-card:hover {
		box-shadow: var(--shadow-lg);
	}

	.plan-card.popular {
		border-color: var(--color-accent);
		box-shadow: 0 8px 32px rgba(150, 139, 223, 0.15);
	}

	.plan-card.current {
		border-color: var(--color-success);
	}

	.plan-card.disabled-card {
		opacity: 0.6;
		background: linear-gradient(135deg, #f9fafb, #f3f4f6);
	}

	.plan-card.disabled-card:hover {
		box-shadow: none;
	}

	.popular-badge {
		position: absolute;
		top: -12px;
		left: 50%;
		transform: translateX(-50%);
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 1rem;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		color: white;
		font-size: 0.75rem;
		font-weight: 600;
		border-radius: 999px;
		white-space: nowrap;
	}

	.current-badge {
		position: absolute;
		top: -12px;
		left: 50%;
		transform: translateX(-50%);
		padding: 0.375rem 0.875rem;
		background: linear-gradient(135deg, #10b981, #059669);
		color: white;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		border-radius: 999px;
	}

	.coming-soon-badge {
		position: absolute;
		top: -12px;
		left: 50%;
		transform: translateX(-50%);
		padding: 0.375rem 0.875rem;
		background: linear-gradient(135deg, #6b7280, #4b5563);
		color: white;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		border-radius: 999px;
		white-space: nowrap;
	}

	.plan-header {
		margin-bottom: 1rem;
	}

	.plan-name {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 0.25rem;
	}

	.plan-description {
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		margin: 0;
	}

	.plan-price {
		display: flex;
		align-items: baseline;
		gap: 0.25rem;
		margin: 1rem 0 0.5rem;
	}

	.price-currency {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	.price-currency.long-currency {
		font-size: 1rem;
		letter-spacing: 0.02em;
	}

	.price-amount {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 3.5rem;
		font-weight: 700;
		line-height: 1;
		color: var(--color-text-primary);
	}

	.price-period {
		font-size: 0.9375rem;
		color: var(--color-text-tertiary);
	}

	.price-free {
		font-size: 2.5rem;
	}

	.plan-credits {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-tertiary);
		border-radius: 0.5rem;
		margin-bottom: 1.5rem;
	}

	.credits-amount {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-accent-dark);
	}

	.credits-label {
		font-size: 0.875rem;
		color: var(--color-text-tertiary);
	}

	.features-list {
		list-style: none;
		padding: 0;
		margin: 0 0 2rem;
	}

	.feature-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.625rem 0;
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
	}

	.feature-item.highlight {
		font-weight: 600;
		color: var(--color-text-primary);
	}

	:global(.feature-check) {
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
		color: var(--color-success);
	}

	.plan-cta {
		margin-top: auto;
		width: 100%;
		padding: 0.875rem;
		font-size: 0.9375rem;
		font-weight: 600;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
		border: none;
		text-align: center;
		text-decoration: none;
	}

	.plan-cta.disabled {
		background: var(--color-bg-tertiary);
		color: var(--color-text-tertiary);
		cursor: not-allowed;
		border: 1px solid var(--color-border);
	}

	.plan-cta.primary {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		color: white;
	}

	.plan-cta.secondary {
		display: block;
		width: 100%;
		background: white;
		color: var(--color-accent-dark);
		border: 1px solid var(--color-border);
	}

	.plan-cta.secondary:hover {
		border-color: var(--color-accent);
		color: var(--color-accent-dark);
		box-shadow: 0 8px 16px rgba(150, 139, 223, 0.12);
		transform: translateY(-1px);
	}

	.plan-cta.primary:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 20px rgba(245, 158, 11, 0.3);
	}

	/* Error toast */
	.error-toast {
		position: fixed;
		bottom: 2rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem 1.5rem;
		background: #dc2626;
		color: white;
		border-radius: 0.75rem;
		box-shadow: 0 8px 32px rgba(220, 38, 38, 0.3);
		animation: toastIn 0.3s ease-out;
		z-index: 100;
		max-width: 90%;
		text-align: center;
	}

	@keyframes toastIn {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(20px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	/* Footer note */
	.footer-note {
		text-align: center;
		font-size: 0.875rem;
		color: var(--color-text-tertiary);
	}

	.footer-note a {
		color: var(--color-accent);
		text-decoration: none;
		font-weight: 500;
	}

	.footer-note a:hover {
		text-decoration: underline;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.plans-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 640px) {
		.plans-grid {
			grid-template-columns: 1fr;
		}

		.credit-explainer {
			flex-direction: column;
			text-align: center;
		}

		.explainer-icon {
			margin: 0 auto;
		}
	}

	/* License label for Self-Hosted plan */
	.plan-license-label {
		margin-bottom: 1.5rem;
	}
	.plan-license-label a {
		font-size: 0.75rem;
		color: #a8a29e;
		text-decoration: none;
		font-weight: 500;
		letter-spacing: 0.02em;
	}
	.plan-license-label a:hover {
		color: #968bdf;
		text-decoration: underline;
	}

	/* Open source footer */
	.oss-footer {
		text-align: center;
		margin-bottom: 2rem;
		padding: 1.5rem;
		background: rgba(150, 139, 223, 0.04);
		border: 1px solid rgba(150, 139, 223, 0.1);
		border-radius: 0.75rem;
	}
	.oss-footer-text {
		font-size: 0.875rem;
		color: #78716c;
		margin: 0 0 0.75rem;
	}
	.oss-footer-link {
		color: #968bdf;
		text-decoration: none;
		font-weight: 500;
	}
	.oss-footer-link:hover { text-decoration: underline; }
	.oss-github-button {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1.25rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: #57534e;
		background: white;
		border: 1px solid #d6d3d1;
		border-radius: 0.5rem;
		text-decoration: none;
		transition: all 0.2s ease;
	}
	.oss-github-button:hover {
		border-color: #968bdf;
		color: #968bdf;
		box-shadow: 0 2px 8px rgba(150, 139, 223, 0.12);
	}
</style>
