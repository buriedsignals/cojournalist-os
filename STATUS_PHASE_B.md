# Phase B — Subpage-Follow Status (2026-04-23)

## What's done

| # | Item | File | Status |
|---|------|------|--------|
| 1 | Widen `ScrapeResult` to return `rawHtml` | `supabase/functions/_shared/firecrawl.ts` | Done |
| 2 | Add `isListingPage` to extraction schema + system prompt | `supabase/functions/_shared/atomic_extract.ts` | Done |
| 3 | Phase B wiring in scout runner | `supabase/functions/scout-web-execute/index.ts` | Done |
| 4 | Benchmark script created | `scripts/benchmark-subpage-follow.ts` | Done |
| 5 | Typecheck (`deno check`) on all files | — | **Passes** |
| 6 | Extract `filterSubpageUrls` into pure-function module | `supabase/functions/_shared/subpage-filter.ts` | Done |
| 7 | Replace inline filter in scout runner with `filterSubpageUrls()` | `supabase/functions/scout-web-execute/index.ts` | Done |
| 8 | 8-case Deno test suite for `filterSubpageUrls` | `supabase/functions/_shared/subpage_filter_test.ts` | Done |
| 9 | Doc update: Step 6b + shared-modules table | `docs/supabase/edge-functions.md` | Done |

## Benchmark result (2026-04-23, final)

Ran against `https://www.baselland.ch/politik-und-behorden/regierungsrat/medienmitteilungen/`.
- **29 units from 10 distinct subpages** — all assertions pass ✓
- Phase B triggered correctly: index flagged as listing page, 10 subpages followed, CAP=10 respected
- Wall time: ~80s (1 index + 10 subpage Firecrawl scrapes + Gemini extractions)

## Remaining

- [ ] Merge the `refactor/subpage-filter-helper` PR (#89) after CI passes — ready for review

## Reference

- Labs commit: `efe6989` on `feat/dorfkoenig-subpage-follow` in `wepublish/labs`
- Labs filter: `src/dorfkoenig/supabase/functions/_shared/subpage-filter.ts`
- Labs tests: `src/dorfkoenig/supabase/functions/_tests/shared/subpage_filter_test.ts`
- Portable spec: `src/dorfkoenig/specs/SUBPAGE_FOLLOW.md`

## Constraints (unchanged from plan)
- No new database migration (dedup uses existing `information_units.source_url`)
- CAP = 10 subpages, single-hop only
- No change to extraction prompt output schema
- `--no-verify-jwt` already set on all Edge Functions
