/**
 * Workspace types — shapes derived from Supabase Edge Functions (OSS) and
 * FastAPI routes (SaaS).
 *
 * Envelope divergence is tolerated by the api-client helpers in
 * `$lib/api-client.ts` via a unified unwrap rule:
 *
 *   body.data ?? body.items ?? body
 *
 * This lets the frontend treat Edge Function responses like
 * `{items, pagination}` and FastAPI responses like `{data: [...]}` (or bare
 * arrays) uniformly. Where a bespoke shape is needed (e.g. the export-claude
 * markdown payload), the helper documents it in JSDoc.
 *
 * See `docs/migration-plans/04-workspace-ui.md` PR 1 for authoritative
 * contracts and the full shape-mismatch audit.
 */

// ---------------------------------------------------------------------------
// Project
// ---------------------------------------------------------------------------

/**
 * Investigation project — logical grouping of scouts + units.
 *
 * Shape derived from:
 *  - Edge Function `supabase/functions/projects/index.ts` (single row from
 *    `projects` table: id, user_id, name, description, visibility, tags,
 *    created_at, updated_at).
 *  - No FastAPI equivalent today — helper is Edge-only and returns the
 *    Edge Function shape verbatim.
 */
export interface Project {
	id: string;
	user_id?: string;
	name: string;
	description?: string | null;
	visibility?: 'private' | 'team';
	tags?: string[];
	created_at: string;
	updated_at?: string | null;
}

// ---------------------------------------------------------------------------
// Scout
// ---------------------------------------------------------------------------

/**
 * Scout category — labels used by the ScoutList UI (location, beat) map to
 * the `pulse` backend type; the rest map 1:1.
 */
export type ScoutUiTemplate = 'location' | 'beat' | 'page' | 'social' | 'civic';

/**
 * Backend scout type (persisted to the database).
 */
export type ScoutType = 'web' | 'pulse' | 'social' | 'civic';

/**
 * Scout — periodic job that produces units.
 *
 * Shape derived from:
 *  - Edge Function `supabase/functions/scouts/index.ts` →
 *    `shapeScoutResponse` in `supabase/functions/_shared/db.ts` (the canonical
 *    agent-first envelope with nested `last_run`).
 *  - FastAPI `backend/app/routers/v1.py` (`/v1/scouts`) returns a similar flat
 *    row; the api-client tolerates both.
 */
export interface Scout {
	id: string;
	name: string;
	type: ScoutType;
	criteria?: string | null;
	url?: string | null;
	platform?: string | null;
	location?: Record<string, unknown> | null;
	project_id?: string | null;
	regularity?: string | null;
	schedule_cron?: string | null;
	is_active: boolean;
	consecutive_failures?: number;
	last_run?: {
		started_at: string | null;
		status: string | null;
		articles_count: number | null;
	} | null;
	created_at?: string | null;
}

/**
 * Payload accepted by `workspaceApi.createScout`. Mirrors the Edge Function
 * `CreateSchema`; template-aware callers pre-fill `type`/`regularity` from the
 * picked template (`location`/`beat` → `pulse`, `page` → `web`).
 */
export interface CreateScoutInput {
	name: string;
	type: ScoutType;
	criteria?: string;
	url?: string;
	location?: Record<string, unknown>;
	regularity?: 'daily' | 'weekly' | 'monthly';
	schedule_cron?: string;
	project_id?: string;
	priority_sources?: string[];
}

// ---------------------------------------------------------------------------
// Unit
// ---------------------------------------------------------------------------

/**
 * Entity reference embedded in a unit (chip-style display in the drawer).
 *
 * Shape derived from `UnitEntityRef` in `supabase/functions/_shared/db.ts`.
 */
export interface UnitEntityRef {
	entity_id: string | null;
	canonical_name: string | null;
	type: string | null;
	mention_text: string;
}

/**
 * Information unit (atomic fact from a scout run or manual ingest).
 *
 * Shape derived from `UnitResponse` in `supabase/functions/_shared/db.ts`.
 * FastAPI `backend/app/routers/units.py` exposes a flatter
 * `InformationUnit` shape; the api-client helpers surface the richer
 * Edge Function envelope and fall back to the flat FastAPI shape where the
 * nested fields are absent.
 */
export interface Unit {
	id: string;
	statement: string | null;
	context_excerpt?: string | null;
	unit_type: string | null;
	entities: UnitEntityRef[];
	location?: Record<string, unknown> | null;
	occurred_at?: string | null;
	extracted_at: string | null;
	source: {
		url: string | null;
		title: string | null;
		domain: string | null;
	};
	verification?: {
		verified: boolean;
		verified_at: string | null;
		verified_by: string | null;
		notes: string | null;
	};
	usage?: {
		used_in_article: boolean;
		used_at: string | null;
		used_in_url: string | null;
	};
	tags?: string[];
	scout_id?: string;
	scout_name?: string;
	similarity?: number | null;
}

// ---------------------------------------------------------------------------
// Reflection
// ---------------------------------------------------------------------------

/**
 * Agent-written synthesized summary referencing units and/or entities.
 *
 * Shape derived from:
 *  - Edge Function `supabase/functions/reflections/index.ts` (plain row from
 *    the `reflections` table).
 *  - No FastAPI equivalent today — helper is Edge-only.
 */
export interface Reflection {
	id: string;
	user_id?: string;
	scope_description: string;
	content: string;
	generated_by: string;
	project_id?: string | null;
	time_range_start?: string | null;
	time_range_end?: string | null;
	source_unit_ids?: string[];
	source_entity_ids?: string[];
	metadata?: Record<string, unknown>;
	created_at: string;
}

// ---------------------------------------------------------------------------
// Entity
// ---------------------------------------------------------------------------

/**
 * Canonical entity (person, org, place, policy, event, document, other).
 *
 * Shape derived from:
 *  - Edge Function `supabase/functions/entities/index.ts` (plain row from
 *    the `entities` table; `/entities/:id` additionally attaches `mentions`).
 *  - No FastAPI equivalent today — helper is Edge-only.
 */
export interface Entity {
	id: string;
	user_id?: string;
	canonical_name: string;
	type: 'person' | 'org' | 'place' | 'policy' | 'event' | 'document' | 'other' | string;
	aliases?: string[];
	metadata?: Record<string, unknown>;
	mention_count?: number;
	created_at?: string;
	mentions?: Array<{
		unit_id: string;
		mention_text: string;
		confidence: number | null;
		resolved_at: string | null;
	}>;
}

// ---------------------------------------------------------------------------
// Paginated envelopes
// ---------------------------------------------------------------------------

/**
 * Paginated units page used by the Inbox store. `next_cursor` is a stringified
 * integer offset (the Edge Functions paginate by `{offset, limit}`; the
 * client encodes the next offset as a cursor to keep the API surface cursor-
 * shaped for a future cursor-native backend).
 */
export interface PaginatedUnits {
	units: Unit[];
	next_cursor: string | null;
}

/**
 * Generic Edge Function pagination envelope. Exported for tests that want to
 * assert on the raw shape before helper unwrap.
 */
export interface EdgePagination {
	total: number;
	offset: number;
	limit: number;
	has_more: boolean;
}
