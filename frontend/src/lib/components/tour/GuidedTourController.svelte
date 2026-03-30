<script lang="ts">
	import { onMount } from 'svelte';
	import * as m from '$lib/paraglide/messages';
	import GuidedTooltip from './GuidedTooltip.svelte';
	import GuidedTourOverlay from './GuidedTourOverlay.svelte';
	import { onboardingTour } from '$lib/stores/onboarding-tour';
	import { sidebarNav, type SidebarView } from '$lib/stores/sidebar-nav';

	export let onComplete: () => void;

	interface TourStep {
		selector: string;
		title: () => string;
		text: () => string;
		view?: SidebarView;
	}

	const TOUR_STEPS: TourStep[] = [
		{
			selector: '[data-tour="new-scout"]',
			title: () => m.tour_step1_title(),
			text: () => m.tour_step1_text(),
			view: 'page-scout'
		},
		{
			selector: '[data-tour="your-scouts"]',
			title: () => m.tour_step2_title(),
			text: () => m.tour_step2_text(),
			view: 'scouts'
		},
		{
			selector: '[data-tour="feed"]',
			title: () => m.tour_step3_title(),
			text: () => m.tour_step3_text(),
			view: 'feed'
		},
		{
			selector: '[data-tour="ai-select"]',
			title: () => m.tour_step4_title(),
			text: () => m.tour_step4_text(),
			view: 'feed'
		},
		{
			selector: '[data-tour="scrape"]',
			title: () => m.tour_step5_title(),
			text: () => m.tour_step5_text(),
			view: 'extract'
		}
	];

	let mounted = false;

	$: active = $onboardingTour.active;
	$: currentStep = $onboardingTour.currentStep;
	$: currentTourStep = TOUR_STEPS[currentStep];
	$: isLastStep = currentStep === TOUR_STEPS.length - 1;
	// Resolve messages here — same reactive scope as currentStep, no indirection
	$: title = currentTourStep?.title() ?? '';
	$: text = currentTourStep?.text() ?? '';

	// Reactive navigation: fires on activation, replay, AND step transitions
	$: if (active && mounted && currentTourStep?.view) {
		sidebarNav.setView(currentTourStep.view);
	}

	$: if (active && mounted && $sidebarNav.collapsed) {
		sidebarNav.toggleCollapsed();
	}

	function handleNext() {
		onboardingTour.nextStep();
	}

	function handleDone() {
		onComplete();
	}

	onMount(() => {
		mounted = true;
	});
</script>

{#if active && mounted && currentTourStep}
	<GuidedTourOverlay targetSelector={currentTourStep.selector} />
	{#key currentStep}
		<GuidedTooltip
			targetSelector={currentTourStep.selector}
			{title}
			{text}
			currentStep={currentStep + 1}
			totalSteps={TOUR_STEPS.length}
			{isLastStep}
			on:next={handleNext}
			on:done={handleDone}
		/>
	{/key}
{/if}
