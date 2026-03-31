<script lang="ts">
	import { ArrowLeft, Copy, Check, Bot, Download, Terminal } from 'lucide-svelte';

	let licenseKey = '';
	let state: 'idle' | 'loading' | 'success' | 'error' = 'idle';
	let errorMessage = '';
	let copiedId = '';
	let downloading = false;
	let filesData: Record<string, string> | null = null;
	let activeTab: 'agent' | 'manual' = 'agent';

	const steps = [
		{ title: 'Validates your license', desc: 'Confirms your key is active' },
		{ title: 'Checks your environment', desc: 'git, node, npm, Supabase CLI' },
		{ title: 'Collects your API keys', desc: 'Gemini, Firecrawl, Resend, Apify, and more' },
		{ title: 'Sets up Supabase', desc: 'Managed cloud or self-hosted Docker' },
		{ title: 'Deploys your instance', desc: 'Render, Docker, or any PaaS' },
		{ title: 'Verifies everything works', desc: 'Health check and first scout' }
	];

	const agentPrompt = `Read SETUP_AGENT.md in this directory — it contains the full 10-step deployment plan for coJournalist. The supporting devops files (render.yaml, setup.sh, SETUP.md) are already downloaded here too. Follow the steps in order, asking me for each API key, database credential, and deployment choice (Render vs Docker) as you go. Do not skip any step or assume values — prompt me for every decision and secret.`;

	const manualSteps = [
		{ title: 'Get your API keys', desc: 'Gemini, Firecrawl, Resend, Apify (required). MapTiler, OpenRouter (optional).' },
		{ title: 'Clone the repository', desc: 'git clone https://github.com/buriedsignals/cojournalist-os' },
		{ title: 'Set up Supabase', desc: 'Create a managed project on supabase.com or run self-hosted via Docker.' },
		{ title: 'Run database migrations', desc: 'supabase db push or run migration files in order.' },
		{ title: 'Deploy Edge Functions', desc: 'supabase functions deploy execute-scout && manage-schedule' },
		{ title: 'Configure environment', desc: 'Copy .env.example, fill in your API keys and Supabase credentials.' },
		{ title: 'Deploy the application', desc: 'Use render.yaml for Render, or docker compose up -d for self-hosted.' },
		{ title: 'Verify and create first user', desc: 'Check /api/health, then sign up via the frontend.' }
	];

	async function handleSubmit() {
		if (!licenseKey.trim()) return;
		state = 'loading';
		errorMessage = '';

		try {
			const response = await fetch('/api/license/setup-guide', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ key: licenseKey.trim() })
			});

			if (response.ok) {
				const data = await response.json();
				filesData = data.files;
				state = 'success';
			} else {
				const data = await response.json();
				errorMessage = data.error || 'Invalid license key';
				state = 'error';
			}
		} catch {
			errorMessage = 'Connection error. Please try again.';
			state = 'error';
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			handleSubmit();
		}
	}

	async function copyText(id: string, text: string) {
		await navigator.clipboard.writeText(text);
		copiedId = id;
		setTimeout(() => (copiedId = ''), 2000);
	}

	async function downloadFiles() {
		if (!filesData) return;
		downloading = true;
		for (const [name, content] of Object.entries(filesData)) {
			if (!content) continue;
			const blob = new Blob([content], { type: 'text/plain' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = name;
			a.click();
			URL.revokeObjectURL(url);
			await new Promise((r) => setTimeout(r, 200));
		}
		downloading = false;
	}
</script>

<svelte:head>
	<title>Setup Guide - coJournalist</title>
</svelte:head>

<div class="setup-page">
	<div class="bg-pattern"></div>
	<div class="bg-gradient"></div>
	<div class="bg-gradient-secondary"></div>

	<div class="content">
		<a class="back-button" href="/pricing">
			<ArrowLeft class="w-4 h-4" />
			<span>Back</span>
		</a>

		<header class="header">
			<div class="badge">SETUP GUIDE</div>

			{#if state === 'success'}
				<h1 class="title">
					Your guide is <span class="gradient-text">ready</span>
				</h1>
			{:else}
				<h1 class="title">
					Deploy your <span class="gradient-text">newsroom</span>
				</h1>
				<p class="subtitle">Enter your license key to access your deployment guide</p>
			{/if}
		</header>

		{#if state === 'success'}
			<!-- Download section (always visible, above tabs) -->
			<div class="download-card">
				<button
					class="download-button"
					on:click={downloadFiles}
					disabled={downloading || !filesData}
				>
					<Download class="w-4 h-4" />
					{#if downloading}
						Downloading...
					{:else}
						Download Deployment Files
					{/if}
				</button>
				<p class="download-subtext">SETUP_AGENT.md, render.yaml, setup.sh, sync-upstream.yml, SETUP.md</p>
			</div>

			<!-- Tab selector -->
			<div class="tab-selector">
				<button
					class="tab-button"
					class:active={activeTab === 'agent'}
					on:click={() => (activeTab = 'agent')}
				>
					<Bot class="w-4 h-4" />
					Agent Install
				</button>
				<button
					class="tab-button"
					class:active={activeTab === 'manual'}
					on:click={() => (activeTab = 'manual')}
				>
					<Terminal class="w-4 h-4" />
					Manual Install
				</button>
			</div>

			<!-- Agent tab -->
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

					<!-- Steps overview -->
					<div class="steps-section">
						<h2 class="steps-heading">What your agent will do</h2>
						<div class="steps-grid">
							{#each steps as step, i}
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
			{/if}

			<!-- Manual tab -->
			{#if activeTab === 'manual'}
				<div class="tab-content">
					<!-- Automated script option -->
					<div class="manual-highlight">
						<div class="step-label">Automated setup script</div>
						<p class="manual-highlight-desc">Run the included setup.sh to walk through deployment interactively. It handles cloning, API key collection, Supabase setup, and deployment.</p>
						<div class="code-block-wrapper">
							<button class="copy-button" on:click={() => copyText('setup-sh', 'export COJOURNALIST_LICENSE_KEY="' + licenseKey + '" && bash setup.sh')} aria-label="Copy setup.sh command">
								{#if copiedId === 'setup-sh'}
									<Check class="w-4 h-4" />
								{:else}
									<Copy class="w-4 h-4" />
								{/if}
							</button>
							<pre class="code-block"><code>export COJOURNALIST_LICENSE_KEY="{licenseKey}" && bash setup.sh</code></pre>
						</div>
					</div>

					<!-- Manual steps overview -->
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

					<!-- Repo link -->
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
						<p class="repo-note">Full documentation in SETUP.md (included in your download)</p>
					</div>
				</div>
			{/if}
		{:else}
			<!-- License key input card -->
			<div class="input-card">
				<label class="input-label" for="license-key">License Key</label>
				<input
					id="license-key"
					class="input-field"
					type="text"
					placeholder="cjl_xxxxxxxx-xxxxxxxx-xxxxxxxx-xxxxxxxx"
					bind:value={licenseKey}
					on:keydown={handleKeydown}
					disabled={state === 'loading'}
				/>
				<button
					class="submit-button"
					on:click={handleSubmit}
					disabled={state === 'loading' || !licenseKey.trim()}
				>
					{#if state === 'loading'}
						Validating...
					{:else}
						Unlock Setup Guide
					{/if}
				</button>

				{#if state === 'error' && errorMessage}
					<div class="inline-error">
						<span>{errorMessage}</span>
					</div>
				{/if}
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
		background: radial-gradient(ellipse, rgba(150, 139, 223, 0.12) 0%, transparent 70%);
		pointer-events: none;
	}

	.bg-gradient-secondary {
		position: absolute;
		bottom: 0;
		right: -200px;
		width: 600px;
		height: 600px;
		background: radial-gradient(ellipse, rgba(150, 139, 223, 0.06) 0%, transparent 70%);
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
		margin-bottom: 2.5rem;
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

	/* Input card */
	.input-card {
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 2rem;
	}

	.input-label {
		display: block;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 0.5rem;
	}

	.input-field {
		width: 100%;
		padding: 0.75rem 1rem;
		font-size: 0.9375rem;
		font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, Consolas, monospace;
		color: var(--color-text-primary);
		background: var(--color-bg-primary);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		outline: none;
		transition: border-color 0.2s ease;
		box-sizing: border-box;
	}

	.input-field::placeholder {
		color: var(--color-text-tertiary);
	}

	.input-field:focus {
		border-color: var(--color-accent);
		box-shadow: 0 0 0 3px rgba(150, 139, 223, 0.1);
	}

	.input-field:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.submit-button {
		width: 100%;
		margin-top: 1rem;
		padding: 0.875rem;
		font-size: 0.9375rem;
		font-weight: 600;
		color: white;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.submit-button:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 8px 20px rgba(150, 139, 223, 0.3);
	}

	.submit-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.inline-error {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		color: #dc2626;
		background: rgba(220, 38, 38, 0.06);
		border: 1px solid rgba(220, 38, 38, 0.15);
		border-radius: 0.5rem;
	}

	/* Download card */
	.download-card {
		text-align: center;
		padding: 1.5rem;
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 1.5rem;
	}

	.download-button {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 2rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: white;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.download-button:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(150, 139, 223, 0.3);
	}

	.download-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.download-subtext {
		font-size: 0.75rem;
		color: var(--color-text-tertiary);
		margin: 0.5rem 0 0;
	}

	/* Tab selector */
	.tab-selector {
		display: flex;
		gap: 0;
		background: var(--color-bg-primary);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.25rem;
		margin-bottom: 1.5rem;
	}

	.tab-button {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.625rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-text-tertiary);
		background: transparent;
		border: none;
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tab-button:hover:not(.active) {
		color: var(--color-text-secondary);
	}

	.tab-button.active {
		color: var(--color-accent-dark);
		background: white;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
	}

	/* Tab content */
	.tab-content {
		animation: fadeIn 0.15s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(4px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.step-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-text-tertiary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 0.5rem;
	}

	/* Code blocks */
	.code-block-wrapper {
		position: relative;
	}

	.copy-button {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 0.375rem;
		color: rgba(255, 255, 255, 0.7);
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.copy-button:hover {
		background: rgba(255, 255, 255, 0.2);
		color: white;
	}

	.code-block {
		background: #1a1a1a;
		border-radius: 0.75rem;
		padding: 1.25rem;
		padding-right: 3.5rem;
		overflow-x: auto;
		margin: 0;
	}

	.code-block code {
		font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, Consolas, monospace;
		font-size: 0.8125rem;
		line-height: 1.6;
		color: #e5e5e5;
		white-space: pre-wrap;
		word-break: break-all;
	}

	/* Steps section */
	.steps-section {
		margin-top: 2rem;
	}

	.steps-heading {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 1rem;
	}

	.steps-grid {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.step-card {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
		transition: all 0.2s ease;
	}

	.step-card:hover {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
	}

	.step-number {
		flex-shrink: 0;
		width: 2rem;
		height: 2rem;
		background: linear-gradient(135deg, #968bdf, #7c6fc7);
		color: white;
		font-size: 0.8125rem;
		font-weight: 700;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.step-content {
		flex: 1;
	}

	.step-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin: 0 0 0.125rem;
	}

	.step-desc {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		margin: 0;
	}

	/* Manual tab */
	.manual-highlight {
		background: white;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.manual-highlight-desc {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		margin: 0.25rem 0 1rem;
		line-height: 1.6;
	}

	.repo-section {
		text-align: center;
		padding: 1.5rem;
		margin-top: 2rem;
		background: rgba(150, 139, 223, 0.04);
		border: 1px solid rgba(150, 139, 223, 0.1);
		border-radius: 0.75rem;
	}

	.repo-note {
		font-size: 0.75rem;
		color: var(--color-text-tertiary);
		margin: 0.75rem 0 0;
	}

	.manual-code {
		display: inline-block;
		background: var(--color-bg-primary);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		margin: 0 0 1rem;
	}

	.manual-code code {
		font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, Consolas, monospace;
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
	}

	.github-link {
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

	.github-link:hover {
		border-color: #968bdf;
		color: #968bdf;
		box-shadow: 0 2px 8px rgba(150, 139, 223, 0.12);
	}

	/* Responsive */
	@media (max-width: 640px) {
		.code-block code {
			font-size: 0.75rem;
		}
	}
</style>
