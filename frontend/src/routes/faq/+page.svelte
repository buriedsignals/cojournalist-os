<script lang="ts">
	import { ArrowLeft } from 'lucide-svelte';
</script>

<svelte:head>
	<title>FAQ - coJournalist</title>
</svelte:head>

<div class="faq-page">
	<div class="bg-pattern"></div>
	<div class="bg-gradient"></div>

	<div class="content">
		<a class="back-button" href="/login">
			<ArrowLeft class="w-4 h-4" />
			<span>Back</span>
		</a>

		<header class="header">
			<div class="badge">FAQ</div>
			<h1 class="title">
				Frequently Asked <span class="gradient-text">Questions</span>
			</h1>
			<p class="subtitle">Licensing, self-hosting, and how coJournalist works for newsrooms.</p>
		</header>

		<div class="faq-list">
			<section class="faq-section">
				<h2 class="section-title">Licensing</h2>

				<details class="faq-item">
					<summary class="faq-question">What license does coJournalist use?</summary>
					<div class="faq-answer">
						<p>coJournalist uses the <strong>Sustainable Use License</strong>, a fair-code license. It allows free use, modification, and redistribution for internal purposes, with restrictions on reselling or offering the software as a hosted service.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">Can I use coJournalist in my newsroom?</summary>
					<div class="faq-answer">
						<p><strong>Yes.</strong> You can deploy, modify, and use coJournalist for your newsroom's internal operations — monitoring beats, tracking sources, generating leads, and producing content. This is exactly what the license is designed for.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">Can I modify the code?</summary>
					<div class="faq-answer">
						<p><strong>Yes.</strong> You can modify coJournalist to fit your newsroom's needs — add custom scout types, change the UI, integrate with your CMS, or adapt it for your editorial workflow. Your modifications are for your internal use.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">What am I NOT allowed to do?</summary>
					<div class="faq-answer">
						<ul>
							<li><strong>Resell it</strong> — you cannot sell coJournalist or a derivative as a standalone product</li>
							<li><strong>Offer it as a service</strong> — you cannot host it and charge others for access (SaaS, managed service)</li>
							<li><strong>White-label it</strong> — you cannot rebrand it and distribute it as your own product</li>
						</ul>
						<p>In short: use it for your journalism, don't compete with us by selling it.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">Is coJournalist open source?</summary>
					<div class="faq-answer">
						<p>coJournalist is <strong>source-available</strong> under the Sustainable Use License. All code is public and readable on GitHub. The license is more permissive than proprietary software but more restrictive than MIT or Apache 2.0 — specifically, it prevents using the software to compete with the original product. This is the same model used by <a href="https://n8n.io" target="_blank" rel="noopener noreferrer">n8n</a>, <a href="https://cal.com" target="_blank" rel="noopener noreferrer">Cal.com</a>, and other fair-code projects.</p>
					</div>
				</details>
			</section>

			<section class="faq-section">
				<h2 class="section-title">Self-Hosted License</h2>

				<details class="faq-item">
					<summary class="faq-question">What does the annual license include?</summary>
					<div class="faq-answer">
						<p>The self-hosted license (CHF 180/year) includes:</p>
						<ul>
							<li><strong>Automated deployment</strong> — a setup skill that gets you running in minutes with any AI coding agent</li>
							<li><strong>Automatic updates</strong> — new features and fixes delivered to your deployment without manual work</li>
							<li><strong>All features</strong> — every scout type, export, API, and integration</li>
						</ul>
						<p>Without a license, you still have the full source code and can deploy manually. The license saves you the operational work.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">What do I need to provide?</summary>
					<div class="faq-answer">
						<p>You bring your own API keys and hosting:</p>
						<ul>
							<li><strong>Supabase</strong> — managed (supabase.com) or self-hosted via Docker</li>
							<li><strong>Gemini API key</strong> — for AI analysis and embeddings</li>
							<li><strong>Firecrawl API key</strong> — for web scraping and search</li>
							<li><strong>Resend API key</strong> — for email notifications</li>
							<li><strong>Apify API token</strong> — for social media monitoring</li>
							<li><strong>Hosting</strong> — Render, Docker, or any PaaS that runs Python</li>
						</ul>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">What happens if I stop paying?</summary>
					<div class="faq-answer">
						<p>Your deployment keeps running — the application itself has no license key checks. Only the automated update pipeline stops. You keep the code at your last version and can continue using it indefinitely. You just won't receive new features automatically.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">Can I deploy without the license?</summary>
					<div class="faq-answer">
						<p><strong>Yes.</strong> The full source code is public. You can clone the repository and deploy manually by following the setup documentation. The license key only gates the automation scripts that make deployment faster — it does not gate any application features.</p>
					</div>
				</details>
			</section>

			<section class="faq-section">
				<h2 class="section-title">Product</h2>

				<details class="faq-item">
					<summary class="faq-question">What is coJournalist?</summary>
					<div class="faq-answer">
						<p>coJournalist is an AI-powered local news monitoring platform. It helps journalists and newsrooms track beats, monitor sources, and surface story leads through automated scouts that watch the web, social media, and government pages on a schedule.</p>
					</div>
				</details>

				<details class="faq-item">
					<summary class="faq-question">What's the difference between the hosted and self-hosted versions?</summary>
					<div class="faq-answer">
						<p><strong>Hosted (cojournalist.ai)</strong> — we run everything. Sign in with MuckRock, pay per credits, no setup needed.</p>
						<p><strong>Self-hosted</strong> — you run it on your own infrastructure (Supabase + Render/Docker). No credit limits, full control, bring your own API keys. Annual license for automated deployment and updates.</p>
						<p>Both versions have the same features — every scout type, every integration.</p>
					</div>
				</details>
			</section>
		</div>

		<p class="footer-note">
			More questions? <a href="mailto:tom@buriedsignals.com">Get in touch</a>.
		</p>
	</div>
