<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { X, Globe, ScanSearch, Tag, MapPin, Bell, CheckCircle, Mail, Filter, Ban, Star, Users, Landmark } from 'lucide-svelte';
	import { fade } from 'svelte/transition';
	import type { GeocodedLocation, RegularityType, ScoutType, ScrapeChannel, ActiveJobsResponse } from '$lib/types';
	import { apiClient } from '$lib/api-client';
	import { authStore } from '$lib/stores/auth';
	import { triggerScoutsRefresh } from '$lib/stores/scouts-refresh';
	import { triggerFeedRefresh } from '$lib/stores/feed-refresh';
	import TimePicker from '$lib/components/ui/TimePicker.svelte';
	import LocationAutocomplete from '$lib/components/ui/LocationAutocomplete.svelte';
	import TopicChips from '$lib/components/ui/TopicChips.svelte';
	import { getScoutCost, validateScheduleCredits } from '$lib/utils/scouts';
	import * as m from '$lib/paraglide/messages';

	export let open = false;
	export let scoutType: ScoutType = 'pulse';

	// Beat Scout context (pulse)
	export let location: GeocodedLocation | null = null;
	export let topic: string = '';
	export let criteria: string = '';

	// Page Scout context (web)
	export let url: string = '';
	export let webCriteria: string = '';
	export let provider: string | undefined = undefined;
	export let scoutName: string = '';
	export let contentHash: string | undefined = undefined;

	// Social Scout context (social)
	export let profile_handle: string = '';
	export let platform: string = 'instagram';
	export let monitor_mode: string = 'summarize';
	export let trackRemovals: boolean = false;
	export let baselinePosts: Record<string, unknown>[] = [];

	// Civic Scout context (civic)
	export let root_domain: string = '';
	export let tracked_urls: string[] = [];
	export let initialPromises: Array<{ promise_text: string; context: string; source_url: string; source_date: string; due_date?: string; date_confidence: string; criteria_match: boolean }> = [];

	// Flat cost from getScoutCost (pulse: 7). Matches the server-of-record in
	// scout-beat-execute/index.ts:153, which ignores sourceMode/location. The
	// prod UI used to override to 10 for pulse+niche+location, but that was
	// cosmetic — actual decrement was always 7. We keep one source of truth.
	$: perRunCost = getScoutCost(scoutType, scoutType === 'social' ? platform : undefined);
	let upgradeRequiredCredits = 0;

	const dispatch = createEventDispatcher<{
		close: void;
		success: { name: string; scoutType: ScoutType };
	}>();

	// Form state
	let regularity: RegularityType = scoutType === 'civic' ? 'monthly' : scoutType === 'social' ? 'weekly' : scoutType === 'pulse' ? 'daily' : 'weekly';
	let dayNumber = 1;
	let hour = 8;
	let minute = 0;
	let period: 'AM' | 'PM' = 'AM';

	let isSubmitting = false;
	let errorMessage = '';
	let scheduleSuccess = false;
	export let sourceMode: 'reliable' | 'niche' = 'niche';
	export let excludedDomains: string[] = [];
	export let prioritySources: string[] = [];

	// Web scout: location/topic added at schedule time
	let selectedLocation: GeocodedLocation | null = null;
	let topicInput = '';
	let existingTopics: string[] = [];

	// Timezone label
	let userTimezoneLabel =
		typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'Local time';

	$: userTimezoneLabel =
		$authStore.user?.timezone ||
		(typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : userTimezoneLabel);

	// Load existing topics for web scout scope dropdown
	onMount(async () => {
		try {
			const response: ActiveJobsResponse = await apiClient.getActiveJobs();
			const allScouts = response.scrapers || [];
			existingTopics = [...new Set(allScouts.filter(s => s.topic).map(s => s.topic!))].sort();
		} catch (_e) {
			// Non-critical
		}
	});

	// Scout type display info
	$: scoutTypeInfo = {
		'pulse': {
			title: m.scoutTypeInfo_newsPulse_title(),
			description: m.scoutTypeInfo_newsPulse_description(),
			color: 'purple',
			icon: Bell,
			notifyRule: m.scoutTypeInfo_newsPulse_notifyRule()
		},
		'web': {
			title: m.scoutTypeInfo_web_title(),
			description: m.scoutTypeInfo_web_description(),
			color: 'blue',
			icon: ScanSearch,
			notifyRule: m.scoutTypeInfo_web_notifyRule()
		},
		'social': {
			title: m.scoutTypeInfo_social_title(),
			description: m.scoutTypeInfo_social_description(),
			color: 'pink',
			icon: Users,
			notifyRule: m.scoutTypeInfo_social_notifyRule()
		},
		'civic': {
			title: m.scoutTypeInfo_civic_title(),
			description: m.scoutTypeInfo_civic_description(),
			color: 'green',
			icon: Landmark,
			notifyRule: m.scoutTypeInfo_civic_notifyRule()
		}
	};

	$: info = scoutTypeInfo[scoutType];
	$: monthlyCost = regularity === 'daily' ? perRunCost * 30 : regularity === 'weekly' ? perRunCost * 4 : perRunCost;

	$: daysOfWeek = [
		{ value: 1, label: m.schedule_monday() },
		{ value: 2, label: m.schedule_tuesday() },
		{ value: 3, label: m.schedule_wednesday() },
		{ value: 4, label: m.schedule_thursday() },
		{ value: 5, label: m.schedule_friday() },
		{ value: 6, label: m.schedule_saturday() },
		{ value: 7, label: m.schedule_sunday() }
	];

	function getScheduleSummary(): string {
		let h = hour;
		if (period === 'AM' && h === 12) h = 0;
		else if (period === 'PM' && h !== 12) h += 12;
		const time24h = `${h.toString().padStart(2, '0')}:${(minute ?? 0).toString().padStart(2, '0')}`;

		if (regularity === 'daily') {
			return `Daily at ${time24h}`;
		} else if (regularity === 'weekly') {
			const dayName = daysOfWeek.find(d => d.value === dayNumber)?.label || 'Monday';
			return `Every ${dayName} at ${time24h}`;
		} else {
			return `Monthly on day ${dayNumber} at ${time24h}`;
		}
	}

	async function handleSubmit(event: Event) {
		event.preventDefault();

		if (!scoutName.trim()) {
			errorMessage = m.scheduleSearch_nameRequired();
			return;
		}

		// Validation for web scouts: need URL
		if (scoutType === 'web' && !url.trim()) {
			errorMessage = m.scheduleSearch_urlRequired();
			return;
		}

		// Validation for pulse: need location or criteria
		if (scoutType === 'pulse' && !location && !criteria) {
			errorMessage = m.scheduleSearch_locationOrTopicRequired();
			return;
		}

		// Validation for social: need profile handle
		if (scoutType === 'social' && !profile_handle.trim()) {
			errorMessage = 'Profile handle is required';
			return;
		}

		isSubmitting = true;
		errorMessage = '';

		// Validate credits client-side. The authoritative charge happens inside
		// each executor Edge Function via decrement_credits; this is UX only.
		const creditCheck = validateScheduleCredits({
			scoutType,
			regularity: regularity as 'daily' | 'weekly' | 'monthly',
			platform: scoutType === 'social' ? platform : undefined,
			currentCredits: 999999
		});
		if (!creditCheck.valid) {
			isSubmitting = false;
			upgradeRequiredCredits = creditCheck.monthlyCost;
			showUpgradeModal = true;
			return;
		}

		// Compute time
		let computedHour = hour;
		if (period === 'AM' && computedHour === 12) computedHour = 0;
		else if (period === 'PM' && computedHour !== 12) computedHour += 12;
		const computedTime = `${computedHour.toString().padStart(2, '0')}:${(minute ?? 0).toString().padStart(2, '0')}`;

		// Schedule the scout and dispatch success only after API completes
		let schedulePromise: Promise<unknown>;
		if (scoutType === 'web') {
			schedulePromise = apiClient.scheduleMonitoring({
				name: scoutName.trim(),
				url,
				criteria: webCriteria,
				channel: 'website' as ScrapeChannel,
				regularity,
				day_number: regularity === 'daily' ? 1 : dayNumber,
				time: computedTime,
				monitoring: 'EMAIL',
				location: selectedLocation || undefined,
				topic: topicInput.trim() || undefined,
				content_hash: contentHash,
				provider
			});
		} else if (scoutType === 'social') {
			schedulePromise = apiClient.scheduleLocalScout({
				name: scoutName.trim(),
				scout_type: 'social',
				regularity,
				day_number: dayNumber,
				time: computedTime,
				monitoring: 'EMAIL',
				criteria: criteria || undefined,
				platform,
				profile_handle: profile_handle.trim(),
				monitor_mode,
				track_removals: trackRemovals,
				baseline_posts: baselinePosts.length ? baselinePosts : undefined,
				topic: topicInput.trim() || undefined
			});
		} else if (scoutType === 'civic') {
			schedulePromise = apiClient.scheduleLocalScout({
				name: scoutName.trim(),
				scout_type: 'civic',
				regularity,
				day_number: dayNumber,
				time: computedTime,
				monitoring: 'EMAIL',
				location: selectedLocation || undefined,
				root_domain: root_domain || undefined,
				tracked_urls: tracked_urls.length ? tracked_urls : undefined,
				topic: topicInput.trim() || undefined,
				criteria: criteria || undefined,
				initial_promises: initialPromises.length ? initialPromises : undefined
			});
		} else {
			schedulePromise = apiClient.scheduleLocalScout({
				name: scoutName.trim(),
				scout_type: scoutType,
				regularity,
				day_number: dayNumber,
				time: computedTime,
				monitoring: 'EMAIL',
				location: location || undefined,
				topic: topicInput.trim() || undefined,
				criteria: criteria || undefined,
				source_mode: sourceMode,
				excluded_domains: excludedDomains.length ? excludedDomains : undefined,
				priority_sources: prioritySources.length ? prioritySources : undefined
			});
		}

		schedulePromise.then(() => {
			scheduleSuccess = true;
			isSubmitting = false;
			dispatch('success', { name: scoutName, scoutType });
			authStore.refreshUser();
			setTimeout(() => {
				triggerScoutsRefresh();
				triggerFeedRefresh();
			}, 1500);
		}).catch((error) => {
			isSubmitting = false;
			errorMessage = error instanceof Error ? error.message : 'Failed to schedule scout';
		});
	}

	function handleClose() {
		dispatch('close');
		if (scoutType !== 'web') scoutName = '';
		errorMessage = '';
		scheduleSuccess = false;
		selectedLocation = null;
		topicInput = '';
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			handleClose();
		}
	}

	function handleLocationSelect(event: CustomEvent<GeocodedLocation>) {
		selectedLocation = event.detail;
	}

	function handleLocationClear() {
		selectedLocation = null;
	}
