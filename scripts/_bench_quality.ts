/**
 * Quality validation helpers for the scout benchmark suite.
 *
 * Port of backend/scripts/benchmark_pulse.py quality checks
 * (validate_language / validate_date_relevance / validate_source_diversity /
 *  validate_undated_ratio / validate_priority_sources) + flaw detection +
 * markdown report writer. Used by --audit mode on benchmark-beat.ts.
 */

export interface Article {
  title: string;
  url: string;
  source?: string;
  date?: string | null;
  summary?: string | null;
}

export interface QualityCheck {
  check: string;
  status: "PASS" | "FAIL" | "WARN" | "SKIP";
  detail: string;
  data?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Language detection — pure heuristic, no npm deps, matches prod's langdetect
// coverage for the 12 supported locales within benchmark tolerance.
// ---------------------------------------------------------------------------

const LANG_MARKERS: Record<string, RegExp[]> = {
  en: [/\b(the|and|of|is|in|to|for|with|on|this|that)\b/gi],
  de: [/\b(und|der|die|das|ist|nicht|mit|sich|auf|ein|eine|den|dem)\b/gi, /[\u00df\u00e4\u00f6\u00fc]/g],
  fr: [/\b(le|la|les|et|de|est|une|un|des|pour|dans|avec|sur)\b/gi, /[\u00e9\u00e8\u00ea\u00e0\u00e7]/g],
  es: [/\b(el|la|los|las|y|de|es|un|una|con|para|por|que)\b/gi, /[\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa]/g],
  it: [/\b(il|la|e|di|un|una|per|con|che|sono|gli)\b/gi, /[\u00e0\u00e8\u00e9\u00ec\u00f2\u00f9]/g],
  pt: [/\b(o|a|os|as|e|de|um|uma|para|com|que|do|da)\b/gi, /[\u00e3\u00f5\u00e1\u00e9\u00ed\u00f3\u00fa\u00e7]/g],
  nl: [/\b(de|het|een|en|van|is|op|voor|met|dat|niet|zijn)\b/gi],
  no: [/\b(og|er|det|en|ikke|av|med|for|som|til|i|p\u00e5)\b/gi, /[\u00e6\u00f8\u00e5]/g],
  sv: [/\b(och|att|det|som|en|p\u00e5|av|f\u00f6r|med|har)\b/gi, /[\u00e5\u00e4\u00f6]/g],
  da: [/\b(og|er|det|en|ikke|af|med|for|som|til)\b/gi, /[\u00e6\u00f8\u00e5]/g],
  fi: [/\b(ja|on|ei|se|h\u00e4n|kuin|mutta|olla|t\u00e4m\u00e4|kun)\b/gi, /[\u00e4\u00f6]/g],
  pl: [/\b(i|w|na|z|do|jest|nie|to|si\u0119|\u017ce)\b/gi, /[\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c]/g],
};

export function detectLanguage(text: string): string | null {
  if (!text || text.length < 20) return null;
  let best: string | null = null;
  let bestScore = 0;
  for (const [lang, markers] of Object.entries(LANG_MARKERS)) {
    let score = 0;
    for (const m of markers) score += (text.match(m) ?? []).length;
    if (score > bestScore) {
      best = lang;
      bestScore = score;
    }
  }
  return bestScore >= 3 ? best : null;
}

export function validateLanguage(
  summary: string,
  expectedLang: string,
): QualityCheck {
  if (!summary) {
    return { check: "language", status: "SKIP", detail: "no summary" };
  }
  const bullets = summary
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 20);
  if (bullets.length === 0) {
    return { check: "language", status: "SKIP", detail: "no bullet lines" };
  }
  const mismatches: Array<{ text: string; detected: string | null }> = [];
  for (const b of bullets) {
    const d = detectLanguage(b);
    if (d && d !== expectedLang) {
      mismatches.push({ text: b.slice(0, 80), detected: d });
    }
  }
  if (mismatches.length > 0) {
    return {
      check: "language",
      status: "FAIL",
      detail: `${mismatches.length}/${bullets.length} bullets wrong language`,
      data: { mismatches },
    };
  }
  return {
    check: "language",
    status: "PASS",
    detail: `${bullets.length} bullets OK (${expectedLang})`,
  };
}

