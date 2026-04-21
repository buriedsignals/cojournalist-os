/**
 * Pulse Store -- Beat Scout (type pulse) search state.
 *
 * USED BY: BeatScoutView.svelte
 * DEPENDS ON: $lib/api-client (searchPulse), $lib/types (AINewsArticle,
 *             GeocodedLocation, SearchCategory, etc.),
 *             $lib/utils/local-storage (TTL persistence)
 *
 * Manages dual-category search (news + government/analysis), AI summaries,
 * custom filter prompts, excluded domains, and result deduplication.
 *
 * Side effects:
 *   - Calls apiClient.searchPulse() for both categories in parallel
 *   - Reads/writes localStorage keys: pulse_news_filter_prompt,
 *     pulse_gov_filter_prompt, pulse_excluded_domains
 */
import { writable, get } from 'svelte/store';
import type {
	AINewsArticle,
	GeocodedLocation,
	SearchCategory,
	StructuredSummary,
	FilterPrompts
} from '$lib/types';
import { apiClient } from '$lib/api-client';
import { loadTimedValue, saveTimedValue } from '$lib/utils/local-storage';

/**
 * Load custom filter prompts from localStorage.
 */
function loadCustomPrompts(): FilterPrompts {
	return {
		news: loadTimedValue('pulse_news_filter_prompt'),
		government: loadTimedValue('pulse_gov_filter_prompt')
	};
}

/**
 * Save custom filter prompt to localStorage with timestamp.
 */
function saveCustomPrompt(category: SearchCategory, prompt: string | null): void {
	const key = category === 'news' ? 'pulse_news_filter_prompt' : 'pulse_gov_filter_prompt';
	saveTimedValue(key, prompt);
}

/**
 * Pulse store state.
 */
interface PulseState {
	// Loading state
	isLoading: boolean;

	// Results by category
	newsArticles: AINewsArticle[];
	govArticles: AINewsArticle[];
	newsTotalResults: number;
	govTotalResults: number;
	filteredOutCount: number;

	// AI summaries
	structuredSummary: StructuredSummary;

	// Filter prompts (persisted to localStorage)
	customFilterPrompts: FilterPrompts;

	// Excluded domains (persisted to localStorage)
	excludedDomains: string[];
	excludedDomainsText: string;

	// Priority sources (persisted to localStorage)
	prioritySources: string[];
	prioritySourcesText: string;

	// Metadata
	searchQueriesUsed: string[];
	processingTimeMs: number | null;
	taskCompleted: boolean;
}

const initialState: PulseState = {
	isLoading: false,
	newsArticles: [],
	govArticles: [],
	newsTotalResults: 0,
	govTotalResults: 0,
	filteredOutCount: 0,
	structuredSummary: { news_summary: '', gov_summary: '' },
	customFilterPrompts: loadCustomPrompts(),
	excludedDomains: [],
	excludedDomainsText: loadTimedValue('pulse_excluded_domains') || '',
	prioritySources: [],
	prioritySourcesText: loadTimedValue('pulse_priority_sources') || '',
	searchQueriesUsed: [],
	processingTimeMs: null,
	taskCompleted: false
};

