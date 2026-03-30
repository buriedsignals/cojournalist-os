<script lang="ts">
import { createEventDispatcher, onDestroy } from 'svelte';
import { apiClient } from '$lib/api-client';
import { authStore } from '$lib/stores/auth';
import { parseCSVBlob, type ParsedCSVData } from '$lib/utils/scraper';
import type { ScrapeChannel } from '$lib/types';
import { CheckCircle, Sparkles } from 'lucide-svelte';
import UpgradeModal from '$lib/components/modals/UpgradeModal.svelte';
import * as m from '$lib/paraglide/messages';

type ExtractResultPayload = {
	summary?: string;
	csvDownloaded?: boolean;
	csvFileName?: string;
};

	const dispatch = createEventDispatcher<{
		extractStart: void;
		extractComplete: { result: ExtractResultPayload };
		extractError: { error: string };
		extractProgress: { progress: number; message: string };
	}>();

	let scrapeChannel: ScrapeChannel = 'website';
	let url = '';
	let instagramHandle = '';
	let xHandle = '';
	let facebookHandle = '';
	let instagramCommentsUrl = '';
let dataTarget = '';
let isExtracting = false;
let extractError = '';
	const socialDefaultTarget = 'tweets';
	const instagramDefaultTarget = 'posts';
	const facebookDefaultTarget = 'posts';
	const instagramCommentsDefaultTarget = 'comments';
	let lastDownloadUrl: string | null = null;
	let isCompleted = false;

	// Progress state
	let progress = 0;
	let progressMessage = '';
	let canCancel = false;
	let pollInterval: NodeJS.Timeout | null = null;

	// CSV preview state
	export let csvPreviewData: ParsedCSVData | null = null;
	export let csvBlob: Blob | null = null;
	export let csvFileName: string = 'data.csv';

	// Upgrade modal state
	let showUpgradeModal = false;
	let upgradeModalCredits = { current: 0, required: 0 };

	$: channelOptions = [
		{ label: m.dataExtract_website(), value: 'website' as ScrapeChannel },
		{ label: m.dataExtract_x(), value: 'social' as ScrapeChannel },
		{ label: m.dataExtract_instagram(), value: 'instagram' as ScrapeChannel },
		{ label: m.dataExtract_facebook(), value: 'facebook' as ScrapeChannel },
		{ label: m.dataExtract_instagramComments(), value: 'instagram_comments' as ScrapeChannel }
	];