// ---------------------------------------------------------------------------
// Date relevance — flag stale-year references + PDFs.
// ---------------------------------------------------------------------------

function extractContentYear(url: string, title: string): number | null {
  const haystack = `${url} ${title}`;
  // Match 4-digit years 2000-2099
  const matches = [...haystack.matchAll(/(20\d{2})/g)].map((m) => parseInt(m[1], 10));
  if (matches.length === 0) return null;
  // Most recent year wins (URLs often have multiple, e.g. /archive/2024/article-2025/)
  return Math.max(...matches);
}

export function validateDateRelevance(articles: Article[]): QualityCheck {
  const currentYear = new Date().getFullYear();
  const stale: Array<{ title: string; url: string; year: number }> = [];
  const pdfs: Array<{ title: string; url: string }> = [];
  for (const a of articles) {
    const url = a.url ?? "";
    const title = a.title ?? "";
    if (url.toLowerCase().includes(".pdf")) pdfs.push({ title, url });
    const year = extractContentYear(url, title);
    if (year !== null && year < currentYear - 1) {
      stale.push({ title, url, year });
    }
  }
  return {
    check: "date_relevance",
    status: stale.length > 0 ? "WARN" : "PASS",
    detail: `${stale.length} stale, ${pdfs.length} PDFs`,
    data: { stale_articles: stale, pdf_count: pdfs.length },
  };
}

// ---------------------------------------------------------------------------
// Source diversity — per-mode cap on domain repetition.
// ---------------------------------------------------------------------------

export function validateSourceDiversity(
  articles: Article[],
  sourceMode: "reliable" | "niche",
): QualityCheck {
  const cap = sourceMode === "niche" ? 2 : 3;
  const counts = new Map<string, number>();
  for (const a of articles) {
    try {
      const d = new URL(a.url).hostname.toLowerCase();
      counts.set(d, (counts.get(d) ?? 0) + 1);
    } catch {
      /* skip bad URL */
    }
  }
  const violations: Record<string, number> = {};
  for (const [d, c] of counts) if (c > cap) violations[d] = c;
  const unique = counts.size;
  const violCount = Object.keys(violations).length;
  return {
    check: "source_diversity",
    status: violCount > 0 ? "WARN" : "PASS",
    detail: `${unique} domains` +
      (violCount > 0 ? `, ${violCount} over cap (${cap})` : ""),
    data: { unique_domains: unique, violations },
  };
}

// ---------------------------------------------------------------------------
// Undated ratio.
// ---------------------------------------------------------------------------

export function validateUndatedRatio(
  articles: Article[],
  category: string,
): QualityCheck {
  if (articles.length === 0) {
    return {
      check: "undated_ratio",
      status: "PASS",
      detail: "no articles",
      data: { ratio: 0 },
    };
  }
  const undated = articles.filter((a) => !a.date).length;
  const ratio = undated / articles.length;
  const threshold = category === "government" ? 0.7 : 0.5;
  return {
    check: "undated_ratio",
    status: ratio > threshold ? "WARN" : "PASS",
    detail: `${undated}/${articles.length} undated (${Math.round(ratio * 100)}%)`,
    data: { ratio: Math.round(ratio * 1000) / 1000 },
  };
}

// ---------------------------------------------------------------------------
// Priority sources — user-configured domains should appear in results.
// ---------------------------------------------------------------------------

