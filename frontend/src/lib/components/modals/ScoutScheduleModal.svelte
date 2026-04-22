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
			triggerScoutsRefresh();
			triggerFeedRefresh();
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
			class="modal-card"
			on:click|stopPropagation
			on:keydown|stopPropagation
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<!-- Header -->
			<div class="modal-header">
				<div class="modal-header-left">
					<div class="modal-icon icon-{info.color}">
						<svelte:component this={info.icon} size={20} />
					</div>
					<div>
						<h2 class="modal-title">{scoutType === 'web' ? m.scheduleSearch_titlePageScout() : scoutType === 'social' ? m.scheduleSearch_titleSocialScout() : scoutType === 'civic' ? m.scheduleSearch_titleCivicScout() : m.scheduleSearch_title()}</h2>
						<p class="modal-subtitle">{info.description}</p>
					</div>
				</div>
				<button on:click={handleClose} class="modal-close" aria-label="Close modal">
					<X size={20} />
				</button>
			</div>

			{#if scheduleSuccess}
				<!-- Success Confirmation -->
				<div class="modal-body" transition:fade={{ duration: 200 }}>
					<div class="success-block">
						<div class="success-icon">
							<CheckCircle size={32} />
						</div>
						<h3 class="success-title">{m.scheduleSearch_scoutScheduled()}</h3>
						<p class="success-name">{scoutName}</p>
						<p class="success-summary">{getScheduleSummary()}</p>
					</div>
					<button on:click={handleClose} class="btn-primary modal-action">
						{m.common_done()}
					</button>
				</div>
			{:else}
				<!-- Form -->
				<form on:submit={handleSubmit} class="modal-body">
					<!-- Context Display (mirrors ApiView's .agent-block pattern) -->
					<div class="context-wrap">
						<div class="context-block">
							{#if scoutType === 'web' && url}
								<div class="context-row">
									<Globe size={14} class="context-icon" />
									<span class="context-key">URL:</span>
									<span class="context-value truncate">{url}</span>
								</div>
							{/if}
							{#if scoutType === 'web' && webCriteria}
								<div class="context-row">
									<Filter size={14} class="context-icon" />
									<span class="context-key">{m.scheduleSearch_criteriaLabel()}</span>
									<span class="context-value italic">{webCriteria}</span>
								</div>
							{/if}
							{#if location && scoutType === 'pulse'}
								<div class="context-row">
									<MapPin size={14} class="context-icon" />
									<span class="context-key">{m.scheduleSearch_locationLabel()}</span>
									<span class="context-value">{location.displayName}</span>
								</div>
							{/if}
							{#if criteria && scoutType === 'pulse'}
								<div class="context-row">
									<Tag size={14} class="context-icon" />
									<span class="context-key">{m.scheduleSearch_searchLabel()}</span>
									<span class="context-value">{criteria}</span>
								</div>
							{/if}
							{#if excludedDomains.length > 0 && scoutType === 'pulse'}
								<div class="context-row context-row-divider">
									<Ban size={14} class="context-icon" />
									<span class="context-key">{m.pulse_excludedDomains()}:</span>
									<span class="context-value">{excludedDomains.join(', ')}</span>
								</div>
							{/if}
							{#if prioritySources.length > 0 && scoutType === 'pulse'}
								<div class="context-row context-row-divider">
									<Star size={14} class="context-icon" />
									<span class="context-key">{m.pulse_prioritySources()}:</span>
									<span class="context-value">{prioritySources.join(', ')}</span>
								</div>
							{/if}
							{#if scoutType === 'social' && profile_handle}
								<div class="context-row">
									<Users size={14} class="context-icon" />
									<span class="context-key">{m.socialScout_handleLabel()}:</span>
									<span class="context-value">@{profile_handle} ({platform})</span>
								</div>
							{/if}
							{#if scoutType === 'civic' && root_domain}
								<div class="context-row">
									<Globe size={14} class="context-icon" />
									<span class="context-key">{m.civic_monitorTitle()}:</span>
									<span class="context-value">{root_domain}</span>
								</div>
							{/if}
							{#if scoutType === 'civic' && tracked_urls.length > 0}
								<div class="context-row">
									<ScanSearch size={14} class="context-icon" />
									<span class="context-key">{m.civic_selectUrls()}:</span>
									<span class="context-value">{tracked_urls.length} URLs</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Email disclaimer for web scouts (near context) -->
					{#if scoutType === 'web'}
						<div class="email-disclaimer">
							<Mail size={14} />
							<span>{webCriteria ? m.schedule_emailDisclaimer_webCriteria() : m.schedule_emailDisclaimer_webAny()}</span>
						</div>
					{/if}

					<!-- Scope (web + civic) -->
					{#if scoutType === 'web' || scoutType === 'civic'}
						<div class="form-group">
							<label class="field-label">{m.filter_locationLabel()}</label>
							<LocationAutocomplete
								selectedLocation={selectedLocation}
								on:select={handleLocationSelect}
								on:clear={handleLocationClear}
							/>
						</div>
					{/if}

					<!-- Category (all scout types) -->
					<div class="form-group">
						<label class="field-label">{m.schedule_categoryLabel()}</label>
						<TopicChips
							bind:topic={topicInput}
							{existingTopics}
							placeholder={m.schedule_categoryPlaceholder()}
						/>
					</div>

					<!-- Scout Name (hidden for web scouts — already set in PageScoutView) -->
					{#if scoutType !== 'web'}
						<div class="form-group">
							<label for="scout-name" class="field-label">
								{m.scout_name()} <span class="required-mark">*</span>
							</label>
							<input
								id="scout-name"
								type="text"
								bind:value={scoutName}
								maxlength="30"
								placeholder={m.scheduleSearch_scoutNamePlaceholder()}
								required
								class="form-input"
							/>
							<p class="field-hint">
								<span>{m.scout_nameHint()}</span>
								<span class={scoutName.length > 25 ? 'count-warning' : ''}>{scoutName.length}/30</span>
							</p>
						</div>
					{/if}

					<!-- Frequency Selector -->
					<div class="form-group">
						<div class="field-label-row">
							<label for="regularity" class="field-label">
								{m.scheduleSearch_monitoringFrequency()}
							</label>
							{#if import.meta.env.PUBLIC_DEPLOYMENT_TARGET !== 'supabase'}
								<span class="cost-badge">
									{monthlyCost === 1 ? m.scout_monthlyCost({ count: monthlyCost }) : m.scout_monthlyCostPlural({ count: monthlyCost })}
								</span>
							{/if}
						</div>
						<select
							id="regularity"
							bind:value={regularity}
							class="form-input"
							disabled={scoutType === 'civic'}
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
						<div class="form-group">
							<label for="day-of-week" class="field-label">{m.schedule_dayOfWeek()}</label>
							<select id="day-of-week" bind:value={dayNumber} class="form-input">
								{#each daysOfWeek as day}
									<option value={day.value}>{day.label}</option>
								{/each}
							</select>
						</div>
					{:else if regularity === 'monthly'}
						<div class="form-group">
							<label for="day-of-month" class="field-label">{m.schedule_dayOfMonth()}</label>
							<input
								id="day-of-month"
								type="number"
								bind:value={dayNumber}
								min="1"
								max="31"
								class="form-input"
							/>
							<p class="field-hint">{m.schedule_dayOfMonthHint()}</p>
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
						<div class="error-block">{errorMessage}</div>
					{/if}

					<!-- Email disclaimer (pulse/social — web shown above context) -->
					{#if scoutType === 'pulse'}
						<div class="email-disclaimer">
							<Mail size={14} />
							<span>{m.schedule_emailDisclaimer_pulse()}</span>
						</div>
					{/if}
					{#if scoutType === 'social'}
						<div class="email-disclaimer">
							<Mail size={14} />
							<span>{m.schedule_emailDisclaimer_social()}</span>
						</div>
					{/if}

					<!-- Action Button -->
					<button
						type="submit"
						disabled={isSubmitting}
						class="btn-primary modal-action"
					>
						{#if isSubmitting}
							<span class="btn-spinner-row">
								<svg class="btn-spinner" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
								</svg>
								{m.common_scheduling()}
							</span>
						{:else}
							{m.scout_scheduleScout()}
						{/if}
					</button>
				</form>
			{/if}
		</div>
	</div>
{/if}


<style>
	/* Card — matches ApiView width (640px) and surface tokens */
	.modal-card {
		position: relative;
		width: 100%;
		max-width: 640px;
		margin: 0 1rem;
		background: var(--color-canvas, #fff);
		border-radius: 0.75rem;
		box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
		border: 1px solid var(--color-border);
		max-height: 90vh;
		overflow-y: auto;
	}

	/* Header */
	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.25rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
	}
	.modal-header-left {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.modal-icon {
		display: flex;
		height: 2.5rem;
		width: 2.5rem;
		align-items: center;
		justify-content: center;
		border-radius: 0.5rem;
	}
	.modal-icon.icon-purple,
	.modal-icon.icon-blue {
		background: var(--color-primary-soft);
		color: var(--color-primary);
	}
	.modal-icon.icon-pink {
		background: #fce7f3;
		color: #db2777;
	}
	.modal-icon.icon-green {
		background: #d1fae5;
		color: #059669;
	}
	.modal-title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0;
		line-height: 1.3;
	}
	.modal-subtitle {
		font-size: 0.75rem;
		color: var(--color-ink-muted);
		margin: 0.125rem 0 0;
		line-height: 1.4;
	}
	.modal-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.375rem;
		color: var(--color-ink-subtle);
		background: transparent;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: background-color 0.15s ease, color 0.15s ease;
	}
	.modal-close:hover {
		background: var(--color-surface);
		color: var(--color-ink-muted);
	}

	/* Body — uses ApiView form-group rhythm */
	.modal-body {
		padding: 1.5rem;
	}

	/* Form groups — matches ApiView */
	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		margin-bottom: 1rem;
	}
	.form-group:last-of-type {
		margin-bottom: 0;
	}
	.field-label {
		display: block;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--color-ink);
		margin: 0;
	}
	.field-label-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.field-hint {
		display: flex;
		justify-content: space-between;
		font-size: 0.75rem;
		color: var(--color-ink-subtle);
		margin: 0.25rem 0 0;
	}
	.required-mark {
		color: #dc2626;
	}
	.count-warning {
		color: #d97706;
	}

	/* Context block — mirrors ApiView .agent-block */
	.context-wrap {
		margin-bottom: 1rem;
	}
	.context-block {
		background: var(--color-surface-alt, var(--color-surface));
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.75rem 0.875rem;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}
	.context-row {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.8125rem;
		line-height: 1.5;
	}
	.context-row-divider {
		margin-top: 0.375rem;
		padding-top: 0.5rem;
		border-top: 1px solid var(--color-border);
	}
	.context-icon {
		color: var(--color-ink-subtle);
		flex-shrink: 0;
		margin-top: 0.125rem;
	}
	.context-key {
		font-weight: 500;
		color: var(--color-ink);
	}
	.context-value {
		color: var(--color-ink-muted);
		min-width: 0;
		overflow: hidden;
	}
	.truncate {
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	.italic {
		font-style: italic;
	}

	/* Disclaimer pill */
	.email-disclaimer {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		color: var(--color-primary-deep);
		background: var(--color-secondary-soft);
		border: 1px solid var(--color-primary-soft);
		border-radius: 0.5rem;
		margin-bottom: 1rem;
	}

	.cost-badge {
		display: inline-flex;
		align-items: center;
		padding: 0.125rem 0.5rem;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--color-primary-deep);
		background: var(--color-secondary-soft);
		border: 1px solid var(--color-primary-soft);
		border-radius: 9999px;
	}

	/* Form inputs — consistent sizing */
	.form-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		font-size: 0.8125rem;
		border: 1px solid var(--color-border);
		border-radius: 0.375rem;
		background: var(--color-canvas, #fff);
		color: var(--color-ink);
		outline: none;
		transition: border-color 0.15s ease;
	}
	.form-input:focus {
		border-color: var(--color-primary);
	}
	.form-input:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* Error block */
	.error-block {
		padding: 0.75rem;
		font-size: 0.8125rem;
		color: #b91c1c;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 0.5rem;
		margin-bottom: 1rem;
	}

	/* Submit button */
	.modal-action {
		width: 100%;
		margin-top: 0.25rem;
	}
	.modal-action:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-spinner-row {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}
	.btn-spinner {
		height: 1rem;
		width: 1rem;
		animation: spin 1s linear infinite;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Success block */
	.success-block {
		text-align: center;
		padding: 1.5rem 0;
	}
	.success-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 4rem;
		height: 4rem;
		border-radius: 9999px;
		background: #d1fae5;
		color: #059669;
		margin-bottom: 1rem;
	}
	.success-title {
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 0.5rem;
	}
	.success-name {
		color: var(--color-ink-muted);
		margin: 0 0 0.25rem;
	}
	.success-summary {
		font-size: 0.8125rem;
		color: var(--color-ink-subtle);
		margin: 0;
	}
</style>
