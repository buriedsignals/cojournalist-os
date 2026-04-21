# Export Service

Draft export to Markdown files.

## Overview

After generating an export in the Feed panel, users can download the draft as a Markdown file client-side. No backend call is made for the download; draft generation itself is billed separately.

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `ExportSlideOver.svelte` | `frontend/src/lib/components/feed/` | Export slide-over UI |
| `FeedView.svelte` | `frontend/src/lib/components/feed/` | Feed orchestration + export trigger |

## Markdown Export

Client-side only. The frontend builds a `.md` file from the draft object and triggers a browser download. No backend call, no credits charged at export time.

## Related Docs

- `features/feed.md` — Feed panel and export generation from information units
- Credit costs: see `supabase/functions/_shared/credits.ts` (`feed_export` → 1 credit, charged at draft generation)