export function validatePrioritySources(
  articles: Article[],
  prioritySources: string[],
): QualityCheck {
  if (!prioritySources || prioritySources.length === 0) {
    return {
      check: "priority_sources",
      status: "SKIP",
      detail: "no priority sources set",
    };
  }
  const expected = new Set(
    prioritySources.map((u) => {
      try {
        return new URL(u).hostname.toLowerCase().replace(/^www\./, "");
      } catch {
        return u.toLowerCase().replace(/^www\./, "");
      }
    }),
  );
  const hits: Record<string, string[]> = {};
  for (const a of articles) {
    let domain = "";
    try {
      domain = new URL(a.url).hostname.toLowerCase().replace(/^www\./, "");
    } catch {
      continue;
    }
    for (const ps of expected) {
      if (domain === ps || domain.endsWith("." + ps) || domain.endsWith(ps)) {
        (hits[ps] ??= []).push((a.title ?? "?").slice(0, 60));
      }
    }
  }
  const found = Object.keys(hits);
  const missing = [...expected].filter((d) => !(d in hits));
  if (found.length === 0) {
    return {
      check: "priority_sources",
      status: "FAIL",
      detail: `0/${expected.size} priority domains found in results`,
      data: { missing },
    };
  }
  if (missing.length > 0) {
    return {
      check: "priority_sources",
      status: "WARN",
      detail: `${found.length}/${expected.size} found (missing: ${missing.join(", ")})`,
      data: { found, missing, hits },
    };
  }
  return {
    check: "priority_sources",
    status: "PASS",
    detail: `${found.length}/${expected.size} priority domains found`,
    data: { found, hits },
  };
}

export function runQualityChecks(
  record: {
    summary: string;
    articles: Article[];
    category: string;
  },
  expectedLang: string,
  sourceMode: "reliable" | "niche",
  prioritySources?: string[],
): QualityCheck[] {
  return [
    validateLanguage(record.summary, expectedLang),
    validateDateRelevance(record.articles),
    validateSourceDiversity(record.articles, sourceMode),
    validateUndatedRatio(record.articles, record.category),
    ...(prioritySources && prioritySources.length > 0
      ? [validatePrioritySources(record.articles, prioritySources)]
      : []),
  ];
}

// ---------------------------------------------------------------------------
// Flaw detection — cross-record sanity on an audit batch.
// ---------------------------------------------------------------------------

export interface AuditRecord {
  permutation: string;
  category: string;
  source_mode: "reliable" | "niche";
  scope: string;
  queries_generated: number;
  raw_results: number;
  final_articles: number;
  articles: Article[];
  summary: string;
  processing_time_ms: number;
  error: string | null;
  quality_checks: QualityCheck[];
}

export function detectFlaws(records: AuditRecord[]): string[] {
  const flaws: string[] = [];
  const byPerm = new Map<string, AuditRecord[]>();
  for (const r of records) {
    const arr = byPerm.get(r.permutation) ?? [];
    arr.push(r);
    byPerm.set(r.permutation, arr);
  }

  for (const [perm, cats] of byPerm) {
    for (const r of cats) {
      if (r.error) {
        flaws.push(`**${perm} / ${r.category}**: Error \u2014 ${r.error}`);
      } else if (r.final_articles === 0) {
        flaws.push(
          `**${perm} / ${r.category}**: Zero articles ` +
            `(raw=${r.raw_results}, queries=${r.queries_generated})`,
        );
      } else if (r.final_articles <= 1) {
        flaws.push(
          `**${perm} / ${r.category}**: Only ${r.final_articles} article ` +
            `(raw=${r.raw_results}, queries=${r.queries_generated})`,
        );
      }
    }

    if (cats.length > 1) {
      const withResults = cats.filter((r) => r.final_articles > 0).map((r) =>
        r.category
      );
      const without = cats
        .filter((r) => r.final_articles === 0 && !r.error)
        .map((r) => r.category);
      if (withResults.length > 0 && without.length > 0) {
        flaws.push(
          `**${perm}**: Imbalanced \u2014 ${withResults.join(", ")} returned results but ` +
            `${without.join(", ")} returned nothing`,
        );
      }
    }
  }

  // 100% drop rate
  for (const r of records) {
    if (r.raw_results > 0 && r.final_articles === 0 && !r.error) {
      flaws.push(
        `**${r.permutation} / ${r.category}**: 100% drop \u2014 ` +
          `${r.raw_results} raw results all filtered out`,
      );
    }
  }

  // Quality FAILs
  for (const r of records) {
    for (const c of r.quality_checks) {
      if (c.status === "FAIL") {
        flaws.push(
          `**${r.permutation} / ${r.category}**: Quality FAIL \u2014 ${c.check}: ${c.detail}`,
        );
      }
    }
  }

  // Cross-category URL overlap
  for (const [perm, cats] of byPerm) {
    if (cats.length < 2) continue;
    const urlSets = new Map<string, Set<string>>();
    for (const r of cats) {
      const urls = new Set(r.articles.map((a) => a.url).filter(Boolean));
      urlSets.set(r.category, urls);
    }
    const names = [...urlSets.keys()];
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const a = urlSets.get(names[i])!;
        const b = urlSets.get(names[j])!;
        const overlap = [...a].filter((u) => b.has(u));
        if (overlap.length > 0) {
          flaws.push(
            `**${perm}**: URL overlap between ${names[i]} and ${names[j]} \u2014 ` +
              `${overlap.length} shared URLs`,
          );
        }
      }
    }
  }

  return flaws;
}

