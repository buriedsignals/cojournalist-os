const POLICY_TERMS =
  /\b(policy|policies|reform|regulation|regulations|law|laws|legislation|legislative|program|programs|funding|plan|plans|planning|zoning|ordinance|consultation|strategy|initiative|initiatives)\b/i;

export function buildBeatCriteriaRule(criteria: string | null | undefined): string {
  const text = criteria?.trim();
  if (!text) return "";
  if (POLICY_TERMS.test(text)) {
    return "Criteria strictness: keep only articles materially about policy, regulation, legislation, planning, official programs, funding, or government decisions related to the criteria. Reject market statistics, listings, service pages, explainers, and general sector coverage without a concrete policy or governance angle.";
  }
  return "Criteria strictness: keep only articles where the user's criteria is a primary subject, not a passing mention or broad sector adjacency.";
}
