<script lang="ts">
	import { Landmark, Search, CheckSquare, Square } from 'lucide-svelte';
	import FormPanel from '$lib/components/ui/FormPanel.svelte';
	import StepButtons from '$lib/components/ui/StepButtons.svelte';
	import ProgressIndicator from '$lib/components/ui/ProgressIndicator.svelte';
	import CriteriaInput from '$lib/components/ui/CriteriaInput.svelte';
	import ScoutScheduleModal from '$lib/components/modals/ScoutScheduleModal.svelte';
	import { apiClient } from '$lib/api-client';
	import { sidebarNav } from '$lib/stores/sidebar-nav';
	import type { ScoutType } from '$lib/types';
	import * as m from '$lib/paraglide/messages';

	// Step state: domain (initial) → results (after search, shows criteria + schedule)
	let hasResults = false;

	// Step 1 — domain input
	let domain = '';
	let isDiscovering = false;
	let discoverError = '';
	let discoverProgress = 0;
	let discoverProgressMessage = '';
	let discoverProgressTimer: ReturnType<typeof setInterval> | null = null;

	// URL selection
	let discoveredUrls: Array<{ url: string; description: string }> = [];
	let selectedUrls: Set<string> = new Set();

	// Step 2 — criteria
	let criteria = '';

	// Test extraction
	let isTesting = false;
	let testError = '';
	let testProgress = 0;
	let testProgressMessage = '';
	let testProgressTimer: ReturnType<typeof setInterval> | null = null;
	let testSuccess = false;
	let testResult: {
		documents_found: number;
		sample_promises: Array<{ promise_text: string; context: string; source_url: string; source_date: string; due_date?: string; date_confidence: string; criteria_match: boolean }>;
	} | null = null;
	let showTestResults = false;

	// Schedule modal state
	let showScheduleModal = false;

	$: canDiscover = domain.trim().length > 0;
	$: canSchedule = selectedUrls.size > 0 && selectedUrls.size <= 2;

	$: discoverProgressState = discoverError ? 'error' as const : 'loading' as const;
	$: testProgressState = testError ? 'error' as const : testSuccess ? 'success' as const : 'loading' as const;

	function startDiscoverProgress() {
		discoverProgress = 5;
		discoverProgressMessage = m.civic_discovering();
		if (discoverProgressTimer) clearInterval(discoverProgressTimer);
		discoverProgressTimer = setInterval(() => {
			if (discoverProgress < 85) {
				discoverProgress = Math.min(discoverProgress + Math.round(Math.random() * 4 + 1), 85);
			}
		}, 800);
	}

	function stopDiscoverProgress(success: boolean) {
		if (discoverProgressTimer) {
			clearInterval(discoverProgressTimer);
			discoverProgressTimer = null;
		}
		if (success) {
			discoverProgress = 0;
			discoverProgressMessage = '';
		} else {
			discoverProgress = 100;
			discoverProgressMessage = '';
		}
	}

	function startTestProgress() {
		testProgress = 5;
		testProgressMessage = m.civic_testing();
		if (testProgressTimer) clearInterval(testProgressTimer);
		testProgressTimer = setInterval(() => {
			if (testProgress < 85) {
				testProgress = Math.min(testProgress + Math.round(Math.random() * 3 + 1), 85);
			}
		}, 1200);
	}

	function stopTestProgress() {
		if (testProgressTimer) {
			clearInterval(testProgressTimer);
			testProgressTimer = null;
		}
		testProgress = 100;
		testProgressMessage = '';
	}

	async function handleDiscover() {
		if (!canDiscover) return;

		// Reset previous results
		discoverError = '';
		hasResults = false;
		showTestResults = false;
		testSuccess = false;
		testError = '';
		testProgress = 0;
		testResult = null;
		isDiscovering = true;
		startDiscoverProgress();

		try {
			const result = await apiClient.discoverCivic(domain.trim());
			discoveredUrls = (result.candidates || []).map((c) => ({ url: c.url, description: c.description || '' }));
			// Don't pre-select — user picks up to 2 deliberately
			selectedUrls = new Set();
			hasResults = true;
			stopDiscoverProgress(true);
		} catch (err) {
			discoverError = err instanceof Error ? err.message : 'Discovery failed';
			stopDiscoverProgress(false);
		} finally {
			isDiscovering = false;
		}
	}

	async function handleTestAndSchedule() {
		isTesting = true;
		testError = '';
		testSuccess = false;
		testResult = null;
		showTestResults = true;
		startTestProgress();

		try {
			const result = await apiClient.testCivic([...selectedUrls], criteria || undefined);
			if (!result.valid) {
				testError = result.error || m.civic_testFailed();
				stopTestProgress();
				return;
			}
			testResult = {
				documents_found: result.documents_found,
				sample_promises: result.sample_promises,
			};
			testSuccess = true;
			stopTestProgress();
		} catch (err) {
			testError = err instanceof Error ? err.message : m.civic_testFailed();
			stopTestProgress();
		} finally {
			isTesting = false;
		}
	}

	function handleReset() {
		discoverError = '';
		discoverProgress = 0;
		discoverProgressMessage = '';
	}

	function toggleUrl(url: string) {
		const next = new Set(selectedUrls);
		if (next.has(url)) {
			next.delete(url);
		} else if (next.size < 2) {
			next.add(url);
		}
		selectedUrls = next;
	}

	function handleOpenSchedule() {
		showScheduleModal = true;
	}
