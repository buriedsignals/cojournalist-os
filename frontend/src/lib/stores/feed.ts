/**
 * Feed Store -- article export generation state.
 *
 * USED BY: FeedView.svelte, ExportSlideOver.svelte, SelectionBar.svelte,
 *          ScoutScheduleModal.svelte, ScoutsPanel.svelte,
 *          tests/stores/feed-ai-select.test.ts
 * DEPENDS ON: $lib/api-client (InformationUnit, ExportDraft types),
 *             $lib/utils/local-storage (TTL persistence)
 *
 * Manages state for the feed panel, including custom export prompt
 * with localStorage persistence (7-day TTL), unit selection, export
 * generation, AI auto-select mode, and slide-over visibility.
 *
 * Side effects: reads/writes localStorage key 'feed_export_prompt'.
 */
import { writable } from 'svelte/store';
import type { InformationUnit, ExportDraft } from '$lib/api-client';
import { loadTimedValue, saveTimedValue } from '$lib/utils/local-storage';

const STORAGE_KEY = 'feed_export_prompt';

/**
 * Feed store state.
 */
interface FeedState {
	// Custom prompt (persisted to localStorage)
	customExportPrompt: string | null;

	// Unit selection (session only)
	selectedUnitIds: Set<string>;

	// Slide-over visibility
	showExportSlideOver: boolean;

	// Export generation
	generatedExport: ExportDraft | null;
	isGenerating: boolean;
	generationError: string | null;

	// Frozen copy of units used for current export (for regeneration context)
	unitsUsedForExport: InformationUnit[];

	// AI select mode
	aiSelectMode: boolean;
	aiSelectedUnitIds: string[];
	aiSelectionSummary: string;
	aiSelectLoading: boolean;
}

const initialState: FeedState = {
	customExportPrompt: loadTimedValue(STORAGE_KEY),
	selectedUnitIds: new Set(),
	showExportSlideOver: false,
	generatedExport: null,
	isGenerating: false,
	generationError: null,
	unitsUsedForExport: [],
	aiSelectMode: false,
	aiSelectedUnitIds: [],
	aiSelectionSummary: '',
	aiSelectLoading: false
};

function createFeedStore() {
	const { subscribe, set, update } = writable<FeedState>(initialState);

	return {
		subscribe,

		/**
		 * Set a custom export prompt.
		 * Persists to localStorage with 7-day TTL.
		 */
		setCustomExportPrompt(prompt: string | null) {
			saveTimedValue(STORAGE_KEY, prompt);
			update((state) => ({
				...state,
				customExportPrompt: prompt
			}));
		},

		/**
		 * Reset custom export prompt to default.
		 */
		resetCustomExportPrompt() {
			saveTimedValue(STORAGE_KEY, null);
			update((state) => ({
				...state,
				customExportPrompt: null
			}));
		},

		// --- Unit selection ---

		toggleUnit(unitId: string) {
			update((state) => {
				const next = new Set(state.selectedUnitIds);
				if (next.has(unitId)) {
					next.delete(unitId);
				} else {
					next.add(unitId);
				}
				return { ...state, selectedUnitIds: next };
			});
		},

		selectAll(unitIds: string[]) {
			update((state) => ({
				...state,
				selectedUnitIds: new Set(unitIds)
			}));
		},

		deselectAll() {
			update((state) => ({
				...state,
				selectedUnitIds: new Set()
			}));
		},

		// --- Slide-over ---

		openSlideOver() {
			update((state) => ({ ...state, showExportSlideOver: true }));
		},

		closeSlideOver() {
			update((state) => ({ ...state, showExportSlideOver: false }));
		},

		// --- Export generation ---

		setGenerating(isGenerating: boolean) {
			update((state) => ({ ...state, isGenerating }));
		},

		setGeneratedExport(draft: ExportDraft | null) {
			update((state) => ({ ...state, generatedExport: draft, generationError: null }));
		},

		setGenerationError(error: string | null) {
			update((state) => ({ ...state, generationError: error, isGenerating: false }));
		},

		setUnitsUsedForExport(units: InformationUnit[]) {
			update((state) => ({ ...state, unitsUsedForExport: [...units] }));
		},

		// --- AI select mode ---

		enterAISelectMode() {
			update((state) => ({ ...state, aiSelectMode: true }));
		},

		exitAISelectMode() {
			update((state) => ({
				...state,
				aiSelectMode: false,
				aiSelectedUnitIds: [],
				aiSelectionSummary: '',
				aiSelectLoading: false,
				selectedUnitIds: new Set()
			}));
		},

		setAISelectedUnitIds(ids: string[]) {
			update((state) => ({
				...state,
				aiSelectedUnitIds: ids,
				selectedUnitIds: new Set(ids)
			}));
		},

		setAISelectionSummary(summary: string) {
			update((state) => ({ ...state, aiSelectionSummary: summary }));
		},

		setAISelectLoading(loading: boolean) {
			update((state) => ({ ...state, aiSelectLoading: loading }));
		},

		// --- Testability ---

		/**
		 * Synchronously read the current store state.
		 */
		getState() {
			let state: FeedState;
			const unsub = subscribe((s) => {
				state = s;
			});
			unsub();
			return state!;
		},

		/**
		 * Reset store to initial state (preserves prompt from localStorage).
		 */
		reset() {
			set({
				...initialState,
				customExportPrompt: loadTimedValue(STORAGE_KEY)
			});
		}
	};
}

export const feedStore = createFeedStore();