// ---------------------------------------------------------------------------
// Markdown report writer.
// ---------------------------------------------------------------------------

export function writeReport(
  records: AuditRecord[],
  flaws: string[],
  totalPermutations: number,
): string {
  const now = new Date().toISOString();
  const L: string[] = [];
  L.push("# Beat Scout (Pulse) Audit Results");
  L.push(`Generated: ${now}\n`);
  L.push(
    `**Searches:** ${records.length} (${totalPermutations} permutations)\n`,
  );

  L.push("## Summary Matrix\n");
  L.push("| Permutation | Category | Source Mode | Queries | Raw | Final | Time (ms) | Status |");
  L.push("|-------------|----------|-------------|---------|-----|-------|-----------|--------|");
  for (const r of records) {
    const status = r.error
      ? "ERROR"
      : r.final_articles === 0
      ? "FAIL"
      : r.final_articles <= 1
      ? `WARN (${r.final_articles})`
      : "OK";
    L.push(
      `| ${r.permutation} | ${r.category} | ${r.source_mode} | ${r.queries_generated} | ` +
        `${r.raw_results} | ${r.final_articles} | ${r.processing_time_ms} | ${status} |`,
    );
  }

  L.push("\n## Flaws Detected\n");
  if (flaws.length === 0) L.push("_None._\n");
  else for (const f of flaws) L.push(`- ${f}`);

  L.push("\n## Quality Validation\n");
  L.push("| Permutation | Category | Language | Date Relevance | Source Diversity | Undated Ratio | Priority Sources |");
  L.push("|-------------|----------|----------|----------------|------------------|---------------|------------------|");
  for (const r of records) {
    const by: Record<string, QualityCheck> = {};
    for (const c of r.quality_checks) by[c.check] = c;
    const cell = (k: string) => {
      const c = by[k];
      return c ? `${c.status} (${c.detail})` : "skip";
    };
    L.push(
      `| ${r.permutation} | ${r.category} | ${cell("language")} | ` +
        `${cell("date_relevance")} | ${cell("source_diversity")} | ${cell("undated_ratio")} | ` +
        `${cell("priority_sources")} |`,
    );
  }

  L.push("\n## Detailed Results\n");
  for (const r of records) {
    L.push(`### ${r.permutation} / ${r.category}\n`);
    L.push(`- **Source mode:** ${r.source_mode}`);
    L.push(`- **Scope:** ${r.scope}`);
    L.push(`- **Queries:** ${r.queries_generated}`);
    L.push(`- **Raw results:** ${r.raw_results}`);
    L.push(`- **Final articles:** ${r.final_articles}`);
    L.push(`- **Time:** ${r.processing_time_ms}ms`);
    if (r.error) L.push(`- **Error:** \`${r.error}\``);
    if (r.articles.length > 0) {
      L.push(`\n**Articles (${r.articles.length}):**`);
      r.articles.forEach((a, i) => {
        L.push(`${i + 1}. **${a.title}**`);
        L.push(`   - Source: ${a.source ?? "?"} | Published: ${a.date ?? "undated"}`);
        L.push(`   - URL: ${a.url}`);
      });
    }
    if (r.summary) L.push(`\n**Summary:** ${r.summary}`);
    L.push("");
  }

  return L.join("\n");
}
