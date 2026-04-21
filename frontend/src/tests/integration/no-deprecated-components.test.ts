/**
 * Integration test: the old sidebar-nav SPA components + stores must be deleted
 * by Plan 04 PR 3. Until PR 3 ships, this suite is gated so CI passes in PR 2
 * (`WORKSPACE_DELETIONS_DONE` unset → `test.todo` markers).
 *
 * After PR 3 merges, set the env var (locally + in CI) to flip these into
 * hard assertions. Or delete this file at that point and keep
 * `tests/integration/workspace-flow.test.ts` as the single workspace canary.
 */
import { describe, expect, it } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';

// Resolve relative to the frontend/ directory (where vitest runs).
const FRONTEND_ROOT = path.resolve(__dirname, '../../../');

// Files PR 3 deletes. Keep this list in sync with
// docs/migration-plans/04-workspace-ui.md "Files deleted".
const DEPRECATED_PATHS: string[] = [
	// feed/
	'src/lib/components/feed/AISelectPanel.svelte',
	'src/lib/components/feed/ExportSlideOver.svelte',
	'src/lib/components/feed/FeedView.svelte',
	'src/lib/components/feed/UnitCard.svelte',
	'src/lib/components/feed/UnitGrid.svelte',
	// sidebars/
	'src/lib/components/sidebars/UnifiedSidebar.svelte',
	// news/
	'src/lib/components/news/BeatScoutView.svelte',
	'src/lib/components/news/PageScoutView.svelte',
	'src/lib/components/news/SocialScoutView.svelte',
	'src/lib/components/news/CivicScoutView.svelte',
	// panels/
	'src/lib/components/panels/ScoutsPanel.svelte',
	// views/
	'src/lib/components/views/ScrapeView.svelte',
	// stores/
	'src/lib/stores/feed.ts',
	'src/lib/stores/feed-refresh.ts',
	'src/lib/stores/pulse.ts',
	'src/lib/stores/sidebar-nav.ts',
	'src/lib/stores/scouts-refresh.ts',
	'src/lib/stores/extraction-state.ts'
];

const DELETIONS_DONE = process.env.WORKSPACE_DELETIONS_DONE === '1';

describe('deprecated components are removed (post PR 3)', () => {
	if (!DELETIONS_DONE) {
		for (const rel of DEPRECATED_PATHS) {
			it.todo(`deletes ${rel} (set WORKSPACE_DELETIONS_DONE=1 after PR 3)`);
		}
		return;
	}

	for (const rel of DEPRECATED_PATHS) {
		it(`does not contain ${rel}`, () => {
			const abs = path.join(FRONTEND_ROOT, rel);
			expect(fs.existsSync(abs), `${rel} still exists — PR 3 did not delete it`).toBe(false);
		});
	}
});
