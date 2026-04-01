<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import * as m from '$lib/paraglide/messages';
	import { apiRequest } from '$lib/api-client';
	import Spinner from '$lib/components/ui/Spinner.svelte';

	export let open = false;

	const dispatch = createEventDispatcher();

	let selectedType: 'bug' | 'feature' | 'other' = 'bug';
	let title = '';
	let description = '';
	let loading = false;
	let error = '';
	let submitted = false;
	let device = '';
	let browser = '';
	let screenshotFile: File | null = null;
	let screenshotPreview = '';

	function handleScreenshot(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		screenshotFile = file;
		const reader = new FileReader();
		reader.onload = () => { screenshotPreview = reader.result as string; };
		reader.readAsDataURL(file);
	}

	function removeScreenshot() {
		screenshotFile = null;
		screenshotPreview = '';
	}

	function close() {
		dispatch('close');
		// reset state after close animation
		setTimeout(() => {
			selectedType = 'bug';
			title = '';
			description = '';
			error = '';
			submitted = false;
			device = '';
			browser = '';
			screenshotFile = null;
			screenshotPreview = '';
		}, 300);
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) close();
	}

	async function handleSubmit() {
		if (!title.trim()) return;
		loading = true;
		error = '';
		try {
			const payload: Record<string, unknown> = {
				title: title.trim(),
				type: selectedType,
				description: description.trim(),
			};
			if (selectedType === 'bug') {
				if (device) payload.device = device;
				if (browser) payload.browser = browser;
				if (screenshotFile && screenshotPreview) {
					payload.screenshot_base64 = screenshotPreview.split(',')[1];
					payload.screenshot_filename = screenshotFile.name;
					payload.screenshot_content_type = screenshotFile.type || 'image/png';
				}
			}
			await apiRequest<{ url: string }>('POST', '/feedback', payload);
			submitted = true;
			setTimeout(() => { submitted = false; close(); }, 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : m.feedback_error();
		} finally {
			loading = false;
		}
	}


</script>

{#if open}
	<div
		class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
		on:click={handleBackdropClick}
		on:keydown={(e) => e.key === 'Escape' && close()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<div class="modal-container">
			<!-- Header -->
			<div style="display:flex;align-items:flex-start;justify-content:space-between;padding:1.5rem 1.5rem 0">
				<div>
					<h2 class="modal-title">{m.feedback_title()}</h2>
					<p class="modal-subtitle">{m.feedback_subtitle()}</p>
				</div>
				<button on:click={close} class="close-button" aria-label="Close modal">
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<line x1="18" y1="6" x2="6" y2="18"/>
						<line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
				</button>
			</div>

			{#if submitted}
				<!-- Success state -->
				<div style="padding:2rem;text-align:center">
					<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin:0 auto 1rem" aria-hidden="true">
						<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
						<polyline points="22 4 12 14.01 9 11.01"/>
					</svg>
					<h3 style="font-family:'Crimson Pro',Georgia,serif;font-size:1.5rem;font-weight:600;margin:0;color:var(--color-text-primary)">{m.feedback_success_heading()}</h3>
				</div>
			{:else}
				<!-- Body -->
				<div style="padding:1.5rem">
					<!-- Type pills -->
					<div style="display:flex;gap:0.5rem;margin-bottom:1.25rem">
						{#each [
							{ key: 'bug', label: m.feedback_type_bug(), activeClass: 'pill-bug' },
							{ key: 'feature', label: m.feedback_type_feature(), activeClass: 'pill-feature' },
							{ key: 'other', label: m.feedback_type_other(), activeClass: 'pill-other' },
						] as pill}
							<button
								type="button"
								class="type-pill {selectedType === pill.key ? pill.activeClass : ''}"
								on:click={() => selectedType = pill.key as 'bug' | 'feature' | 'other'}
							>{pill.label}</button>
						{/each}
					</div>

					<!-- Title input -->
					<label for="feedback-title" class="block text-sm font-semibold text-gray-700 mb-1">{m.feedback_field_title()}</label>
					<input
						id="feedback-title"
						type="text"
						bind:value={title}
						class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf]"
						placeholder={m.feedback_field_title_placeholder()}
						required
					/>

					<!-- Description textarea -->
					<label for="feedback-description" class="block text-sm font-semibold text-gray-700 mb-1 mt-4">{m.feedback_field_description()}</label>
					<textarea
						id="feedback-description"
						bind:value={description}
						rows="4"
						class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf] resize-none"
						placeholder={m.feedback_field_description_placeholder()}
					></textarea>

					{#if selectedType === 'bug'}
						<!-- Device -->
						<label for="feedback-device" class="block text-sm font-semibold text-gray-700 mb-1 mt-4">{m.feedback_device_label()}</label>
						<select
							id="feedback-device"
							bind:value={device}
							class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf] bg-white"
						>
							<option value="">Select device…</option>
							<option value="Mac">Mac</option>
							<option value="Windows">Windows</option>
							<option value="Linux">Linux</option>
							<option value="iPhone">iPhone</option>
							<option value="iPad">iPad</option>
							<option value="Android">Android</option>
							<option value="Other">Other</option>
						</select>

						<!-- Browser -->
						<label for="feedback-browser" class="block text-sm font-semibold text-gray-700 mb-1 mt-4">{m.feedback_browser_label()}</label>
						<select
							id="feedback-browser"
							bind:value={browser}
							class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf] bg-white"
						>
							<option value="">Select browser…</option>
							<option value="Chrome">Chrome</option>
							<option value="Safari">Safari</option>
							<option value="Firefox">Firefox</option>
							<option value="Edge">Edge</option>
							<option value="Brave">Brave</option>
							<option value="Other">Other</option>
						</select>

						<!-- Screenshot -->
						<label class="block text-sm font-semibold text-gray-700 mb-1 mt-4">{m.feedback_screenshot_label()}</label>
						{#if screenshotPreview}
							<div style="position:relative;display:inline-block;margin-bottom:0.5rem">
								<img src={screenshotPreview} alt="Screenshot preview" style="max-width:100%;max-height:120px;border-radius:0.5rem;border:1px solid #e5e7eb;display:block"/>
								<button type="button" on:click={removeScreenshot} style="position:absolute;top:-8px;right:-8px;width:20px;height:20px;border-radius:50%;background:#ef4444;border:none;color:white;font-size:14px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center">×</button>
							</div>
						{:else}
							<label class="screenshot-upload-area">
								<input type="file" accept="image/*" on:change={handleScreenshot} style="display:none" />
								<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin:0 auto 0.5rem;display:block;color:#9ca3af" aria-hidden="true">
									<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
								</svg>
								<span style="font-size:0.8125rem;color:#9ca3af">Click to attach screenshot</span>
							</label>
						{/if}
					{/if}

					{#if error}
						<p class="mt-2 text-sm text-red-600">{error}</p>
					{/if}
				</div>

				<!-- Footer -->
				<div style="padding:1.5rem;background:#f5f5f4;border-top:1px solid rgba(0,0,0,0.06);border-radius:0 0 1.5rem 1.5rem;display:flex;gap:0.75rem">
					<button class="btn-cancel" on:click={close}>{m.common_cancel()}</button>
					<button
						class="btn-primary flex-1"
						on:click={handleSubmit}
						disabled={loading}
					>
						{#if loading}<Spinner size="sm" variant="white" />{/if}
						{loading ? m.feedback_submitting() : m.feedback_submit()}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.modal-container {
		background: white;
		border-radius: 1.5rem;
		box-shadow: 0 20px 48px rgba(0, 0, 0, 0.12);
		max-width: 28rem;
		width: 100%;
		overflow: hidden;
		animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
	}

	@keyframes modalIn {
		from {
			opacity: 0;
			transform: scale(0.95) translateY(10px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}

	.modal-title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 0.25rem;
	}

	.modal-subtitle {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		margin-bottom: 0;
		line-height: 1.5;
	}

	.close-button {
		color: var(--color-text-tertiary);
		transition: color 0.2s ease;
		padding: 0.5rem;
		border-radius: 0.5rem;
	}

	.close-button:hover {
		color: var(--color-text-primary);
		background: var(--color-bg-tertiary);
	}

	.type-pill {
		flex: 1;
		padding: 0.5rem;
		font-size: 0.875rem;
		font-weight: 500;
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		background: white;
		cursor: pointer;
		transition: all 0.15s ease;
		color: #9ca3af;
		font-family: inherit;
	}

	.type-pill:hover {
		background: #f9fafb;
		color: #6b7280;
	}

	.pill-bug {
		background: #fef2f2 !important;
		border-color: #fecaca !important;
		color: #b91c1c !important;
	}

	.pill-feature {
		background: #f5f3ff !important;
		border-color: #ddd6fe !important;
		color: #968bdf !important;
	}

	.pill-other {
		background: #eff6ff !important;
		border-color: #bfdbfe !important;
		color: #3b82f6 !important;
	}

	.btn-cancel {
		flex: 1;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-secondary);
		background: white;
		border: 1px solid var(--color-border-strong);
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-cancel:hover {
		background: var(--color-bg-primary);
		border-color: var(--color-border-hover);
	}

	.btn-submit {
		flex: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: white;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-submit:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.btn-submit:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.screenshot-upload-area {
		display: block;
		border: 1px dashed #d1d5db;
		border-radius: 0.5rem;
		padding: 1rem;
		text-align: center;
		cursor: pointer;
		transition: border-color 0.15s ease;
	}
	.screenshot-upload-area:hover {
		border-color: #968bdf;
	}
</style>
