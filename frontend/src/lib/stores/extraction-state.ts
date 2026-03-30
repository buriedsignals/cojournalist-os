/**
 * Extraction State Store -- tracks whether a data extraction job is running.
 *
 * USED BY: ScrapeView.svelte
 * DEPENDS ON: (none)
 *
 * Simple boolean flag used to disable UI controls during an active
 * Firecrawl extraction job. No side effects.
 */
import { writable } from 'svelte/store';

export const isExtracting = writable<boolean>(false);
