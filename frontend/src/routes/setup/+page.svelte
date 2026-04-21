<script lang="ts">
	import { ArrowLeft, Copy, Check, Bot, Terminal } from 'lucide-svelte';

	let copiedId = '';
	let activeTab: 'agent' | 'manual' = 'agent';

	const agentSteps = [
		{ title: 'Clones the repo', desc: 'git clone https://github.com/buriedsignals/cojournalist-os' },
		{ title: 'Checks your environment', desc: 'Node 22 LTS, git, npm, Supabase CLI' },
		{ title: 'Collects your API keys', desc: 'Gemini, Firecrawl, Resend, Apify (required); MapTiler and OpenRouter (optional)' },
		{ title: 'Sets up Supabase', desc: 'Managed cloud (supabase.com) or self-hosted Docker' },
		{ title: 'Deploys Edge Functions', desc: 'All Supabase edge functions pushed and wired to cron' },
		{ title: 'Builds and deploys the frontend', desc: 'Render, Cloudflare Pages, Vercel, or any static host' },
		{ title: 'Verifies everything works', desc: 'Health check plus a first scout end-to-end' }
	];

	const agentPrompt = `Clone https://github.com/buriedsignals/cojournalist-os and read automation/SETUP_AGENT.md — it contains the full deployment plan. Follow the steps in order, asking me for each API key, database credential, and deployment choice (Render vs Docker) as you go. Do not skip any step or assume values — prompt me for every decision and secret.`;

	const manualSteps = [
		{ title: 'Install Node 22 LTS', desc: 'Required runtime. Install via nvm (nvm install 22) or Homebrew (brew install node@22).' },
		{ title: 'Get your API keys', desc: 'Gemini, Firecrawl, Resend, Apify (required). MapTiler, OpenRouter (optional).' },
		{ title: 'Verify Resend domain', desc: 'Add and verify your sending domain at resend.com/domains before configuring email.' },
		{ title: 'Clone the repository', desc: 'git clone https://github.com/buriedsignals/cojournalist-os' },
		{ title: 'Set up Supabase', desc: 'Create a managed project on supabase.com or run self-hosted via Docker.' },
		{ title: 'Run database migrations', desc: 'supabase db push' },
		{ title: 'Deploy Edge Functions', desc: 'supabase functions deploy --all' },
		{ title: 'Configure environment', desc: 'Copy .env.example, fill in your API keys and Supabase credentials.' },
		{ title: 'Build and deploy the frontend', desc: 'cd frontend && npm ci && npm run build, then serve the static build on any host.' },
		{ title: 'Verify and create first user', desc: 'Check /health, then sign up via the frontend.' }
	];

	async function copyText(id: string, text: string) {
		await navigator.clipboard.writeText(text);
		copiedId = id;
		setTimeout(() => (copiedId = ''), 2000);
	}
</script>

<svelte:head>
	<title>Self-host — coJournalist</title>
	<meta name="description" content="Run your own coJournalist instance — fork the repo, provision Supabase, deploy edge functions, and connect your AI agent." />
</svelte:head>

