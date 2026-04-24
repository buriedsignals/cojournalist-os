/**
 * Onboarding Placeholders -- static demo data for the guided tour.
 *
 * USED BY: workspace demo seed, tests/utils/onboarding-placeholders.test.ts
 * DEPENDS ON: $lib/types (ActiveJob)
 *
 * These constants populate empty panels during the guided tour so new users
 * see realistic content before they create their first scout. The data is
 * purely cosmetic and never hits the backend.
 * Exports: PLACEHOLDER_SCOUTS (ActiveJob[]), PLACEHOLDER_UNITS (PlaceholderUnit[])
 */

import type { ActiveJob } from '$lib/types';

// ---------------------------------------------------------------------------
// PlaceholderUnit — lightweight information-unit shape used in the workspace inbox
// ---------------------------------------------------------------------------

export interface PlaceholderUnit {
	unit_id: string;
	statement: string;
	unit_type: string;
	entities: string[];
	source_url: string;
	source_domain: string;
	source_title: string;
	scout_type: 'web' | 'pulse';
	created_at: string;
}

// ---------------------------------------------------------------------------
// PLACEHOLDER_SCOUTS — three demo scouts covering every scout type
// ---------------------------------------------------------------------------

export const PLACEHOLDER_SCOUTS: ActiveJob[] = [
	{
		scraper_name: 'Zurich City Council Agenda',
		scout_type: 'web',
		regularity: 'weekly',
		time: '09:00',
		url: 'https://www.zurich.ch/gemeinderat',
		location: {
			displayName: 'Zurich, Switzerland',
			city: 'Zurich',
			state: 'ZH',
			country: 'CH',
			locationType: 'city'
		},
		last_run: {
			last_run: '03:03:2026 09:00',
			scraper_status: true,
			criteria_status: true,
			card_summary:
				'New agenda items added for March session including transit funding vote.'
		}
	},
	{
		scraper_name: 'Tokyo Urban Development',
		scout_type: 'pulse',
		regularity: 'weekly',
		time: '08:00',
		topic: 'Urban Development',
		location: {
			displayName: 'Tokyo, Japan',
			city: 'Tokyo',
			country: 'JP',
			locationType: 'city'
		},
		last_run: {
			last_run: '03:03:2026 08:00',
			scraper_status: true,
			criteria_status: true,
			card_summary:
				'6 new articles found covering zoning reform and transit expansion.'
		}
	},
	{
		scraper_name: 'Berlin Senate Press Releases',
		scout_type: 'web',
		regularity: 'daily',
		time: '07:00',
		url: 'https://www.berlin.de/sen/kulteu/aktuelles/pressemitteilungen/',
		location: {
			displayName: 'Berlin, Germany',
			city: 'Berlin',
			country: 'DE',
			locationType: 'city'
		},
		last_run: {
			last_run: '04:03:2026 07:00',
			scraper_status: true,
			criteria_status: false,
			card_summary: 'Page updated but no criteria-matching changes found.'
		}
	},
	{
		scraper_name: 'Austin Housing Market',
		scout_type: 'pulse',
		regularity: 'monthly',
		time: '10:00',
		location: {
			displayName: 'Austin, TX',
			state: 'TX',
			country: 'US',
			locationType: 'city'
		},
		topic: 'Real Estate',
		criteria: 'New zoning changes and affordable housing developments',
		last_run: null
	}
];

// ---------------------------------------------------------------------------
// PLACEHOLDER_UNITS — four demo inbox items spanning multiple cities
// ---------------------------------------------------------------------------

export const PLACEHOLDER_UNITS: PlaceholderUnit[] = [
	{
		unit_id: 'onboarding-unit-1',
		statement:
			'Zurich City Council approved CHF 3.2M for expanded tram service to Altstetten',
		unit_type: 'claim',
		entities: ['Zurich', 'Altstetten'],
		source_url: 'https://www.tagesanzeiger.ch/zurich-tram-altstetten',
		source_domain: 'tagesanzeiger.ch',
		source_title: 'Zurich approves tram expansion funding',
		scout_type: 'web',
		created_at: '2026-03-03T09:00:00Z'
	},
	{
		unit_id: 'onboarding-unit-2',
		statement:
			'Tokyo Metropolitan Government announces mixed-use zoning reform for Shibuya ward',
		unit_type: 'claim',
		entities: ['Tokyo', 'Shibuya'],
		source_url: 'https://www.japantimes.co.jp/tokyo-shibuya-zoning',
		source_domain: 'japantimes.co.jp',
		source_title: 'Tokyo announces Shibuya zoning reform',
		scout_type: 'pulse',
		created_at: '2026-03-03T08:00:00Z'
	},
	{
		unit_id: 'onboarding-unit-3',
		statement:
			'Austin City Council passes new ADU ordinance allowing backyard units on all residential lots',
		unit_type: 'claim',
		entities: ['Austin', 'ADU'],
		source_url: 'https://www.statesman.com/austin-adu-ordinance',
		source_domain: 'statesman.com',
		source_title: 'Austin passes ADU ordinance',
		scout_type: 'pulse',
		created_at: '2026-03-03T07:00:00Z'
	},
	{
		unit_id: 'onboarding-unit-4',
		statement:
			'Seoul Transport Authority reports 15% ridership increase on Line 9 extension',
		unit_type: 'claim',
		entities: ['Seoul', 'Line 9'],
		source_url: 'https://www.koreaherald.com/seoul-line9-ridership',
		source_domain: 'koreaherald.com',
		source_title: 'Seoul Line 9 ridership surges',
		scout_type: 'pulse',
		created_at: '2026-03-03T06:00:00Z'
	}
];