$: scrapeCost = ({ website: 1, social: 2, instagram: 2, facebook: 15, instagram_comments: 15 } as Record<string, number>)[scrapeChannel] ?? 1;
$: urlPlaceholder =
	scrapeChannel === 'instagram'
		? 'https://instagram.com/username'
		: scrapeChannel === 'social'
			? 'https://x.com/username'
			: scrapeChannel === 'facebook'
				? 'https://facebook.com/profilename'
				: scrapeChannel === 'instagram_comments'
					? 'https://instagram.com/p/ABC123/'
					: 'https://example.com';

	function triggerDownload(blob: Blob, filename: string) {
		if (lastDownloadUrl) {
			URL.revokeObjectURL(lastDownloadUrl);
			lastDownloadUrl = null;
		}
		const url = URL.createObjectURL(blob);
		lastDownloadUrl = url;
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = filename;
		document.body.appendChild(anchor);
		anchor.click();
		document.body.removeChild(anchor);
		setTimeout(() => {
			if (lastDownloadUrl) {
				URL.revokeObjectURL(lastDownloadUrl);
				lastDownloadUrl = null;
			}
		}, 2000);
	}

	onDestroy(() => {
		if (lastDownloadUrl) {
			URL.revokeObjectURL(lastDownloadUrl);
			lastDownloadUrl = null;
		}
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	});

	async function handleExtract() {
		extractError = '';
		csvPreviewData = null;
		csvBlob = null;
		progress = 0;
		isCompleted = false;

		const targetPayload = scrapeChannel === 'social'
			? socialDefaultTarget
			: scrapeChannel === 'instagram'
				? instagramDefaultTarget
				: scrapeChannel === 'facebook'
					? facebookDefaultTarget
					: scrapeChannel === 'instagram_comments'
						? instagramCommentsDefaultTarget
						: dataTarget.trim();

		// Construct URL from handle or direct input
		const targetUrl = scrapeChannel === 'instagram'
			? `https://www.instagram.com/${instagramHandle.replace('@', '').trim()}/`
			: scrapeChannel === 'social'
				? `https://x.com/${xHandle.replace('@', '').trim()}`
				: scrapeChannel === 'facebook'
					? `https://www.facebook.com/${facebookHandle.replace('@', '').trim()}/`
					: scrapeChannel === 'instagram_comments'
						? instagramCommentsUrl.trim()
						: url;

	// Flip UI state immediately for instant feedback
	isExtracting = true;
	canCancel = true;
	progressMessage = 'Validating...';
	dispatch('extractStart');

		// Validate credits first
		try {
			await apiClient.validateExtractionCredits({
				url: targetUrl,
				target: targetPayload,
				channel: scrapeChannel
			});
		} catch (err: unknown) {
			const creditErr = err as Record<string, unknown>;
			if (creditErr?.type === 'insufficient_credits') {
				upgradeModalCredits = {
					current: Number(creditErr.current_credits) || 0,
					required: Number(creditErr.required_credits) || 0
				};
				showUpgradeModal = true;
				isExtracting = false;
				canCancel = false;
				return;
			}
			extractError = err instanceof Error ? err.message : 'Failed to validate credits';
			dispatch('extractError', { error: extractError });
			isExtracting = false;
			canCancel = false;
			return;
		}

	progressMessage = 'Starting extraction...';

	try {
		// Start the extraction job
		const { job_id } = await apiClient.startExtraction({
			url: targetUrl,
			target: targetPayload,
			channel: scrapeChannel,
			criteria: undefined
		});

			progress = 10;
			progressMessage = 'Extraction job started...';
			dispatch('extractProgress', { progress, message: progressMessage });

			// Poll for status
			pollInterval = setInterval(async () => {
				try {
					const statusResponse = await apiClient.getExtractionStatus(job_id);
					
					if (statusResponse.status === 'completed') {
						if (pollInterval) clearInterval(pollInterval);
						pollInterval = null;

						const result = statusResponse.result; // { csv_content, filename, raw }

						// Defensive: treat empty data as error even if backend says "completed"
						const rawData = result?.raw;
						const isWrapperEmpty = typeof rawData === 'object' && rawData !== null
							&& !Array.isArray(rawData)
							&& Object.keys(rawData).length > 0
							&& Object.values(rawData).every(
								(v) => (Array.isArray(v) && v.length === 0)
									|| (typeof v === 'object' && v !== null && Object.keys(v).length === 0)
							);
						const hasData = rawData !== null && rawData !== undefined
							&& !(Array.isArray(rawData) && rawData.length === 0)
							&& !(typeof rawData === 'object' && Object.keys(rawData).length === 0)
							&& !isWrapperEmpty;

						const csvIsPlaceholder = result?.csv_content?.includes('No data extracted');

						if (!hasData || !result?.csv_content || csvIsPlaceholder) {
							const errorMsg = m.dataExtract_noDataExtracted();
							extractError = errorMsg;
							dispatch('extractProgress', { progress, message: 'Extraction failed' });
							dispatch('extractError', { error: errorMsg });
							isExtracting = false;
							canCancel = false;
							return;
						}

						// Convert CSV string to Blob
						csvBlob = new Blob([result.csv_content], { type: 'text/csv' });
						csvFileName = result.filename;

						// Parse CSV for preview
						try {
							csvPreviewData = await parseCSVBlob(csvBlob, 10);
						} catch {
							// CSV preview parsing failed, continue without preview
						}
						
						// Update credits
						try {
							const authStatus = await apiClient.getAuthStatus();
							if (authStatus.authenticated && authStatus.user?.credits !== undefined) {
								authStore.setCredits(authStatus.user.credits);
							}
						} catch {
							// Credit refresh failed, continue without updating
						}

						const processedResult = {
							summary: '',
							csvDownloaded: false,
							csvFileName: csvFileName
						};

						dispatch('extractComplete', { result: processedResult });
						isExtracting = false;
						canCancel = false;
						progress = 100;
						progressMessage = 'Extraction complete!';
						dispatch('extractProgress', { progress, message: progressMessage });
						isCompleted = true;
						
					} else if (statusResponse.status === 'failed') {
						if (pollInterval) clearInterval(pollInterval);
						pollInterval = null;

						const errorMsg = statusResponse.error || 'Extraction failed';
						extractError = errorMsg;
						dispatch('extractProgress', { progress, message: 'Extraction failed' });
						dispatch('extractError', { error: errorMsg });
						isExtracting = false;
						canCancel = false;
						
					} else {
						// Still running
						// Simulate progress for better UX since we don't get exact progress from all backends
						if (progress < 90) {
							progress += 5;
						}
						progressMessage = 'Extracting data...';
						dispatch('extractProgress', { progress, message: progressMessage });
					}
				} catch {
					// Polling error, will retry on next interval
				}
			}, 3000); // Poll every 3 seconds

		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to start extraction';
			extractError = message;

			dispatch('extractProgress', { progress, message: 'Extraction failed' });
			dispatch('extractError', { error: message });
			isExtracting = false;
			canCancel = false;
		}
	}

	export function handleCancelExtraction() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
	isExtracting = false;
	canCancel = false;
	progress = 0;
	progressMessage = 'Extraction cancelled';
	isCompleted = false;
}
	}

	export function getProgress() {
		return { progress, message: progressMessage, canCancel: canCancel };
	}

	export function handleDownloadCSV() {
		if (csvBlob) {
			triggerDownload(csvBlob, csvFileName);
		}
	}