<div class="setup-page">
	<div class="bg-pattern"></div>
	<div class="bg-gradient"></div>
	<div class="bg-gradient-secondary"></div>

	<div class="content">
		<a class="back-button" href="/docs">
			<ArrowLeft class="w-4 h-4" />
			<span>Back to docs</span>
		</a>

		<header class="header">
			<div class="badge">SETUP GUIDE</div>
			<h1 class="title">
				Self-host your <span class="gradient-text">newsroom</span>
			</h1>
			<p class="subtitle">
				Drop an AI coding agent into the repo, run the setup skill, and it provisions everything —
				Supabase, edge functions, and the frontend. Or follow the manual path below.
			</p>
		</header>

		<!-- Prerequisites callout -->
		<div class="prerequisites-note">
			<strong>Prerequisites:</strong> Node 22 LTS, Docker (only if you self-host Supabase), and a verified domain in Resend for email notifications.
		</div>

		<!-- Tab selector -->
		<div class="tab-selector">
			<button
				class="tab-button"
				class:active={activeTab === 'agent'}
				on:click={() => (activeTab = 'agent')}
			>
				<Bot class="w-4 h-4" />
				Agent install
			</button>
			<button
				class="tab-button"
				class:active={activeTab === 'manual'}
				on:click={() => (activeTab = 'manual')}
			>
				<Terminal class="w-4 h-4" />
				Manual install
			</button>
		</div>

		{#if activeTab === 'agent'}
			<div class="tab-content">
				<div class="step-label">Paste this prompt into your agent</div>
				<div class="code-block-wrapper">
					<button class="copy-button" on:click={() => copyText('prompt', agentPrompt)} aria-label="Copy agent prompt">
						{#if copiedId === 'prompt'}
							<Check class="w-4 h-4" />
						{:else}
							<Copy class="w-4 h-4" />
						{/if}
					</button>
					<pre class="code-block"><code>{agentPrompt}</code></pre>
				</div>

				<div class="steps-section">
					<h2 class="steps-heading">What your agent will do</h2>
					<div class="steps-grid">
						{#each agentSteps as step, i}
							<div class="step-card">
								<div class="step-number">{i + 1}</div>
								<div class="step-content">
									<p class="step-title">{step.title}</p>
									<p class="step-desc">{step.desc}</p>
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>
		{:else}
			<div class="tab-content">
				<div class="manual-highlight">
					<div class="step-label">Automated setup script</div>
					<p class="manual-highlight-desc">
						Run <code>automation/setup.sh</code> to walk through deployment interactively. It handles cloning, API-key collection, Supabase setup, and deployment.
					</p>
					<div class="code-block-wrapper">
						<button class="copy-button" on:click={() => copyText('setup-sh', 'bash automation/setup.sh')} aria-label="Copy setup.sh command">
							{#if copiedId === 'setup-sh'}
								<Check class="w-4 h-4" />
							{:else}
								<Copy class="w-4 h-4" />
							{/if}
						</button>
						<pre class="code-block"><code>bash automation/setup.sh</code></pre>
					</div>
				</div>

				<div class="steps-section">
					<h2 class="steps-heading">Manual steps</h2>
					<div class="steps-grid">
						{#each manualSteps as step, i}
							<div class="step-card">
								<div class="step-number">{i + 1}</div>
								<div class="step-content">
									<p class="step-title">{step.title}</p>
									<p class="step-desc">{step.desc}</p>
								</div>
							</div>
						{/each}
					</div>
				</div>

				<div class="repo-section">
					<pre class="manual-code"><code>git clone https://github.com/buriedsignals/cojournalist-os</code></pre>
					<a
						class="github-link"
						href="https://github.com/buriedsignals/cojournalist-os"
						target="_blank"
						rel="noopener noreferrer"
					>
						<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
							<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
						</svg>
						View on GitHub
					</a>
					<p class="repo-note">Full deployment reference in <code>deploy/SETUP.md</code> and <code>automation/SETUP_AGENT.md</code>.</p>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.setup-page {
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
		background: radial-gradient(ellipse, rgba(107, 63, 160, 0.12) 0%, transparent 70%);
		pointer-events: none;
	}

	.bg-gradient-secondary {
		position: absolute;
		bottom: 0;
		right: -200px;
		width: 600px;
		height: 600px;
		background: radial-gradient(ellipse, rgba(107, 63, 160, 0.06) 0%, transparent 70%);
		pointer-events: none;
	}

	.content {
		position: relative;
		z-index: 1;
		max-width: 700px;
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
		margin-bottom: 2.5rem;
	}

	.badge {
		display: inline-block;
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
		background: linear-gradient(135deg, #6B3FA0, #4E2C78);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.subtitle {
		font-size: 1.0625rem;
		color: var(--color-text-secondary);
		max-width: 560px;
		margin: 0 auto;
		line-height: 1.5;
	}

	.prerequisites-note {
		padding: 0.875rem 1rem;
		background: #fff7ed;
		border: 1px solid #fed7aa;
		color: #7c2d12;
		border-radius: 0.625rem;
		font-size: 0.875rem;
		line-height: 1.55;
		margin-bottom: 1.5rem;
	}
	.prerequisites-note strong {
		color: #9a3412;
	}

	.tab-selector {
		display: inline-flex;
		padding: 0.25rem;
		background: #f3f4f6;
		border-radius: 0.625rem;
		margin-bottom: 1.25rem;
	}
	.tab-button {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4375rem 0.875rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-text-secondary);
		background: transparent;
		border: none;
		border-radius: 0.4375rem;
		cursor: pointer;
		transition: all 0.15s ease;
	}
	.tab-button.active {
		background: white;
		color: var(--color-accent-dark);
		box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
	}

	.tab-content {
		display: flex;
		flex-direction: column;
		gap: 1.75rem;
	}

	.step-label {
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--color-text-tertiary);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin-bottom: 0.625rem;
	}

	.code-block-wrapper {
		position: relative;
	}
	.code-block {
		margin: 0;
		padding: 1rem 3rem 1rem 1rem;
		background: #1c1917;
		color: #f5f5f4;
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8125rem;
		line-height: 1.6;
		border-radius: 0.625rem;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-word;
	}
	.copy-button {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.375rem;
		background: rgba(255, 255, 255, 0.08);
		color: #f5f5f4;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.15s ease;
	}
	.copy-button:hover {
		background: rgba(255, 255, 255, 0.16);
	}

	.steps-heading {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin: 0 0 0.875rem 0;
	}

	.steps-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.625rem;
	}
	@media (min-width: 640px) {
		.steps-grid {
			grid-template-columns: 1fr 1fr;
		}
	}

	.step-card {
		display: grid;
		grid-template-columns: 2rem 1fr;
		gap: 0.75rem;
		padding: 0.875rem 1rem;
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.625rem;
	}
	.step-number {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		background: linear-gradient(135deg, #4E2C78 0%, #5b4bbd 100%);
		color: white;
		font-size: 0.8125rem;
		font-weight: 600;
		border-radius: 999px;
		box-shadow: 0 1px 2px rgba(91, 75, 189, 0.25);
	}
	.step-title {
		margin: 0 0 0.125rem 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}
	.step-desc {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	.manual-highlight {
		padding: 1rem 1.25rem;
		background: #faf9ff;
		border: 1px solid #e2dcf7;
		border-radius: 0.75rem;
	}
	.manual-highlight-desc {
		margin: 0 0 0.625rem 0;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.55;
	}
	.manual-highlight-desc code {
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8125rem;
		padding: 0.0625rem 0.3125rem;
		background: rgba(78, 44, 120, 0.1);
		color: #5b4bbd;
		border-radius: 0.25rem;
	}

	.repo-section {
		padding: 1.125rem 1.25rem;
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
	}
	.manual-code {
		margin: 0 0 0.75rem 0;
		padding: 0.625rem 0.875rem;
		background: #f9fafb;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8125rem;
		color: var(--color-text-primary);
	}
	.github-link {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.4375rem 0.75rem;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-text-primary);
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		text-decoration: none;
		transition: all 0.15s ease;
	}
	.github-link:hover {
		border-color: var(--color-accent);
		color: var(--color-accent-dark);
	}
	.repo-note {
		margin: 0.5rem 0 0 0;
		font-size: 0.8125rem;
		color: var(--color-text-tertiary);
	}
	.repo-note code {
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.75rem;
		padding: 0.0625rem 0.3125rem;
		background: rgba(78, 44, 120, 0.1);
		color: #5b4bbd;
		border-radius: 0.25rem;
	}
</style>
