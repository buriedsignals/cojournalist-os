<script lang="ts">
	import DataExtract from '$lib/components/sidebars/DataExtract.svelte';
	import FormPanel from '$lib/components/ui/FormPanel.svelte';
	import ProgressIndicator from '$lib/components/ui/ProgressIndicator.svelte';
	import { isExtracting } from '$lib/stores/extraction-state';
	import * as m from '$lib/paraglide/messages';

let isExtractingData = false;
let showExtractionSection = false;
type ExtractDisplay = {
	summary?: string;
	csvDownloaded?: boolean;
	csvFileName?: string;
};

let dataExtractResult: ExtractDisplay | null = null;
let dataExtractError: string | null = null;
let dataExtractProgress = 0;
let dataExtractMessage = '';
let canCancelExtraction = false;
let dataExtractComponentRef: DataExtract;
let csvPreviewData: any = null;
let csvBlob: Blob | null = null;
let csvFileName: string = 'data.csv';

$: extractionState = (dataExtractError
	? 'error'
	: dataExtractResult
		? 'success'
		: 'loading') as 'loading' | 'success' | 'error';

export function handleDataExtractStart() {
	isExtractingData = true;
	isExtracting.set(true);
	showExtractionSection = true;
	dataExtractResult = null;
	dataExtractError = null;
	dataExtractProgress = 0;
	dataExtractMessage = m.scrape_startingExtraction();
	canCancelExtraction = false;
}

export function handleDataExtractProgress(event: CustomEvent<{ progress: number; message: string }>) {
	dataExtractProgress = event.detail.progress;
	dataExtractMessage = event.detail.message;
	canCancelExtraction = true;
}

export function handleDataExtractComplete(event: CustomEvent<{ result: ExtractDisplay }>) {
	isExtractingData = false;
	isExtracting.set(false);
	dataExtractResult = event.detail.result;
	dataExtractMessage = '';
	canCancelExtraction = false;
}

export function handleDataExtractError(event: CustomEvent<{ error: string }>) {
	isExtractingData = false;
	isExtracting.set(false);
	showExtractionSection = true;
	dataExtractError = event.detail.error;
	dataExtractMessage = '';
	canCancelExtraction = false;
}

function handleCancelExtraction() {
	if (dataExtractComponentRef) {
		dataExtractComponentRef.handleCancelExtraction();
	}
	isExtractingData = false;
	isExtracting.set(false);
	showExtractionSection = false;
}
</script>

<div class="panel-view">
	<div class="two-column-layout">
			<!-- Left Column: Extraction Form -->
			<div class="query-column">
				<FormPanel
					badge={m.scrape_badge()}
					title={m.scrape_formTitle()}
					subtitle={m.scrape_formSubtitle()}
				>
					<DataExtract
						bind:this={dataExtractComponentRef}
						bind:csvPreviewData
						bind:csvBlob
						bind:csvFileName
						on:extractStart={handleDataExtractStart}
						on:extractProgress={handleDataExtractProgress}
						on:extractComplete={handleDataExtractComplete}
						on:extractError={handleDataExtractError}
					/>
				</FormPanel>
			</div>

			<!-- Right Column: Results -->
			<div class="results-column">
				{#if showExtractionSection}
					<section class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
						<div class="flex items-center justify-between mb-4">
							<h3 class="text-lg font-semibold text-gray-900">{m.scrape_dataExtraction()}</h3>
							{#if isExtractingData}
								<span class="text-xs font-semibold text-indigo-600 uppercase tracking-wide">{m.scrape_statusRunning()}</span>
							{:else if dataExtractError}
								<span class="text-xs font-semibold text-red-600 uppercase tracking-wide">{m.scrape_statusError()}</span>
							{:else if dataExtractResult}
								<span class="text-xs font-semibold text-green-600 uppercase tracking-wide">{m.scrape_statusComplete()}</span>
							{/if}
						</div>

						<ProgressIndicator
							progress={dataExtractProgress}
							message={dataExtractMessage || m.scrape_startingExtraction()}
							state={extractionState}
							successMessage={m.scrape_extractionComplete()}
							errorTitle={m.scrape_extractionFailed()}
							errorMessage={dataExtractError || ''}
							hintText={isExtractingData ? m.scrape_complexPageHint() : ''}
						/>

						{#if isExtractingData && canCancelExtraction}
							<div class="flex justify-end mt-2">
								<button
									type="button"
									class="extraction-progress__cancel"
									on:click={handleCancelExtraction}
								>
									{m.scrape_cancelExtraction()}
								</button>
							</div>
						{/if}

						<!-- CSV Preview -->
						{#if csvPreviewData}
							<div class="mt-6 space-y-3">
								<div class="flex items-center justify-between">
									<h3 class="text-sm font-semibold text-gray-700">
										{m.scrape_dataPreview()}
										{#if csvPreviewData.totalRows > csvPreviewData.rows.length}
											<span class="text-xs font-normal text-gray-500">
												{m.scrape_showingRows({ shown: csvPreviewData.rows.length, total: csvPreviewData.totalRows })}
											</span>
										{/if}
									</h3>
									<button
										type="button"
										class="btn-secondary text-sm px-4 py-2"
										on:click={() => dataExtractComponentRef?.handleDownloadCSV()}
									>
										{m.scrape_downloadCSV()}
									</button>
								</div>

								<div class="table-container">
									<table class="preview-table">
										<thead class="bg-gray-100">
											<tr>
												{#each csvPreviewData.headers as header}
													<th scope="col" class="table-header">
														{header}
													</th>
												{/each}
											</tr>
										</thead>
										<tbody class="bg-white divide-y divide-gray-200">
											{#each csvPreviewData.rows as row}
												<tr>
													{#each row as cell}
														<td class="table-cell">
															<span class="cell-content">{cell}</span>
														</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>
						{/if}
					</section>
				{/if}
			</div>
		</div>
</div>

<style>
	.results-column {
		overflow: hidden;
	}

	/* Override global styles */
	:global(.panel-view .bg-white) {
		background: var(--color-bg-secondary);
	}

	:global(.panel-view .rounded-2xl) {
		border-radius: var(--radius-xl);
	}

	:global(.panel-view .shadow-sm) {
		box-shadow: var(--shadow-md);
	}

	:global(.panel-view .border-gray-100) {
		border-color: var(--color-border);
	}

	/* Table styles */
	.table-container {
		overflow-x: auto;
		border-radius: 0.5rem;
		border: 1px solid #e5e7eb;
		background: #f9fafb;
	}

	.preview-table {
		min-width: 100%;
		border-collapse: collapse;
		opacity: 0.6;
	}

	.table-header {
		padding: 0.5rem 1rem;
		text-align: left;
		font-size: 0.75rem;
		font-weight: 600;
		color: #374151;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		white-space: nowrap;
		min-width: 100px;
	}

	.table-cell {
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		color: #111827;
		max-width: 300px;
		min-width: 80px;
	}

	.cell-content {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
