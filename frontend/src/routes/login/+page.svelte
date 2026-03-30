<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { onMount } from 'svelte';

	let mounted = false;

	$: notAvailable = $page.url.searchParams.get('error') === 'not_available';

	onMount(() => {
		mounted = true;
		const unsubscribe = auth.subscribe(async (state) => {
			if (state.authenticated) {
				await goto('/');
			}
		});

		return () => {
			unsubscribe();
		};
	});
</script>

<div class="login-container">
	<!-- Animated background elements -->
	<div class="bg-orbs">
		<div class="orb orb-1"></div>
		<div class="orb orb-2"></div>
		<div class="orb orb-3"></div>
	</div>

	<!-- Subtle grid pattern -->
	<div class="grid-pattern"></div>

	<!-- Animated points along grid lines -->
	<div class="grid-points">
		<div class="point point-1"></div>
		<div class="point point-2"></div>
		<div class="point point-3"></div>
		<div class="point point-4"></div>
		<div class="point point-5"></div>
	</div>

	<div class="content-wrapper">
		<!-- Auth panel - Fixed centered on left -->
		<div class="auth-panel-container">
			<div class="auth-panel" class:mounted>
				<div class="auth-card">
					{#if notAvailable}
						<img src="/logo-cojournalist.svg" alt="coJournalist" class="auth-logo" />
						<p class="coming-soon-title">Coming Soon</p>
						<p class="coming-soon-text">
							coJournalist will be available by the end of March 2026. We'll notify you when access opens up.
						</p>
					{:else}
						<span class="brand-dot"></span>
						<p class="auth-title">Welcome</p>
						<p class="auth-subtitle">Sign in via MuckRock</p>
						<button class="sign-in-button" onclick={() => auth.login()}>
							Sign in
						</button>
						<a href="/pricing" class="auth-link-pricing">See pricing</a>

						<div class="auth-oss-badge">
							<p class="auth-oss-text">
								Open source under the
								<a href="/faq" class="auth-oss-link">Sustainable Use License</a>
							</p>
							<a href="https://github.com/buriedsignals/cojournalist-os" target="_blank" rel="noopener noreferrer" class="auth-github-link">
								<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" style="vertical-align: -2px; margin-right: 4px;"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
								View on GitHub
							</a>
						</div>
					{/if}
				</div>
			</div>
		</div>

		<!-- Story / marketing panel -->
		<div class="story-panel" class:mounted>
			<div class="badge">
				<span class="badge-dot"></span>
				PRIVATE BETA
			</div>

			<img src="/logo-cojournalist.svg" alt="coJournalist" class="headline-logo" />

			<p class="tagline">
				Let your AI assistant monitor the
				<span class="highlight-muted">noise</span>
				and
				<span class="highlight-accent">surface leads</span>.
			</p>

			<div class="description-block">
				<h2 class="subheadline">
					AI scouts that track your beats, monitor pages, and surface leads — while you <span class="highlight-accent">focus on reporting</span>.
				</h2>

				<div class="feature-list">
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/>
								<path d="M4 6h.01"/>
								<path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/>
								<path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/>
								<path d="M12 18h.01"/>
								<path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/>
								<circle cx="12" cy="12" r="2"/>
								<path d="m13.41 10.59 5.66-5.66"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Track Your Beat</p>
							<p class="feature-desc">AI scouts that monitor locations, topics, or both — on your schedule. Surface under-reported stories and leads automatically.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<circle cx="12" cy="12" r="10"/>
								<line x1="22" y1="12" x2="18" y2="12"/>
								<line x1="6" y1="12" x2="2" y2="12"/>
								<line x1="12" y1="6" x2="12" y2="2"/>
								<line x1="12" y1="22" x2="12" y2="18"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Track Pages</p>
							<p class="feature-desc">Watch any webpage for changes and get notified when updates match your criteria — meeting minutes, press releases, filings.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
								<circle cx="9" cy="7" r="4"/>
								<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
								<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Track Social Profiles</p>
							<p class="feature-desc">Track Instagram, X, and Facebook profiles — monitoring text and images for leads that match your beat.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M3 21h18"/>
								<path d="M5 21V7l8-4v18"/>
								<path d="M19 21V11l-6-4"/>
								<path d="M9 9v.01"/>
								<path d="M9 12v.01"/>
								<path d="M9 15v.01"/>
								<path d="M9 18v.01"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Track City Council</p>
							<p class="feature-desc">Monitor council pages for new documents, extract promises from meeting minutes, and get alerted when deadlines approach.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<ellipse cx="12" cy="5" rx="9" ry="3"/>
								<path d="M3 5V19a9 3 0 0 0 18 0V5"/>
								<path d="M3 12a9 3 0 0 0 18 0"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Extract Data</p>
							<p class="feature-desc">Pull structured data from websites, Instagram, and X with AI-powered scraping. Turn unstructured content into usable information.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M22 2L11 13"/>
								<path d="M22 2L15 22L11 13L2 9L22 2"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">Feed &amp; Export</p>
							<p class="feature-desc">Scouts extract structured information units whenever they find a match. Use AI Select to pick the most relevant, and export to your CMS or via API.</p>
						</div>
					</div>
					<div class="feature-item">
						<div class="feature-icon">
							<svg class="feature-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<polyline points="16 18 22 12 16 6"/>
								<polyline points="8 6 2 12 8 18"/>
							</svg>
						</div>
						<div>
							<p class="feature-title">AI-Ready API</p>
							<p class="feature-desc">Create scouts, run searches, and process information units programmatically. Built for workflows with GPT, Claude, or your own tools.</p>
						</div>
					</div>
				</div>
			</div>

			<div class="footer-badges-container">
				<div class="footer-group">
					<p class="footer-label">SUPPORTED BY</p>
					<img src="/logos/logo_imj_schwarz.svg" alt="IMJ" class="footer-logo footer-logo-imj" />
				</div>
				<div class="footer-group">
					<p class="footer-label">IN PARTNERSHIP WITH</p>
					<div class="footer-logos-inline">
							<img src="/logos/biglocal.png" alt="Big Local" class="footer-logo footer-logo-biglocal footer-logo-desaturated" />
					</div>
				</div>
				<div class="footer-group">
					<span class="footer-label">AUTHENTICATION BY</span>
					<a href="https://www.muckrock.com" target="_blank" rel="noopener noreferrer">
						<img src="/logos/muckrock.png" alt="MuckRock" class="footer-logo footer-logo-muckrock footer-logo-desaturated" />
					</a>
				</div>
			</div>
		</div>
	</div>
</div>

<style>
	.login-container {
		min-height: 100vh;
		background: #fafaf9;
		position: relative;
		overflow-x: hidden;
		font-family: 'DM Sans', -apple-system, system-ui, sans-serif;
	}

	/* Animated background orbs */
	.bg-orbs {
		position: absolute;
		inset: 0;
		overflow: hidden;
		pointer-events: none;
		z-index: 0;
	}

	.orb {
		position: absolute;
		border-radius: 50%;
		filter: blur(80px);
		opacity: 0.15;
		animation: float 20s ease-in-out infinite;
	}

	.orb-1 {
		width: 500px;
		height: 500px;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		top: -10%;
		right: -10%;
		animation-delay: 0s;
	}

	.orb-2 {
		width: 400px;
		height: 400px;
		background: linear-gradient(135deg, #fbbf24, #f59e0b);
		bottom: -5%;
		left: -5%;
		animation-delay: -7s;
	}

	.orb-3 {
		width: 350px;
		height: 350px;
		background: linear-gradient(135deg, #818cf8, #6366f1);
		top: 40%;
		left: 50%;
		animation-delay: -14s;
	}

	@keyframes float {
		0%, 100% {
			transform: translate(0, 0) scale(1);
		}
		33% {
			transform: translate(30px, -30px) scale(1.1);
		}
		66% {
			transform: translate(-20px, 20px) scale(0.9);
		}
	}

	/* Subtle grid pattern */
	.grid-pattern {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(to right, #e7e5e4 1px, transparent 1px),
			linear-gradient(to bottom, #e7e5e4 1px, transparent 1px);
		background-size: 60px 60px;
		opacity: 0.3;
		z-index: 1;
	}

	/* Animated grid points */
	.grid-points {
		position: absolute;
		inset: 0;
		overflow: hidden;
		pointer-events: none;
		z-index: 2;
	}

	.point {
		position: absolute;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		box-shadow: 0 0 12px rgba(150, 139, 223, 0.6);
		opacity: 0.8;
	}

	.point-1 {
		top: 10%;
		left: 15%;
		animation: moveAlongGrid1 12s ease-in-out infinite;
	}

	.point-2 {
		top: 30%;
		left: 35%;
		animation: moveAlongGrid2 15s ease-in-out infinite;
		animation-delay: -3s;
	}

	.point-3 {
		top: 50%;
		left: 25%;
		animation: moveAlongGrid3 18s ease-in-out infinite;
		animation-delay: -6s;
	}

	.point-4 {
		top: 70%;
		left: 45%;
		animation: moveAlongGrid4 14s ease-in-out infinite;
		animation-delay: -9s;
	}

	.point-5 {
		top: 85%;
		left: 20%;
		animation: moveAlongGrid5 16s ease-in-out infinite;
		animation-delay: -12s;
	}

	@keyframes moveAlongGrid1 {
		0%, 100% {
			transform: translate(0, 0);
			opacity: 0.8;
		}
		25% {
			transform: translate(180px, 0);
			opacity: 1;
		}
		50% {
			transform: translate(180px, 240px);
			opacity: 0.8;
		}
		75% {
			transform: translate(0, 240px);
			opacity: 1;
		}
	}

	@keyframes moveAlongGrid2 {
		0%, 100% {
			transform: translate(0, 0);
			opacity: 0.8;
		}
		33% {
			transform: translate(-120px, 0);
			opacity: 1;
		}
		66% {
			transform: translate(-120px, -180px);
			opacity: 0.8;
		}
	}

	@keyframes moveAlongGrid3 {
		0%, 100% {
			transform: translate(0, 0);
			opacity: 0.8;
		}
		25% {
			transform: translate(0, -120px);
			opacity: 1;
		}
		50% {
			transform: translate(240px, -120px);
			opacity: 0.8;
		}
		75% {
			transform: translate(240px, 0);
			opacity: 1;
		}
	}

	@keyframes moveAlongGrid4 {
		0%, 100% {
			transform: translate(0, 0);
			opacity: 0.8;
		}
		50% {
			transform: translate(-180px, 120px);
			opacity: 1;
		}
	}

	@keyframes moveAlongGrid5 {
		0%, 100% {
			transform: translate(0, 0);
			opacity: 0.8;
		}
		33% {
			transform: translate(120px, 0);
			opacity: 1;
		}
		66% {
			transform: translate(120px, -60px);
			opacity: 0.8;
		}
	}

	.content-wrapper {
		position: relative;
		z-index: 3;
		max-width: 1440px;
		margin: 0 auto;
		padding: 2rem 1.25rem;
		min-height: 100vh;
		display: flex;
		flex-direction: column-reverse;
		gap: 3rem;
		align-items: flex-start;
	}

	@media (min-width: 768px) {
		.content-wrapper {
			padding: 3rem 2rem;
			gap: 4rem;
		}
	}

	@media (min-width: 1024px) {
		.content-wrapper {
			flex-direction: row;
			padding: 4rem 3rem;
			gap: 3rem;
			align-items: flex-start;
			justify-content: center;
		}
	}

	@media (min-width: 1280px) {
		.content-wrapper {
			padding: 5rem 4rem;
			gap: 5rem;
		}
	}

	/* Auth Panel Container - Fixed centered on left */
	.auth-panel-container {
		width: 100%;
		max-width: 420px;
		flex-shrink: 0;
	}

	@media (min-width: 1024px) {
		.auth-panel-container {
			position: fixed;
			left: 5rem;
			top: 50%;
			transform: translateY(-50%);
			width: 420px;
			max-width: calc(50vw - 6rem);
			z-index: 10;
		}
	}

	/* Auth Panel */
	.auth-panel {
		width: 100%;
		opacity: 0;
		transform: translateY(30px);
		transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
	}

	.auth-panel.mounted {
		opacity: 1;
		transform: translateY(0);
		transition-delay: 0.2s;
	}

	.auth-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 3rem 2rem;
		border-radius: 1.5rem;
		border: 1px solid rgba(0, 0, 0, 0.06);
		background: rgba(255, 255, 255, 0.6);
		backdrop-filter: blur(10px);
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
		gap: 1.5rem;
	}

	.auth-logo {
		height: 2rem;
		width: auto;
	}

	.brand-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
	}

	.auth-title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.75rem;
		font-weight: 600;
		color: #1c1917;
		margin: 0;
	}

	.auth-subtitle {
		color: #57534e;
		font-size: 0.9375rem;
		font-weight: 500;
		margin: 0;
	}

	.coming-soon-title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: #1c1917;
		margin: 0;
	}

	.coming-soon-text {
		color: #57534e;
		font-size: 0.9375rem;
		line-height: 1.6;
		text-align: center;
		margin: 0;
	}

	.auth-link-pricing {
		display: block;
		width: 100%;
		padding: 0.625rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: #78716c;
		text-decoration: none;
		text-align: center;
		background: transparent;
		border: 1px solid #e7e5e4;
		border-radius: 0.75rem;
		transition: all 0.2s ease;
	}
	.auth-link-pricing:hover {
		border-color: #968bdf;
		color: #968bdf;
	}

	.auth-oss-badge {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(0,0,0,0.06);
		text-align: center;
	}
	.auth-oss-text {
		font-size: 0.75rem;
		color: #a8a29e;
		margin: 0 0 0.5rem;
		line-height: 1.5;
	}
	.auth-oss-link {
		color: #78716c;
		text-decoration: none;
		font-weight: 500;
	}
	.auth-oss-link:hover { color: #968bdf; text-decoration: underline; }
	.auth-github-link {
		display: inline-flex;
		align-items: center;
		padding: 0.375rem 0.875rem;
		font-size: 0.75rem;
		color: #78716c;
		text-decoration: none;
		font-weight: 600;
		border: 1px solid #e7e5e4;
		border-radius: 0.5rem;
		transition: all 0.2s ease;
	}
	.auth-github-link:hover {
		border-color: #968bdf;
		color: #968bdf;
	}

	.sign-in-button {
		width: 100%;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		color: white;
		font-weight: 600;
		padding: 0.75rem 1.5rem;
		border-radius: 0.75rem;
		border: none;
		font-size: 1.125rem;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
		box-shadow: 0 2px 12px rgba(150, 139, 223, 0.3);
		position: relative;
		overflow: hidden;
	}

	.sign-in-button::before {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent);
		opacity: 0;
		transition: opacity 0.3s ease;
	}

	.sign-in-button:hover::before {
		opacity: 1;
	}

	.sign-in-button:hover {
		transform: translateY(-1px);
		box-shadow: 0 4px 16px rgba(150, 139, 223, 0.4);
	}

	.sign-in-button:active {
		transform: translateY(0);
	}

	/* Story Panel */
	.story-panel {
		flex: 1;
		max-width: 800px;
		color: #1c1917;
		opacity: 0;
		transform: translateY(30px);
		transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
	}

	.story-panel.mounted {
		opacity: 1;
		transform: translateY(0);
		transition-delay: 0.4s;
	}

	@media (min-width: 1024px) {
		.story-panel {
			margin-left: calc(420px + 3rem);
			padding: 0;
		}
	}

	@media (min-width: 1280px) {
		.story-panel {
			margin-left: calc(420px + 5rem);
		}
	}

	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		border: 1.5px solid #968bdf;
		border-radius: 9999px;
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.15em;
		color: #57534e;
		margin-bottom: 2rem;
		transition: all 0.3s ease;
	}

	.badge:hover {
		border-color: #7c6fc7;
		background: rgba(150, 139, 223, 0.05);
	}

	.badge-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		animation: pulse-dot 2s ease-in-out infinite;
	}

	@keyframes pulse-dot {
		0%, 100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.5;
			transform: scale(0.85);
		}
	}

	.headline-logo {
		display: block;
		height: clamp(2.5rem, 6vw, 4rem);
		width: auto;
		margin-bottom: 1.5rem;
	}

	.tagline {
		font-size: clamp(1.125rem, 2vw, 1.375rem);
		line-height: 1.6;
		color: #57534e;
		margin-bottom: 3rem;
		font-weight: 400;
	}

	.highlight-muted {
		font-weight: 600;
		color: #78716c;
	}

	.highlight-accent {
		font-weight: 700;
		background: linear-gradient(135deg, #968bdf 0%, #7c6fc7 100%);
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
	}

	.description-block {
		margin-bottom: 3rem;
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.subheadline {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: clamp(1.5rem, 3vw, 2rem);
		font-weight: 600;
		line-height: 1.3;
		color: #1c1917;
		letter-spacing: -0.01em;
	}

	.feature-list {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.feature-item {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
		padding: 1.25rem;
		border-radius: 0.875rem;
		background: rgba(255, 255, 255, 0.5);
		border: 1px solid rgba(0, 0, 0, 0.04);
		transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
	}

	.feature-item:hover {
		background: rgba(255, 255, 255, 0.8);
		border-color: rgba(150, 139, 223, 0.2);
		transform: translateX(4px);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
	}

	.feature-icon {
		flex-shrink: 0;
		width: 2.25rem;
		height: 2.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.5rem;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		color: white;
	}

	.feature-icon-svg {
		width: 1.25rem;
		height: 1.25rem;
	}

	.feature-title {
		font-weight: 600;
		font-size: 0.875rem;
		color: #1c1917;
		margin: 0 0 0.25rem 0;
		line-height: 1.4;
	}

	.feature-desc {
		color: #57534e;
		line-height: 1.6;
		font-size: 0.875rem;
		margin: 0;
	}

	.footer-badges-container {
		display: flex;
		flex-direction: row;
		flex-wrap: wrap;
		gap: 2.5rem;
		padding-top: 2rem;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
	}

	.footer-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}

	.footer-label {
		font-size: 0.675rem;
		font-weight: 700;
		letter-spacing: 0.15em;
		color: #a8a29e;
		margin: 0;
	}

	.footer-logo {
		height: 2.25rem;
		opacity: 0.5;
		transition: opacity 0.3s ease;
	}

	.footer-logo:hover {
		opacity: 0.8;
	}

	.footer-logos-inline {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		flex-wrap: wrap;
	}

	.footer-logo-imj {
		margin-top: 6px;
	}

	.footer-logo-biglocal {
		height: 3rem;
	}

	.footer-logo-muckrock {
		height: 2rem;
		border-radius: 4px;
	}

	.footer-logo-desaturated {
		filter: grayscale(1);
	}

	/* Mobile: center footer logos and labels */
	@media (max-width: 640px) {
		.footer-badges-container {
			flex-direction: column;
			align-items: center;
			text-align: center;
		}

		.footer-group {
			align-items: center;
			width: 100%;
		}

		.footer-logos-inline {
			justify-content: center;
		}
	}

	/* Responsive adjustments */
	@media (max-width: 640px) {
		.headline-logo {
			height: 2.25rem;
		}

		.tagline {
			font-size: 1.0625rem;
		}

		.subheadline {
			font-size: 1.375rem;
		}

		.feature-item {
			padding: 1rem;
		}

		.footer-badges-container {
			gap: 1.5rem;
		}
	}

	/* Prevent horizontal overflow on very small screens */
	@media (max-width: 375px) {
		.content-wrapper {
			padding: 2rem 1rem;
		}

		.badge {
			font-size: 0.625rem;
			padding: 0.375rem 0.75rem;
		}
	}
</style>
