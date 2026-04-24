#!/usr/bin/env -S deno run --allow-net --allow-env --allow-read --allow-write

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import {
  EMBEDDING_MODEL_TAG,
  geminiEmbed,
} from "../supabase/functions/_shared/gemini.ts";

type TableName = "information_units" | "reflections" | "execution_records";

interface TableState {
  lastId: string | null;
  processed: number;
  updated: number;
  completed: boolean;
}

interface BackfillState {
  targetModel: string;
  updatedAt: string;
  tables: Record<TableName, TableState>;
}

interface InformationUnitRow {
  id: string;
  statement: string;
  source_title: string | null;
}

interface ReflectionRow {
  id: string;
  content: string;
}

interface ExecutionRecordRow {
  id: string;
  summary_text: string;
}

const DEFAULT_STATE_PATH = "/tmp/cojournalist-gemini-embedding-v2-backfill-state.json";
const DEFAULT_BATCH_SIZE = 100;
const TABLES: TableName[] = ["information_units", "reflections", "execution_records"];

function required(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing required env var: ${name}`);
  return value;
}

function loadTables(): TableName[] {
  const raw = (Deno.env.get("BACKFILL_TABLES") ?? TABLES.join(",")).trim();
  const parsed = raw.split(",").map((part) => part.trim()).filter(Boolean);
  const invalid = parsed.filter((table) => !TABLES.includes(table as TableName));
  if (invalid.length > 0) {
    throw new Error(`Invalid BACKFILL_TABLES entries: ${invalid.join(", ")}`);
  }
  return parsed as TableName[];
}

function loadBatchSize(): number {
  const raw = Deno.env.get("BACKFILL_BATCH_SIZE");
  if (!raw) return DEFAULT_BATCH_SIZE;
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error("BACKFILL_BATCH_SIZE must be a positive integer");
  }
  return value;
}

function emptyState(): BackfillState {
  return {
    targetModel: EMBEDDING_MODEL_TAG,
    updatedAt: new Date().toISOString(),
    tables: {
      information_units: { lastId: null, processed: 0, updated: 0, completed: false },
      reflections: { lastId: null, processed: 0, updated: 0, completed: false },
      execution_records: { lastId: null, processed: 0, updated: 0, completed: false },
    },
  };
}

async function loadState(path: string, reset: boolean): Promise<BackfillState> {
  if (reset) return emptyState();

  try {
    const text = await Deno.readTextFile(path);
    const parsed = JSON.parse(text) as BackfillState;
    if (parsed.targetModel !== EMBEDDING_MODEL_TAG) {
      return emptyState();
    }
    return parsed;
  } catch (error) {
    if (error instanceof Deno.errors.NotFound) return emptyState();
    throw error;
  }
}

async function saveState(path: string, state: BackfillState): Promise<void> {
  state.updatedAt = new Date().toISOString();
  await Deno.writeTextFile(path, `${JSON.stringify(state, null, 2)}\n`);
}

async function fetchInformationUnits(
  supabase: any,
  tableState: TableState,
  batchSize: number,
): Promise<InformationUnitRow[]> {
  let query = supabase
    .from("information_units")
    .select("id, statement, source_title")
    .not("embedding", "is", null)
    .neq("embedding_model", EMBEDDING_MODEL_TAG)
    .order("id", { ascending: true })
    .limit(batchSize);

  if (tableState.lastId) query = query.gt("id", tableState.lastId);
  const { data, error } = await query;
  if (error) throw new Error(`information_units fetch failed: ${error.message}`);
  return (data ?? []) as InformationUnitRow[];
}

async function fetchReflections(
  supabase: any,
  tableState: TableState,
  batchSize: number,
): Promise<ReflectionRow[]> {
  let query = supabase
    .from("reflections")
    .select("id, content")
    .not("embedding", "is", null)
    .neq("embedding_model", EMBEDDING_MODEL_TAG)
    .order("id", { ascending: true })
    .limit(batchSize);

  if (tableState.lastId) query = query.gt("id", tableState.lastId);
  const { data, error } = await query;
  if (error) throw new Error(`reflections fetch failed: ${error.message}`);
  return (data ?? []) as ReflectionRow[];
}

async function fetchExecutionRecords(
  supabase: any,
  tableState: TableState,
  batchSize: number,
): Promise<ExecutionRecordRow[]> {
  let query = supabase
    .from("execution_records")
    .select("id, summary_text")
    .not("embedding", "is", null)
    .neq("embedding_model", EMBEDDING_MODEL_TAG)
    .order("id", { ascending: true })
    .limit(batchSize);

  if (tableState.lastId) query = query.gt("id", tableState.lastId);
  const { data, error } = await query;
  if (error) throw new Error(`execution_records fetch failed: ${error.message}`);
  return (data ?? []) as ExecutionRecordRow[];
}

async function updateInformationUnit(
  supabase: any,
  row: InformationUnitRow,
): Promise<void> {
  const embedding = await geminiEmbed(row.statement, "RETRIEVAL_DOCUMENT", {
    title: row.source_title,
  });
  const { error } = await supabase
    .from("information_units")
    .update({
      embedding,
      embedding_model: EMBEDDING_MODEL_TAG,
    })
    .eq("id", row.id);
  if (error) throw new Error(`information_units update failed for ${row.id}: ${error.message}`);
}

async function updateReflection(
  supabase: any,
  row: ReflectionRow,
): Promise<void> {
  const embedding = await geminiEmbed(row.content, "RETRIEVAL_DOCUMENT");
  const { error } = await supabase
    .from("reflections")
    .update({
      embedding,
      embedding_model: EMBEDDING_MODEL_TAG,
    })
    .eq("id", row.id);
  if (error) throw new Error(`reflections update failed for ${row.id}: ${error.message}`);
}

async function updateExecutionRecord(
  supabase: any,
  row: ExecutionRecordRow,
): Promise<void> {
  const embedding = await geminiEmbed(row.summary_text, "SEMANTIC_SIMILARITY");
  const { error } = await supabase
    .from("execution_records")
    .update({
      embedding,
      embedding_model: EMBEDDING_MODEL_TAG,
    })
    .eq("id", row.id);
  if (error) throw new Error(`execution_records update failed for ${row.id}: ${error.message}`);
}

async function processTable(
  supabase: any,
  statePath: string,
  state: BackfillState,
  table: TableName,
  batchSize: number,
): Promise<void> {
  const tableState = state.tables[table];
  if (tableState.completed) {
    console.log(`[skip] ${table}: already completed in checkpoint`);
    return;
  }

  console.log(`[start] ${table}: lastId=${tableState.lastId ?? "(beginning)"}`);
  while (true) {
    const rows = table === "information_units"
      ? await fetchInformationUnits(supabase, tableState, batchSize)
      : table === "reflections"
      ? await fetchReflections(supabase, tableState, batchSize)
      : await fetchExecutionRecords(supabase, tableState, batchSize);

    if (rows.length === 0) {
      tableState.completed = true;
      await saveState(statePath, state);
      console.log(`[done] ${table}: processed=${tableState.processed} updated=${tableState.updated}`);
      return;
    }

    for (const row of rows) {
      if (table === "information_units") {
        await updateInformationUnit(supabase, row as InformationUnitRow);
      } else if (table === "reflections") {
        await updateReflection(supabase, row as ReflectionRow);
      } else {
        await updateExecutionRecord(supabase, row as ExecutionRecordRow);
      }
      tableState.lastId = row.id;
      tableState.processed += 1;
      tableState.updated += 1;
    }

    await saveState(statePath, state);
    console.log(
      `[batch] ${table}: processed=${tableState.processed} updated=${tableState.updated} lastId=${tableState.lastId}`,
    );
  }
}

async function main() {
  const supabaseUrl = required("SUPABASE_URL");
  const serviceRoleKey = required("SUPABASE_SERVICE_ROLE_KEY");
  required("GEMINI_API_KEY");

  const batchSize = loadBatchSize();
  const statePath = Deno.env.get("BACKFILL_STATE_PATH") ?? DEFAULT_STATE_PATH;
  const resetState = (Deno.env.get("RESET_BACKFILL_STATE") ?? "false").toLowerCase() === "true";
  const tables = loadTables();

  const state = await loadState(statePath, resetState);
  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  console.log(`Target model: ${EMBEDDING_MODEL_TAG}`);
  console.log(`State path: ${statePath}`);
  console.log(`Batch size: ${batchSize}`);
  console.log(`Tables: ${tables.join(", ")}`);

  for (const table of tables) {
    await processTable(supabase, statePath, state, table, batchSize);
  }
}

if (import.meta.main) {
  await main();
}
