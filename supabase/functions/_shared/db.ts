/**
 * Agent-first response shapers. Produce self-contained JSON so an LLM never
 * needs a follow-up fetch to understand a unit or a scout.
 */

import type { SupabaseClient } from "./supabase.ts";

// ---------------------------------------------------------------------------
// Unit
// ---------------------------------------------------------------------------

export interface UnitEntityRef {
  entity_id: string | null;
  canonical_name: string | null;
  type: string | null;
  mention_text: string;
}

export interface UnitResponse {
  id: string;
  statement: string | null;
  context_excerpt: string | null;
  unit_type: string | null;
  entities: UnitEntityRef[];
  location: Record<string, unknown> | null;
  occurred_at: string | null;
  extracted_at: string | null;
  source: {
    url: string | null;
    title: string | null;
    domain: string | null;
  };
  verification: {
    verified: boolean;
    verified_at: string | null;
    verified_by: string | null;
    notes: string | null;
  };
  usage: {
    used_in_article: boolean;
    used_at: string | null;
    used_in_url: string | null;
  };
  tags: string[];
}

interface RawUnitRow {
  id: string;
  statement?: string | null;
  context_excerpt?: string | null;
  type?: string | null; // column is named `type` in the schema; surfaced as unit_type in the response
  location?: Record<string, unknown> | null;
  occurred_at?: string | null;
  extracted_at?: string | null;
  source_url?: string | null;
  source_title?: string | null;
  source_domain?: string | null;
  verified?: boolean | null;
  verified_at?: string | null;
  verified_by?: string | null;
  verification_notes?: string | null;
  used_in_article?: boolean | null;
  used_at?: string | null;
  used_in_url?: string | null;
  tags?: string[] | null;
}

export async function shapeUnitResponse(
  db: SupabaseClient,
  row: RawUnitRow,
): Promise<UnitResponse> {
  const { data: entityRows } = await db
    .from("unit_entities")
    .select("entity_id, mention_text, entities(canonical_name, type)")
    .eq("unit_id", row.id);

  const entities: UnitEntityRef[] = (entityRows ?? []).map((r) => {
    const ent = (r as { entities?: { canonical_name?: string; type?: string } }).entities;
    return {
      entity_id: r.entity_id ?? null,
      canonical_name: ent?.canonical_name ?? null,
      type: ent?.type ?? null,
      mention_text: (r as { mention_text: string }).mention_text,
    };
  });

  return {
    id: row.id,
    statement: row.statement ?? null,
    context_excerpt: row.context_excerpt ?? null,
    unit_type: row.type ?? null,
    entities,
    location: row.location ?? null,
    occurred_at: row.occurred_at ?? null,
    extracted_at: row.extracted_at ?? null,
    source: {
      url: row.source_url ?? null,
      title: row.source_title ?? null,
      domain: row.source_domain ?? null,
    },
    verification: {
      verified: Boolean(row.verified),
      verified_at: row.verified_at ?? null,
      verified_by: row.verified_by ?? null,
      notes: row.verification_notes ?? null,
    },
    usage: {
      used_in_article: Boolean(row.used_in_article),
      used_at: row.used_at ?? null,
      used_in_url: row.used_in_url ?? null,
    },
    tags: row.tags ?? [],
  };
}

// ---------------------------------------------------------------------------
// Scout
// ---------------------------------------------------------------------------

export interface ScoutResponse {
  id: string;
  name: string;
  type: string;
  criteria: string | null;
  url: string | null;
  location: Record<string, unknown> | null;
  project_id: string | null;
  regularity: string | null;
  schedule_cron: string | null;
  is_active: boolean;
  consecutive_failures: number;
  last_run: {
    started_at: string | null;
    status: string | null;
    articles_count: number | null;
  } | null;
  created_at: string | null;
}

interface RawScoutRow {
  id: string;
  name?: string | null;
  type?: string | null;
  criteria?: string | null;
  url?: string | null;
  location?: Record<string, unknown> | null;
  project_id?: string | null;
  regularity?: string | null;
  schedule_cron?: string | null;
  is_active?: boolean | null;
  consecutive_failures?: number | null;
  created_at?: string | null;
}

export async function shapeScoutResponse(
  db: SupabaseClient,
  row: RawScoutRow,
): Promise<ScoutResponse> {
  const { data: lastRun } = await db
    .from("scout_runs")
    .select("started_at, status, articles_count")
    .eq("scout_id", row.id)
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  return {
    id: row.id,
    name: row.name ?? "",
    type: row.type ?? "",
    criteria: row.criteria ?? null,
    url: row.url ?? null,
    location: row.location ?? null,
    project_id: row.project_id ?? null,
    regularity: row.regularity ?? null,
    schedule_cron: row.schedule_cron ?? null,
    is_active: row.is_active ?? true,
    consecutive_failures: row.consecutive_failures ?? 0,
    last_run: lastRun
      ? {
          started_at: (lastRun as { started_at: string | null }).started_at,
          status: (lastRun as { status: string | null }).status,
          articles_count: (lastRun as { articles_count: number | null }).articles_count,
        }
      : null,
    created_at: row.created_at ?? null,
  };
}
