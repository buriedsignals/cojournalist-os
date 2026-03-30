/**
 * Onboarding Tour Store -- guided tour progress and completion tracking.
 *
 * USED BY: FeedView.svelte, ScoutsPanel.svelte, UnifiedSidebar.svelte,
 *          GuidedTourController.svelte, +layout.svelte
 * DEPENDS ON: (none)
 *
 * State: { active: boolean, currentStep: number }
 * Side effects: reads/writes localStorage key 'cojournalist_onboarding_tour_completed'
 *               (format: "userId:timestamp")
 *
 * Exports: onboardingTour (store), isTourActive (derived),
 *          isTourCompleted(), markTourCompleted() (localStorage helpers)
 */

import { writable, derived } from 'svelte/store';

const TOUR_FLAG_KEY = 'cojournalist_onboarding_tour_completed';

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

/**
 * Check if the tour has been completed for a specific user.
 * Stored format: "userId:timestamp"
 */
export function isTourCompleted(userId: string | null | undefined): boolean {
	if (typeof localStorage === 'undefined' || !userId) {
		return false;
	}

	const stored = localStorage.getItem(TOUR_FLAG_KEY);
	if (!stored) {
		return false;
	}

	const storedUserId = stored.split(':')[0];
	return storedUserId === userId;
}

/**
 * Mark the tour as completed for a specific user
 */
export function markTourCompleted(userId: string | null | undefined): void {
	if (typeof localStorage === 'undefined' || !userId) {
		return;
	}

	localStorage.setItem(TOUR_FLAG_KEY, `${userId}:${Date.now()}`);
}

// ---------------------------------------------------------------------------
// Reactive store for tour state
// ---------------------------------------------------------------------------

interface OnboardingTourState {
	active: boolean;
	currentStep: number;
}

const INITIAL_STATE: OnboardingTourState = { active: false, currentStep: 0 };

function createOnboardingTourStore() {
	const { subscribe, set, update } = writable<OnboardingTourState>(INITIAL_STATE);

	return {
		subscribe,
		start: () => set({ active: true, currentStep: 0 }),
		nextStep: () => update(s => ({ ...s, currentStep: s.currentStep + 1 })),
		complete: () => set(INITIAL_STATE)
	};
}

export const onboardingTour = createOnboardingTourStore();

/** Whether the tour is currently active. */
export const isTourActive = derived(onboardingTour, $t => $t.active);