function createPulseStore() {
	const { subscribe, set, update } = writable<PulseState>(initialState);

	return {
		subscribe,

		/**
		 * Fetch both news and government categories in parallel.
		 * Uses /pulse/search endpoint for both categories.
		 */
		async fetchBothCategories(location?: GeocodedLocation, sourceMode?: 'reliable' | 'niche', criteria?: string, excludedDomains?: string[], prioritySources?: string[]) {
			// In criteria-only mode (no location), use 'analysis' instead of 'government'
			const isCriteriaOnly = criteria && !location;
			const secondCategory: SearchCategory = isCriteriaOnly ? 'analysis' : 'government';

			// Niche + location (no criteria): skip government — institutional content
			// contradicts niche promise of community/indie sources
			const isNicheLocation = !isCriteriaOnly && sourceMode === 'niche' && !criteria;

			// Set loading states for both
			update((state) => ({
				...state,
				isLoading: true,
				newsArticles: [],
				govArticles: [],
				structuredSummary: { news_summary: '', gov_summary: '' }
			}));

			const state = get({ subscribe });

			// Fetch news (always) + second category (unless niche+location)
			let newsResult: PromiseSettledResult<any>;
			let govResult: PromiseSettledResult<any>;

			if (isNicheLocation) {
				[newsResult] = await Promise.allSettled([
					apiClient.searchPulse({
						location,
						category: 'news',
						custom_filter_prompt: state.customFilterPrompts.news || undefined,
						source_mode: sourceMode,
						criteria,
						excluded_domains: excludedDomains,
						priority_sources: prioritySources
					})
				]);
				govResult = { status: 'fulfilled', value: { status: 'completed', articles: [], summary: '', totalResults: 0, search_queries_used: [], processing_time_ms: 0 } };
			} else {
				[newsResult, govResult] = await Promise.allSettled([
					apiClient.searchPulse({
						location,
						category: 'news',
						custom_filter_prompt: state.customFilterPrompts.news || undefined,
						source_mode: sourceMode,
						criteria,
						excluded_domains: excludedDomains,
						priority_sources: prioritySources
					}),
					apiClient.searchPulse({
						location,
						category: secondCategory,
						custom_filter_prompt: state.customFilterPrompts.government || undefined,
						source_mode: sourceMode,
						criteria,
						excluded_domains: excludedDomains,
						priority_sources: prioritySources
					})
				]);
			}

			// Process news results
			let newsArticles: AINewsArticle[] = [];
			let newsSummary = '';
			let newsTotalResults = 0;
			let newsQueries: string[] = [];
			let totalFilteredOut = 0;

			if (newsResult.status === 'fulfilled' && newsResult.value.status !== 'failed') {
				newsArticles = newsResult.value.articles || [];
				newsSummary = newsResult.value.summary || '';
				newsTotalResults = newsResult.value.totalResults || 0;
				newsQueries = newsResult.value.search_queries_used || [];
				totalFilteredOut += newsResult.value.filteredOutCount || 0;
			} else {
				console.error('[Pulse] News category failed:', newsResult);
			}

			// Process government results
			let govArticles: AINewsArticle[] = [];
			let govSummary = '';
			let govTotalResults = 0;
			let govQueries: string[] = [];

			if (govResult.status === 'fulfilled' && govResult.value.status !== 'failed') {
				govArticles = govResult.value.articles || [];
				govSummary = govResult.value.summary || '';
				govTotalResults = govResult.value.totalResults || 0;
				govQueries = govResult.value.search_queries_used || [];
				totalFilteredOut += govResult.value.filteredOutCount || 0;
			} else {
				console.error('[Pulse] Government category failed:', govResult);
			}

			// Cross-category dedup: remove articles from second category
			// whose URLs already appear in news results
			if (newsArticles.length > 0 && govArticles.length > 0) {
				const newsUrls = new Set(newsArticles.map((a) => a.url));
				govArticles = govArticles.filter((a) => !newsUrls.has(a.url));
			}

			// Calculate combined processing time
			let totalProcessingTime = 0;
			if (newsResult.status === 'fulfilled' && newsResult.value.processing_time_ms) {
				totalProcessingTime += newsResult.value.processing_time_ms;
			}
			if (govResult.status === 'fulfilled' && govResult.value.processing_time_ms) {
				totalProcessingTime = Math.max(totalProcessingTime, govResult.value.processing_time_ms);
			}

			// Update store with combined results
			update((state) => ({
				...state,
				isLoading: false,
				newsArticles,
				govArticles,
				newsTotalResults,
				govTotalResults,
				filteredOutCount: totalFilteredOut,
				structuredSummary: {
					news_summary: newsSummary,
					gov_summary: govSummary
				},
				searchQueriesUsed: [...newsQueries, ...govQueries],
				processingTimeMs: totalProcessingTime,
				taskCompleted: newsArticles.length > 0 || govArticles.length > 0
			}));
		},

		/**
		 * Set a custom filter prompt for a category.
		 * Persists to localStorage.
		 */
		setCustomFilterPrompt(category: SearchCategory, prompt: string | null) {
			saveCustomPrompt(category, prompt);
			update((state) => ({
				...state,
				customFilterPrompts: {
					...state.customFilterPrompts,
					[category]: prompt
				}
			}));
		},

		/**
		 * Set excluded domains (raw text and parsed array).
		 * Persists raw text to localStorage.
		 */
		setExcludedDomains(text: string, domains: string[]) {
			saveTimedValue('pulse_excluded_domains', text || null);
			update((state) => ({
				...state,
				excludedDomainsText: text,
				excludedDomains: domains
			}));
		},

		/**
		 * Set priority sources (raw text and parsed array).
		 * Persists raw text to localStorage.
		 */
		setPrioritySources(text: string, sources: string[]) {
			saveTimedValue('pulse_priority_sources', text || null);
			update((state) => ({
				...state,
				prioritySourcesText: text,
				prioritySources: sources
			}));
		},

		/**
		 * Reset custom filter prompts to defaults.
		 */
		resetCustomFilterPrompts() {
			saveCustomPrompt('news', null);
			saveCustomPrompt('government', null);
			saveTimedValue('pulse_excluded_domains', null);
			saveTimedValue('pulse_priority_sources', null);
			update((state) => ({
				...state,
				customFilterPrompts: { news: null, government: null },
				excludedDomains: [],
				excludedDomainsText: '',
				prioritySources: [],
				prioritySourcesText: ''
			}));
		},

		/**
		 * Reset store to initial state.
		 */
		reset() {
			set({
				...initialState,
				customFilterPrompts: loadCustomPrompts() // Preserve custom prompts
			});
		}
	};
}

export const pulseStore = createPulseStore();