</script>

<div class="panel-view">
	<div class="two-column-layout">
		<!-- Left Column: Form -->
		<div class="query-column">
			<FormPanel
				badge={m.civic_trackCouncil()}
				badgeVariant="amber"
				title={m.civic_monitorTitle()}
				subtitle={m.civic_monitorDescription()}
			>
				<!-- Domain input — always editable -->
				<div class="field-group">
					<label for="civic-domain" class="field-label">{m.civic_enterDomain()}</label>
					<input
						id="civic-domain"
						type="text"
						bind:value={domain}
						placeholder="https://gemeinde.zermatt.ch/"
						class="form-input"
						disabled={isDiscovering}
					/>
				</div>

				<!-- Steps -->
				<div class="step-spacer">
					{#if discoverError}
						<button on:click={handleReset} class="btn-secondary w-full">
							{m.common_tryAgain()}
						</button>
					{:else}
						<StepButtons
							step1Disabled={!canDiscover || isDiscovering}
							step1Loading={isDiscovering}
							step1Label={m.pulse_startSearch()}
							step1LoadingLabel={m.common_searching()}
							step1Icon={Search}
							step2Enabled={hasResults && canSchedule && !isTesting}
							step2Label={m.civic_testExtraction()}
							step3Enabled={testSuccess}
							step3Label={m.pulse_scheduleScout()}
							on:step1={handleDiscover}
							on:step2={handleTestAndSchedule}
							on:step3={handleOpenSchedule}
						>
							<div slot="between-step2-step3">
								{#if hasResults && canSchedule}
									<div class="field-group criteria-section">
										<label class="field-label">
											{m.scheduleSearch_criteriaLabel()}
											<span class="field-subtitle">{m.civic_criteriaHint()}</span>
										</label>
										<CriteriaInput
											bind:value={criteria}
											placeholder={m.webScout_criteriaPlaceholder()}
											rows={2}
											examples={[
												{ label: 'housing policy', value: 'housing policy' },
												{ label: 'budget', value: 'budget' },
												{ label: 'infrastructure', value: 'infrastructure' },
											]}
										/>
									</div>
								{/if}
							</div>
						</StepButtons>
					{/if}
				</div>
			<div class="form-spacer"></div>
			</FormPanel>
		</div>

		<!-- Right Column: Results / Progress -->
		<div class="results-column">
			{#if isDiscovering || discoverError}
				<ProgressIndicator
					progress={discoverProgress}
					message={discoverProgressMessage || m.civic_discovering()}
					state={discoverProgressState}
					errorTitle={m.civic_noResults()}
					errorMessage={discoverError}
					showButton={false}
					hintText={isDiscovering ? 'This may take up to 30 seconds' : ''}
				/>
			{:else if showTestResults}
				<!-- Test/extraction results (replaces URL list) -->
				<ProgressIndicator
					progress={testProgress}
					message={testProgressMessage || m.civic_testing()}
					state={testProgressState}
					successMessage={m.civic_testSuccess()}
					successDetails={testResult ? `${testResult.documents_found} documents analyzed, ${testResult.sample_promises.length} promises found` : ''}
					errorTitle={m.civic_testFailed()}
					errorMessage={testError}
					showButton={false}
					hintText={isTesting ? 'Parsing documents and extracting promises...' : ''}
				/>

				{#if testSuccess && testResult && testResult.sample_promises.length > 0}
					<div class="promises-preview">
						<p class="preview-label">Extracted promises (preview)</p>
						{#each testResult.sample_promises as promise}
							<div class="promise-item">
								<p class="promise-text">{promise.promise_text}</p>
								{#if promise.due_date}
									<span class="promise-due">Due: {promise.due_date}</span>
								{/if}
								<span class="promise-source">{promise.source_url}</span>
							</div>
						{/each}
					</div>
				{/if}
			{:else if hasResults && discoveredUrls.length > 0}
				<!-- URL selection (step 1 results) -->
				<div class="results-summary">
					<div class="results-summary-header">
						<Landmark size={20} class="results-icon" />
						<div>
							<p class="results-count">{m.civic_bestCandidates()}</p>
							<p class="results-domain">{domain}</p>
						</div>
					</div>
					<p class="results-hint">{m.civic_selectHint()}</p>
					<p class="results-selection-count">{selectedUrls.size}/2 selected</p>
				</div>

				<div class="url-list">
					{#each discoveredUrls as candidate}
						<!-- svelte-ignore a11y-click-events-have-key-events -->
						<!-- svelte-ignore a11y-no-static-element-interactions -->
						<div
							class="url-item"
							class:url-item--selected={selectedUrls.has(candidate.url)}
							class:url-item--disabled={!selectedUrls.has(candidate.url) && selectedUrls.size >= 2}
							on:click={() => toggleUrl(candidate.url)}
						>
							<span class="url-check">
								{#if selectedUrls.has(candidate.url)}
									<CheckSquare size={16} class="url-check-icon--checked" />
								{:else}
									<Square size={16} class="url-check-icon" />
								{/if}
							</span>
							<span class="url-content">
								<span class="url-text" title={candidate.url}>{candidate.url}</span>
								{#if candidate.description}
									<span class="url-description">{candidate.description}</span>
								{/if}
							</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

<!-- Schedule Modal -->
<ScoutScheduleModal
	bind:open={showScheduleModal}
	scoutType={'civic' as ScoutType}
	root_domain={domain.trim()}
	tracked_urls={[...selectedUrls]}
	criteria={criteria}
	initialPromises={testResult?.sample_promises ?? []}
	on:close={() => showScheduleModal = false}
	on:success={() => {
		showScheduleModal = false;
		sidebarNav.setView('scouts');
	}}
/>

<style>
	.form-spacer { height: 6rem; }

	.field-group { margin-bottom: 0.75rem; }

	.field-label {
		display: block;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-ink);
		margin-bottom: 0.375rem;
	}

	.field-subtitle {
		font-weight: 400;
		color: var(--color-text-secondary);
		margin-left: 0.375rem;
		font-size: 0.8125rem;
	}

	/* Extra spacing below domain input to give the form more height */
	.step-spacer {
		margin-top: 1.5rem;
	}

	.criteria-section {
		margin-top: 1rem;
	}

	/* URL list (results column) */
	.url-list {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		max-height: 400px;
		overflow-y: auto;
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 0;
		padding: 0.375rem;
		margin-top: 1rem;
		background: var(--color-surface-alt);
	}

	.url-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.625rem;
		border-radius: 0;
		cursor: pointer;
		transition: background 0.15s ease;
		user-select: none;
	}

	.url-item:hover {
		background: var(--color-bg);
	}

	.url-item--selected {
		background: #fffbeb;
	}

	.url-item--selected:hover {
		background: var(--color-secondary-soft);
	}

	.url-check {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		color: var(--color-ink-subtle);
	}

	.url-item--selected .url-check {
		color: #9F6016;
	}

	.url-check :global(.url-check-icon--checked) {
		color: #9F6016;
	}

	.url-check :global(.url-check-icon) {
		color: var(--color-ink-subtle);
	}

	.url-text {
		font-size: 0.8125rem;
		color: var(--color-ink);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}

	.url-item--selected .url-text {
		color: var(--color-secondary);
	}

	/* Results summary panel */
	.results-summary {
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: var(--radius-xl, 0.75rem);
		padding: 1.25rem 1.5rem;
		box-shadow: var(--shadow-md, 0 1px 4px rgba(0,0,0,0.06));
	}

	.results-summary-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.results-summary-header :global(.results-icon) {
		color: #9F6016;
		flex-shrink: 0;
	}

	.results-count {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
	}

	.results-domain {
		font-size: 0.8125rem;
		color: var(--color-ink-muted);
		margin: 0;
	}

	.results-hint {
		font-size: 0.8125rem;
		color: var(--color-ink-muted);
		margin: 0;
		line-height: 1.5;
	}

	.results-selection-count {
		font-size: 0.75rem;
		font-weight: 600;
		color: #9F6016;
		margin: 0.5rem 0 0;
	}

	.url-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		min-width: 0;
		flex: 1;
	}

	.url-description {
		font-size: 0.6875rem;
		color: var(--color-ink-subtle);
		line-height: 1.3;
	}

	.url-item--disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	/* Test results */
	.test-results-section {
		margin-top: 1.5rem;
	}

	/* Promises preview */
	.promises-preview {
		margin-top: 1rem;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 0;
		padding: 1rem;
	}

	.preview-label {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 0.75rem;
	}

	.promise-item {
		padding: 0.75rem;
		background: #fffbeb;
		border: 1px solid var(--color-secondary-soft);
		border-radius: 0;
		margin-bottom: 0.5rem;
	}

	.promise-item:last-child {
		margin-bottom: 0;
	}

	.promise-text {
		font-size: 0.875rem;
		color: var(--color-ink);
		margin: 0 0 0.375rem;
		line-height: 1.5;
	}

	.promise-due {
		display: inline-block;
		font-size: 0.75rem;
		font-weight: 500;
		color: #9F6016;
		background: var(--color-secondary-soft);
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		margin-right: 0.5rem;
	}

	.promise-source {
		font-size: 0.75rem;
		color: var(--color-ink-muted);
	}
</style>