</div>

<style>
	.faq-page {
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

	.content {
		position: relative;
		z-index: 1;
		max-width: 720px;
		margin: 0 auto;
		padding: 2rem 1.5rem 4rem;
	}

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

	.faq-list {
		display: flex;
		flex-direction: column;
		gap: 2.5rem;
	}

	.section-title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.375rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 1rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.faq-item {
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		transition: box-shadow 0.2s ease;
	}

	.faq-item:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
	}

	.faq-item[open] {
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
	}

	.faq-question {
		padding: 1rem 1.25rem;
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
		cursor: pointer;
		list-style: none;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.faq-question::-webkit-details-marker {
		display: none;
	}

	.faq-question::after {
		content: '+';
		font-size: 1.25rem;
		font-weight: 400;
		color: var(--color-text-tertiary);
		transition: transform 0.2s ease;
	}

	.faq-item[open] .faq-question::after {
		content: '−';
		color: var(--color-accent);
	}

	.faq-answer {
		padding: 0 1.25rem 1.25rem;
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.faq-answer p {
		margin: 0 0 0.75rem;
	}

	.faq-answer p:last-child {
		margin-bottom: 0;
	}

	.faq-answer ul {
		margin: 0.5rem 0;
		padding-left: 1.25rem;
	}

	.faq-answer li {
		margin-bottom: 0.5rem;
	}

	.faq-answer a {
		color: var(--color-accent);
		text-decoration: none;
		font-weight: 500;
	}

	.faq-answer a:hover {
		text-decoration: underline;
	}

	.footer-note {
		text-align: center;
		font-size: 0.875rem;
		color: var(--color-text-tertiary);
		margin-top: 3rem;
	}

	.footer-note a {
		color: var(--color-accent);
		text-decoration: none;
		font-weight: 500;
	}

	.footer-note a:hover {
		text-decoration: underline;
	}

	@media (max-width: 640px) {
		.content {
			padding: 1.5rem 1rem 3rem;
		}
	}
</style>
