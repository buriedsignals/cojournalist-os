export type SearchMatchCategory = "direct" | "related" | "loose";
export type SearchKeywordField =
  | "statement"
  | "context_excerpt"
  | "source"
  | "entities"
  | "scout_name"
  | "linked_scouts"
  | "tags";

export interface SearchMatchInfo {
  category: SearchMatchCategory;
  reason: string;
  keyword_fields: SearchKeywordField[];
  semantic_similarity: number | null;
  below_interest_threshold: boolean;
}

const SEMANTIC_INTEREST_THRESHOLD = 0.78;

export function searchTokens(queryText: string): string[] {
  return (queryText.toLowerCase().match(/[\p{L}\p{N}]{2,}/gu) ?? []);
}

function keywordTokens(queryText: string): string[] {
  return searchTokens(queryText).filter((token) =>
    token.length >= 4 || /^\d{2,}$/.test(token)
  );
}

export function isPreciseSearchQuery(queryText: string): boolean {
  const trimmed = queryText.trim();
  if (/^".+"$/.test(trimmed)) return true;
  const tokens = searchTokens(trimmed);
  if (tokens.length !== 1) return false;
  return tokens[0].length >= 4 || /^\d{2,}$/.test(tokens[0]);
}

function stringsFromValue(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) {
    return value.flatMap((entry) => stringsFromValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap((entry) =>
      stringsFromValue(entry)
    );
  }
  return [];
}

function fieldStrings(
  item: Record<string, unknown>,
): Record<SearchKeywordField, string[]> {
  return {
    statement: stringsFromValue(item.statement),
    context_excerpt: stringsFromValue(item.context_excerpt),
    source: stringsFromValue(item.source),
    entities: stringsFromValue(item.entities),
    scout_name: stringsFromValue(item.scout_name),
    linked_scouts: stringsFromValue(item.linked_scouts),
    tags: stringsFromValue(item.tags),
  };
}

export function matchingKeywordFields(
  queryText: string,
  item: Record<string, unknown>,
): SearchKeywordField[] {
  const tokens = keywordTokens(queryText);
  if (tokens.length === 0) return [];

  const fields = fieldStrings(item);
  return (Object.entries(fields) as Array<[SearchKeywordField, string[]]>)
    .filter(([, values]) => {
      const haystack = values.join(" ").toLowerCase();
      return tokens.some((token) => haystack.includes(token));
    })
    .map(([field]) => field);
}

export function unitHasKeywordHit(
  queryText: string,
  item: Record<string, unknown>,
): boolean {
  return matchingKeywordFields(queryText, item).length > 0;
}

function humanFieldLabel(field: SearchKeywordField): string {
  switch (field) {
    case "context_excerpt":
      return "context";
    case "scout_name":
      return "scout";
    case "linked_scouts":
      return "linked scout";
    default:
      return field.replace(/_/g, " ");
  }
}

function joinFieldLabels(fields: SearchKeywordField[]): string {
  const labels = fields.map(humanFieldLabel);
  if (labels.length <= 1) return labels[0] ?? "text";
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(", ")}, and ${labels.at(-1)}`;
}

export function buildSearchMatchInfo(
  queryText: string,
  item: Record<string, unknown>,
  semanticSimilarity: number | null,
): SearchMatchInfo {
  const keywordFields = matchingKeywordFields(queryText, item);
  if (keywordFields.length > 0) {
    return {
      category: "direct",
      reason: `Direct text match in ${joinFieldLabels(keywordFields)}.`,
      keyword_fields: keywordFields,
      semantic_similarity: semanticSimilarity,
      below_interest_threshold: false,
    };
  }

  if (semanticSimilarity === null) {
    return {
      category: "direct",
      reason: "Matched indexed text for this unit.",
      keyword_fields: [],
      semantic_similarity: null,
      below_interest_threshold: false,
    };
  }

  if (semanticSimilarity >= SEMANTIC_INTEREST_THRESHOLD) {
    return {
      category: "related",
      reason: "Related semantic match surfaced by hybrid search.",
      keyword_fields: [],
      semantic_similarity: semanticSimilarity,
      below_interest_threshold: false,
    };
  }

  return {
    category: "loose",
    reason: "Low-confidence semantic match shown for recall.",
    keyword_fields: [],
    semantic_similarity: semanticSimilarity,
    below_interest_threshold: true,
  };
}

export function filterPreciseSearchResults(
  queryText: string,
  items: Record<string, unknown>[],
): Record<string, unknown>[] {
  if (!isPreciseSearchQuery(queryText)) return items;
  return items.filter((item) => unitHasKeywordHit(queryText, item));
}