</script>

<div class="extract-form">
	<div class="form-group">
		<label for="extract-channel" class="field-label">{m.dataExtract_whatScraping()}</label>
		<select
			id="extract-channel"
			class="form-select"
			bind:value={scrapeChannel}
			disabled={isExtracting}
		>
			{#each channelOptions as option}
				<option value={option.value}>{option.label}</option>
			{/each}
		</select>
		<div class="cost-badge">
			{m.dataExtract_costPerExtract({ cost: scrapeCost })}
		</div>
	</div>

	{#if scrapeChannel === 'instagram'}
		<div class="form-group">
			<label for="extract-handle" class="field-label">{m.dataExtract_instagramHandle()}</label>
			<div class="input-prefix-wrapper">
				<span class="input-prefix">instagram.com/</span>
				<input
					id="extract-handle"
					type="text"
					class="form-input prefixed-input"
					bind:value={instagramHandle}
					placeholder="username"
					required
					disabled={isExtracting}
				/>
			</div>
		</div>
	{:else if scrapeChannel === 'social'}
		<div class="form-group">
			<label for="extract-x-handle" class="field-label">{m.dataExtract_xHandle()}</label>
			<div class="input-prefix-wrapper">
				<span class="input-prefix">x.com/</span>
				<input
					id="extract-x-handle"
					type="text"
					class="form-input prefixed-input"
					bind:value={xHandle}
					placeholder="username"
					required
					disabled={isExtracting}
				/>
			</div>
		</div>
	{:else if scrapeChannel === 'facebook'}
		<div class="form-group">
			<label for="extract-fb-handle" class="field-label">{m.dataExtract_facebookHandle()}</label>
			<div class="input-prefix-wrapper">
				<span class="input-prefix">facebook.com/</span>
				<input
					id="extract-fb-handle"
					type="text"
					class="form-input prefixed-input"
					bind:value={facebookHandle}
					placeholder="profilename"
					required
					disabled={isExtracting}
				/>
			</div>
		</div>
	{:else if scrapeChannel === 'instagram_comments'}
		<div class="form-group">
			<label for="extract-ig-comments-url" class="field-label">{m.dataExtract_postUrl()}</label>
			<input
				id="extract-ig-comments-url"
				type="url"
				class="form-input"
				bind:value={instagramCommentsUrl}
				placeholder="https://instagram.com/p/ABC123/"
				required
				disabled={isExtracting}
			/>
		</div>
	{:else}
		<div class="form-group">
			<label for="extract-url" class="field-label">{m.dataExtract_targetUrl()}</label>
			<input
				id="extract-url"
				type="url"
				class="form-input"
				bind:value={url}
				placeholder={urlPlaceholder}
				required
				disabled={isExtracting}
			/>
		</div>
	{/if}

	{#if scrapeChannel === 'website'}
		<div class="form-group">
			<label for="extract-target" class="field-label">{m.dataExtract_dataTarget()}</label>
			<textarea
				id="extract-target"
				class="form-textarea compact-textarea"
				bind:value={dataTarget}
				placeholder={m.dataExtract_dataTargetPlaceholder()}
				required
				disabled={isExtracting}
			></textarea>
		</div>
	{/if}

	<button
		class={
			isCompleted
				? 'submit-btn submit-btn-success'
				: 'btn-primary w-full submit-btn'
		}
		type="button"
		on:click={handleExtract}
		disabled={isExtracting ||
			(scrapeChannel === 'instagram' ? !instagramHandle.trim() :
			 scrapeChannel === 'social' ? !xHandle.trim() :
			 scrapeChannel === 'facebook' ? !facebookHandle.trim() :
			 scrapeChannel === 'instagram_comments' ? !instagramCommentsUrl.trim() :
			 !url.trim()) ||
			(scrapeChannel === 'website' && !dataTarget.trim())}
	>
		{#if isExtracting}
			<span>{m.dataExtract_extracting()}</span>
		{:else if isCompleted}
			<CheckCircle class="w-4 h-4" /> {m.dataExtract_complete()}
		{:else}
			<Sparkles size={16} />
			<span>{m.dataExtract_extractData()}</span>
		{/if}
	</button>
</div>

<style>
	.extract-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.field-label {
		display: block;
		font-size: 0.8125rem;
		font-weight: 500;
		color: #374151;
		margin: 0;
	}

	.cost-badge {
		display: inline-flex;
		align-items: center;
		width: fit-content;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: #eff6ff;
		border: 1px solid #bfdbfe;
		font-size: 0.75rem;
		font-weight: 500;
		color: #1d4ed8;
	}

	.input-prefix-wrapper {
		display: flex;
		align-items: center;
		border: 1px solid #d1d5db;
		border-radius: 0.5rem;
		overflow: hidden;
		background: white;
	}

	.input-prefix-wrapper:focus-within {
		border-color: #6366f1;
		box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
	}

	.input-prefix {
		padding: 0.625rem 0 0.625rem 0.75rem;
		background: #f9fafb;
		color: #6b7280;
		font-size: 0.875rem;
		white-space: nowrap;
		border-right: 1px solid #e5e7eb;
	}

	.prefixed-input {
		flex: 1;
		border: none;
		border-radius: 0;
		padding-left: 0.5rem;
	}

	.prefixed-input:focus {
		outline: none;
		box-shadow: none;
	}


	.compact-textarea {
		min-height: 80px;
		max-height: 80px;
		resize: none;
	}

	.submit-btn {
		padding: 0.75rem 1rem;
		font-size: 0.9375rem;
	}

	.submit-btn-success {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		width: 100%;
		background: #16a34a;
		color: white;
		font-weight: 600;
		padding: 0.75rem 1rem;
		border-radius: 0.75rem;
		border: none;
		cursor: pointer;
		transition: background 0.2s ease;
	}

	.submit-btn-success:hover {
		background: #15803d;
	}
</style>

<UpgradeModal
	open={showUpgradeModal}
	currentCredits={upgradeModalCredits.current}
	requiredCredits={upgradeModalCredits.required}
	operationType="extraction"
	on:close={() => (showUpgradeModal = false)}
/>
