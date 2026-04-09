<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { Settings, CheckCircle, ExternalLink } from 'lucide-svelte';
	import { fade } from 'svelte/transition';
	import { authStore } from '$lib/stores/auth';
	import { SUPPORTED_LANGUAGES, getLanguageLabel } from '$lib/i18n/constants';
	import { setLocaleFromUser } from '$lib/i18n/locale';
	import { formatTz, getTimezoneOptions, normalizeTimezone } from '$lib/utils/timezones';
	import * as m from '$lib/paraglide/messages';

	export let open = false;

	const dispatch = createEventDispatcher<{ close: void }>();

	let selectedLanguage = '';
	let selectedTimezone = '';
	let cmsApiUrl = '';
	let cmsTokenInput = '';
	let showTokenInput = false;
	let hasCmsToken = false;
	let saving = false;
	let saveSuccess = false;
	let errorMessage: string | null = null;
	let initialized = false;

	// Reset initialization when modal closes
	$: if (!open) {
		initialized = false;
	}

	// Initialize only once when modal first opens
	$: if (open && $authStore.user && !initialized) {
		selectedLanguage = $authStore.user.preferred_language || 'en';
		selectedTimezone = $authStore.user.timezone || normalizeTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
		cmsApiUrl = $authStore.user.cms_api_url || '';
		hasCmsToken = $authStore.user.has_cms_token || false;
		cmsTokenInput = '';
		showTokenInput = false;
		errorMessage = null;
		saveSuccess = false;
		initialized = true;
	}

	$: timezones = getTimezoneOptions(selectedTimezone);

	async function handleSave() {
		saving = true;
		errorMessage = null;

		try {
			const params: { preferred_language?: string; timezone?: string; cms_api_url?: string; cms_api_token?: string } = {};

			if (selectedLanguage !== ($authStore.user?.preferred_language || 'en')) {
				params.preferred_language = selectedLanguage;
			}
			if (selectedTimezone !== ($authStore.user?.timezone || '')) {
				params.timezone = selectedTimezone;
			}
			if (cmsApiUrl !== ($authStore.user?.cms_api_url || '')) {
				params.cms_api_url = cmsApiUrl;
			}
			if (cmsTokenInput) {
				params.cms_api_token = cmsTokenInput;
			}

			if (Object.keys(params).length === 0) {
				dispatch('close');
				return;
			}

			await authStore.updatePreferences(params);

			// Update UI locale if language changed
			if (params.preferred_language) {
				setLocaleFromUser(params.preferred_language);
			}

			saveSuccess = true;
		} catch (e: unknown) {
			errorMessage = e instanceof Error ? e.message : m.preferences_failedToSave();
		} finally {
			saving = false;
		}
	}

	function handleCancel() {
		dispatch('close');
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			handleCancel();
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-gray-900/60 backdrop-blur-sm flex items-center justify-center z-50 px-4"
		on:click={handleBackdropClick}
		on:keydown={(e) => e.key === 'Escape' && handleCancel()}
		role="button"
		tabindex="0"
	>
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<form
			class="w-full max-w-lg bg-white rounded-2xl shadow-2xl p-6 space-y-5"
			on:submit|preventDefault={handleSave}
			on:keydown={(e) => e.key === 'Escape' && handleCancel()}
		>
			{#if saveSuccess}
				<div class="flex flex-col items-center py-6 space-y-4" transition:fade={{ duration: 200 }}>
					<div class="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
						<CheckCircle size={32} class="text-green-600" />
					</div>
					<div class="text-center space-y-1">
						<h3 class="text-lg font-semibold text-gray-900">{m.preferences_updated()}</h3>
						<p class="text-sm text-gray-500">
							{m.preferences_language()}: {getLanguageLabel(selectedLanguage)}
						</p>
					</div>
					<button
						type="button"
						on:click={handleCancel}
						class="px-6 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
					>
						{m.common_done()}
					</button>
				</div>
			{:else}
				<!-- Header -->
				<div class="flex items-center gap-3">
					<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-100 to-purple-50 flex items-center justify-center">
						<Settings size={20} class="text-[#7c6fc7]" />
					</div>
					<div>
						<h2 class="text-lg font-semibold text-gray-900">{m.preferences_title()}</h2>
						<p class="text-sm text-gray-500">{m.preferences_subtitle()}</p>
					</div>
				</div>

				<!-- Language -->
				<div>
					<label for="pref-language" class="block text-sm font-medium text-gray-700 mb-1">
						{m.preferences_language()}
					</label>
					<select
						id="pref-language"
						bind:value={selectedLanguage}
						class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf]"
					>
						{#each SUPPORTED_LANGUAGES as lang}
							<option value={lang.code}>{lang.label}</option>
						{/each}
					</select>
					<p class="text-xs text-gray-400 mt-1">{m.preferences_languageHint()}</p>
				</div>

				<!-- Timezone -->
				<div>
					<label for="pref-timezone" class="block text-sm font-medium text-gray-700 mb-1">
						{m.preferences_timezone()}
					</label>
					<select
						id="pref-timezone"
						bind:value={selectedTimezone}
						class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf]"
					>
						{#each timezones as tz}
							<option value={tz}>{formatTz(tz)}</option>
						{/each}
					</select>
					<p class="text-xs text-gray-400 mt-1">{m.preferences_timezoneHint()}</p>
				</div>

				<!-- CMS Export -->
				<div class="border-t border-gray-200 pt-4">
					<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{m.preferences_cmsExport()}</p>
					<div class="space-y-3">
						<div>
							<label for="pref-cms-url" class="block text-sm font-medium text-gray-700 mb-1">
								{m.preferences_cmsApiEndpoint()}
							</label>
							<input
								id="pref-cms-url"
								type="url"
								bind:value={cmsApiUrl}
								placeholder={m.preferences_cmsApiEndpointPlaceholder()}
								class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf]"
							/>
						</div>
						<div>
							<label for="pref-cms-token" class="block text-sm font-medium text-gray-700 mb-1">
								{m.preferences_cmsBearerTokenOptional()}
							</label>
							{#if hasCmsToken && !showTokenInput}
								<div class="flex items-center gap-2">
									<span class="text-xs text-green-600 font-medium">{m.preferences_cmsTokenSaved()}</span>
									<button
										type="button"
										on:click={() => { showTokenInput = true; }}
										class="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
									>{m.preferences_cmsTokenChange()}</button>
									<button
										type="button"
										on:click={() => { cmsTokenInput = ''; hasCmsToken = false; showTokenInput = false; }}
										class="text-xs text-red-500 hover:text-red-700 font-medium"
									>{m.preferences_cmsTokenClear()}</button>
								</div>
							{:else}
								<input
									id="pref-cms-token"
									type="password"
									bind:value={cmsTokenInput}
									placeholder="Bearer token"
									class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:ring-2 focus:ring-[#968bdf] focus:border-[#968bdf]"
								/>
								<p class="text-xs text-gray-400 mt-1">{m.preferences_cmsBearerTokenHint()}</p>
							{/if}
						</div>
					</div>
				</div>

				<!-- Account -->
			{#if import.meta.env.PUBLIC_DEPLOYMENT_TARGET !== 'supabase'}
			<div class="border-t border-gray-200 pt-4">
				<p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{m.preferences_account()}</p>
				<div class="space-y-3">
					<div class="flex items-center gap-2">
						<span class="text-sm text-gray-700">{m.preferences_currentTier()}</span>
						<span class="tier-badge tier-{$authStore.user?.tier ?? 'free'}">
							{($authStore.user?.tier ?? 'free').charAt(0).toUpperCase() + ($authStore.user?.tier ?? 'free').slice(1)}
						</span>
					</div>
					<a
						href={$authStore.user?.username
							? `#
							: '#'}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
					>
						{m.preferences_manageMuckrock()}
						<ExternalLink size={14} />
					</a>
					<p class="text-xs text-gray-400">{m.preferences_manageMuckrockHint()}</p>
				</div>
			</div>
			{/if}

				<!-- Error -->
				{#if errorMessage}
					<p class="text-sm text-red-600">{errorMessage}</p>
				{/if}

				<!-- Actions -->
				<div class="flex justify-end gap-3 pt-2">
					<button
						type="button"
						on:click={handleCancel}
						class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
					>
						{m.common_cancel()}
					</button>
					<button
						type="submit"
						disabled={saving}
						class="btn-primary"
					>
						{saving ? m.common_saving() : m.common_save()}
					</button>
				</div>
			{/if}
		</form>
	</div>
{/if}

<style>
	.tier-badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		font-size: 0.75rem;
		font-weight: 600;
		line-height: 1.25rem;
	}
	.tier-free {
		background-color: #f3f4f6;
		color: #6b7280;
	}
	.tier-pro {
		background-color: #fef3c7;
		color: #b45309;
	}
	.tier-team {
		background-color: #dbeafe;
		color: #1e40af;
	}
</style>