</script>

{#if open}
	<!-- Modal Backdrop -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
		on:click={handleBackdropClick}
		on:keydown={(event) => event.key === 'Escape' && handleClose()}
		role="button"
		tabindex="0"
		aria-label="Close modal backdrop"
	>
		<!-- Modal Card -->
		<div
			class="relative w-full max-w-lg mx-4 bg-white rounded-xl shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto"
			on:click|stopPropagation
			on:keydown|stopPropagation
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<!-- Header -->
			<div class="flex items-center justify-between p-5 border-b border-gray-200">
				<div class="flex items-center gap-3">
					<div
						class="flex h-10 w-10 items-center justify-center rounded-lg {info.color === 'purple' ? 'bg-purple-100' : ''} {info.color === 'blue' ? 'bg-blue-100' : ''} {info.color === 'pink' ? 'bg-pink-100' : ''} {info.color === 'green' ? 'bg-green-100' : ''}"
					>
						<svelte:component
							this={info.icon}
							class="h-5 w-5 {info.color === 'purple' ? 'text-purple-600' : ''} {info.color === 'blue' ? 'text-blue-600' : ''} {info.color === 'pink' ? 'text-pink-600' : ''} {info.color === 'green' ? 'text-green-600' : ''}"
						/>
					</div>
					<div>
						<h2 class="text-lg font-semibold text-gray-900">{scoutType === 'web' ? m.scheduleSearch_titlePageScout() : scoutType === 'social' ? m.scheduleSearch_titleSocialScout() : scoutType === 'civic' ? m.scheduleSearch_titleCivicScout() : m.scheduleSearch_title()}</h2>
						<p class="text-xs text-gray-600">{info.description}</p>
					</div>
				</div>
				<button
					on:click={handleClose}
					class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
					aria-label="Close modal"
				>
					<X class="h-5 w-5" />
				</button>
			</div>

			{#if scheduleSuccess}
				<!-- Success Confirmation -->
				<div class="p-6" transition:fade={{ duration: 200 }}>
					<div class="text-center py-6">
						<div class="mx-auto w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
							<CheckCircle class="h-8 w-8 text-green-600" />
						</div>
						<h3 class="text-xl font-semibold text-gray-900 mb-2">{m.scheduleSearch_scoutScheduled()}</h3>
						<p class="text-gray-600 mb-1">{scoutName}</p>
						<p class="text-sm text-gray-500">{getScheduleSummary()}</p>
					</div>

					<button
						on:click={handleClose}
						class="btn-primary w-full mt-4"
					>
						{m.common_done()}
					</button>
				</div>
			{:else}
				<!-- Form -->
				<form on:submit={handleSubmit} class="p-6 space-y-5">
					<!-- Context Display -->
					<div class="rounded-lg bg-gray-100 p-4 space-y-2">
						{#if scoutType === 'web' && url}
							<div class="flex items-center gap-2 text-sm">
								<Globe class="h-4 w-4 text-gray-500" />
								<span class="font-medium text-gray-700">URL:</span>
								<span class="text-gray-600 truncate">{url}</span>
							</div>
						{/if}

						{#if scoutType === 'web' && webCriteria}
							<div class="flex items-start gap-2 text-sm">
								<Filter class="h-4 w-4 text-gray-500 mt-0.5" />
								<span class="font-medium text-gray-700">{m.scheduleSearch_criteriaLabel()}</span>
								<span class="text-gray-600 italic">{webCriteria}</span>
							</div>
						{/if}

						{#if location && scoutType === 'pulse'}
							<div class="flex items-center gap-2 text-sm">
								<MapPin class="h-4 w-4 text-gray-500" />
								<span class="font-medium text-gray-700">{m.scheduleSearch_locationLabel()}</span>
								<span class="text-gray-600">{location.displayName}</span>
							</div>
						{/if}

						{#if criteria && scoutType === 'pulse'}
							<div class="flex items-center gap-2 text-sm">
								<Tag class="h-4 w-4 text-gray-500" />
								<span class="font-medium text-gray-700">{m.scheduleSearch_searchLabel()}</span>
								<span class="text-gray-600">{criteria}</span>
							</div>
						{/if}

						{#if excludedDomains.length > 0 && scoutType === 'pulse'}
							<div class="flex items-start gap-2 text-sm mt-2 pt-2 border-t border-gray-200">
								<Ban class="h-4 w-4 text-gray-500 mt-0.5" />
								<span class="font-medium text-gray-700">{m.pulse_excludedDomains()}:</span>
								<span class="text-gray-600">{excludedDomains.join(', ')}</span>
							</div>
						{/if}

						{#if prioritySources.length > 0 && scoutType === 'pulse'}
							<div class="flex items-start gap-2 text-sm mt-2 pt-2 border-t border-gray-200">
								<Star class="h-4 w-4 text-gray-500 mt-0.5" />
								<span class="font-medium text-gray-700">{m.pulse_prioritySources()}:</span>
								<span class="text-gray-600">{prioritySources.join(', ')}</span>
							</div>
						{/if}

						{#if scoutType === 'social' && profile_handle}
							<div class="flex items-center gap-2 text-sm">
								<Users class="h-4 w-4 text-gray-500" />
								<span class="font-medium text-gray-700">{m.socialScout_handleLabel()}:</span>
								<span class="text-gray-600">@{profile_handle} ({platform})</span>
							</div>
						{/if}

						{#if scoutType === 'civic' && root_domain}
							<div class="flex items-center gap-2 text-sm">
								<Globe class="h-4 w-4 text-gray-500" />
								<span class="font-medium text-gray-700">{m.civic_monitorTitle()}:</span>
								<span class="text-gray-600">{root_domain}</span>
							</div>
						{/if}
						{#if scoutType === 'civic' && tracked_urls.length > 0}
							<div class="flex items-start gap-2 text-sm">
								<ScanSearch class="h-4 w-4 text-gray-500 mt-0.5" />
								<span class="font-medium text-gray-700">{m.civic_selectUrls()}:</span>
								<span class="text-gray-600">{tracked_urls.length} URLs</span>
							</div>
						{/if}
					</div>

					<!-- Email disclaimer for web scouts (near context) -->
					{#if scoutType === 'web'}
						<div class="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
							<Mail size={14} />
							<span>{webCriteria ? m.schedule_emailDisclaimer_webCriteria() : m.schedule_emailDisclaimer_webAny()}</span>
						</div>
					{/if}

					<!-- Scope (web + civic) -->
					{#if scoutType === 'web' || scoutType === 'civic'}
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">{m.filter_locationLabel()}</label>
							<LocationAutocomplete
								selectedLocation={selectedLocation}
								on:select={handleLocationSelect}
								on:clear={handleLocationClear}
							/>
						</div>
					{/if}

					<!-- Category (all scout types) -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">{m.schedule_categoryLabel()}</label>
						<TopicChips
							bind:topic={topicInput}
							{existingTopics}
							placeholder={m.schedule_categoryPlaceholder()}
						/>
					</div>

					<!-- Scout Name (hidden for web scouts — already set in PageScoutView) -->
					{#if scoutType !== 'web'}
						<div>
							<label for="scout-name" class="block text-sm font-medium text-gray-700 mb-1.5">
								{m.scout_name()} <span class="text-red-500">*</span>
							</label>
							<input
								id="scout-name"
								type="text"
								bind:value={scoutName}
								maxlength="30"
								placeholder={m.scheduleSearch_scoutNamePlaceholder()}
								required
								class="form-input w-full text-sm"
							/>
							<p class="mt-1 text-xs text-gray-500 flex justify-between">
								<span>{m.scout_nameHint()}</span>
								<span class={scoutName.length > 25 ? 'text-amber-600' : ''}>{scoutName.length}/30</span>
							</p>
						</div>
					{/if}

					<!-- Frequency Selector -->
					<div>
						<div class="flex items-center justify-between mb-1.5">
							<label for="regularity" class="text-sm font-medium text-gray-700">
								{m.scheduleSearch_monitoringFrequency()}
							</label>
							{#if import.meta.env.PUBLIC_DEPLOYMENT_TARGET !== 'supabase'}
							<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-medium border border-blue-200">
								{monthlyCost === 1 ? m.scout_monthlyCost({ count: monthlyCost }) : m.scout_monthlyCostPlural({ count: monthlyCost })}
							</span>
						{/if}
						</div>
						<select
							id="regularity"
							bind:value={regularity}
							class="form-input w-full text-sm"
							disabled={scoutType === 'civic'}
							style={scoutType === 'civic' ? 'opacity: 0.5; cursor: not-allowed;' : ''}
						>
							{#if scoutType !== 'social' && scoutType !== 'civic'}
								<option value="daily">{m.schedule_daily()}</option>
							{/if}
							{#if scoutType !== 'civic'}
								<option value="weekly">{m.schedule_weekly()}</option>
							{/if}
							<option value="monthly">{m.schedule_monthly()}</option>
						</select>
					</div>

					<!-- Day Selection (Conditional) -->
					{#if regularity === 'weekly'}
						<div>
							<label for="day-of-week" class="block text-sm font-medium text-gray-700 mb-1.5">
								{m.schedule_dayOfWeek()}
							</label>
							<select
								id="day-of-week"
								bind:value={dayNumber}
								class="form-input w-full text-sm"
							>
								{#each daysOfWeek as day}
									<option value={day.value}>{day.label}</option>
								{/each}
							</select>
						</div>
					{:else if regularity === 'monthly'}
						<div>
							<label for="day-of-month" class="block text-sm font-medium text-gray-700 mb-1.5">
								{m.schedule_dayOfMonth()}
							</label>
							<input
								id="day-of-month"
								type="number"
								bind:value={dayNumber}
								min="1"
								max="31"
								class="form-input w-full text-sm"
							/>
							<p class="mt-1 text-xs text-gray-500">{m.schedule_dayOfMonthHint()}</p>
						</div>
					{/if}

					<!-- Time Picker -->
					<TimePicker
						bind:hour
						bind:minute
						bind:period
						timezoneLabel={userTimezoneLabel}
					/>

					<!-- Error Message -->
					{#if errorMessage}
						<div class="rounded-lg bg-red-50 p-3 text-sm text-red-700">
							{errorMessage}
						</div>
					{/if}

					<!-- Email disclaimer (pulse/social — web shown above context) -->
					{#if scoutType === 'pulse'}
						<div class="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
							<Mail size={14} />
							<span>{m.schedule_emailDisclaimer_pulse()}</span>
						</div>
					{/if}
					{#if scoutType === 'social'}
						<div class="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
							<Mail size={14} />
							<span>{m.schedule_emailDisclaimer_social()}</span>
						</div>
					{/if}

					<!-- Action Button -->
					<div class="pt-1">
						<button
							type="submit"
							disabled={isSubmitting}
							class="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{#if isSubmitting}
								<span class="flex items-center justify-center gap-2">
									<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
									{m.common_scheduling()}
								</span>
							{:else}
								{m.scout_scheduleScout()}
							{/if}
						</button>
					</div>
				</form>
			{/if}
		</div>
	</div>
{/if}


<style>
</style>
