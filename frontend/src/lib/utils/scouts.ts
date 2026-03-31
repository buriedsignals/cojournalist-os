/**
 * Scout Utilities -- pure functions for scout card display and status logic.
 *
 * USED BY: ScoutsPanel.svelte, ScoutScheduleModal.svelte,
 *          tests/utils/scouts.test.ts
 * DEPENDS ON: $lib/types (ScoutType)
 *
 * Extracted from ScoutsPanel for testability. Contains credit costs,
 * schedule formatting, URL truncation, markdown stripping, and the
 * consolidated scout status cascade (priority-ordered condition matching).
 */

import type { ScoutType } from '$lib/types';

/** Credit costs per scout type (see backend/app/utils/credits.py:CREDIT_COSTS) */
export const SCOUT_COSTS: Record<ScoutType, number> = {
	civic: 20,
	pulse: 7,
	social: 2, // Base cost (Instagram/X). Facebook is 15.
	web: 1
};

/** Platform-specific costs for social scouts */
export const SOCIAL_SCOUT_COSTS: Record<string, number> = {
	instagram: 2,
	x: 2,
	twitter: 2,
	facebook: 15,
	tiktok: 2
};

/** Get credit cost for a scout, with platform awareness for social scouts. */
export function getScoutCost(type: ScoutType, platform?: string): number {
	if (type === 'social' && platform) {
		return SOCIAL_SCOUT_COSTS[platform] ?? SCOUT_COSTS.social;
	}
	return SCOUT_COSTS[type] ?? 1;
}

/** Channel-specific costs for data extraction */
export const EXTRACT_COSTS: Record<string, number> = {
	website: 1,
	social: 2,
	instagram: 2,
	facebook: 15,
	tiktok: 2,
	instagram_comments: 15
};

/** Format a regularity + time into a human-readable schedule string. */
export function formatRegularity(regularity: string, time?: string): string {
	if (regularity === 'weekly') return 'Weekly';
	if (regularity === 'monthly') return 'Monthly';

	if (regularity === 'daily' && time) {
		const [hourStr, minuteStr] = time.split(':');
		const hour = parseInt(hourStr, 10);
		const minute = parseInt(minuteStr, 10);
		const period = hour >= 12 ? 'PM' : 'AM';
		const displayHour = hour % 12 || 12;
		const displayTime =
			minute === 0 ? `${displayHour}${period}` : `${displayHour}:${minuteStr}${period}`;
		return `Daily at ${displayTime}`;
	}

	return regularity.charAt(0).toUpperCase() + regularity.slice(1);
}

/** Truncate a URL for display, showing hostname + path. */
export function truncateUrl(url: string, maxLength = 40): string {
	try {
		const parsed = new URL(url);
		const display = parsed.hostname + parsed.pathname;
		return display.length > maxLength ? display.slice(0, maxLength - 3) + '...' : display;
	} catch {
		return url.length > maxLength ? url.slice(0, maxLength - 3) + '...' : url;
	}
}

/** Strip markdown formatting from text for cleaner card display. */
export function stripMarkdown(text: string): string {
	if (!text) return '';
	return (
		text
			.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [text](url) → text
			.replace(/\*\*([^*]+)\*\*/g, '$1') // bold (before bullets)
			.replace(/\*([^*]+)\*/g, '$1') // italic (before bullets)
			.replace(/^[•\-*]\s*/gm, '') // bullets
			.replace(/#{1,6}\s*/g, '') // headers
			.replace(/\s+/g, ' ') // collapse whitespace
			.trim()
			.slice(0, 150) + (text.length > 150 ? '...' : '')
	);
}

/**
 * Consolidated scout status system.
 * Single pill replaces the old two-badge (execution + criteria) approach.
 * See docs/plans/2026-03-03-scout-status-consolidation-design.md
 */

export type StatusVariant = 'success' | 'error' | 'neutral' | 'warning' | 'waiting';

export type StatusKey = 'awaitingFirstRun' | 'runFailed' | 'newFindings' | 'match' | 'noChanges' | 'noMatch';

/** Scout data needed for status display. */
export interface ScoutStatusInput {
	type: ScoutType;
	last_run?: {
		scraper_status?: boolean | null;
		criteria_status?: boolean | null;
		card_summary?: string;
	} | null;
}

export interface ScoutStatusResult {
	variant: StatusVariant;
	key: StatusKey;
}

/**
 * Status config: priority cascade for the single status pill.
 * Each entry has a condition function, the i18n key suffix, and the visual variant.
 * Evaluated in order — first match wins.
 */
const STATUS_CASCADE: Array<{
	key: StatusKey;
	variant: StatusVariant;
	match: (input: ScoutStatusInput) => boolean;
}> = [
	// Priority 1: No run yet
	{
		key: 'awaitingFirstRun',
		variant: 'waiting',
		match: (s) => !s.last_run,
	},
	// Priority 2: Execution failed
	{
		key: 'runFailed',
		variant: 'error',
		match: (s) => s.last_run?.scraper_status === false,
	},
	// Priority 3a: Criteria matched — pulse, social, or civic
	{
		key: 'newFindings',
		variant: 'success',
		match: (s) => s.last_run?.criteria_status === true && (s.type === 'pulse' || s.type === 'social' || s.type === 'civic'),
	},
	// Priority 3b: Criteria matched — web
	{
		key: 'match',
		variant: 'success',
		match: (s) => s.last_run?.criteria_status === true && s.type === 'web',
	},
	// Priority 4a: Web scout — no changes detected
	{
		key: 'noChanges',
		variant: 'neutral',
		match: (s) => s.type === 'web' && s.last_run?.card_summary?.toLowerCase().includes('no changes') === true,
	},
	// Priority 4b: Web scout — changes detected but criteria not met
	{
		key: 'noMatch',
		variant: 'warning',
		match: (s) => s.type === 'web',
	},
	// Priority 4c: pulse — no new results
	{
		key: 'noChanges',
		variant: 'neutral',
		match: () => true,
	},
];

/**
 * Get the consolidated status for a scout card.
 * Returns a variant for styling and a key for i18n lookup.
 */
export function getScoutStatus(scout: ScoutStatusInput): ScoutStatusResult {
	for (const entry of STATUS_CASCADE) {
		if (entry.match(scout)) {
			return { variant: entry.variant, key: entry.key };
		}
	}
	// Unreachable — last entry always matches
	return { variant: 'neutral', key: 'noChanges' };
}
