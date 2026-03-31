# Frontend (SvelteKit)

SvelteKit static SPA with TailwindCSS. Built and served by the FastAPI backend via Docker.

**Node version:** Must use Node 22 LTS (see `.nvmrc`). Run `nvm use` before any `npm install`. Mismatched npm versions produce lock files that break the Docker build on Render.

## Structure

```
frontend/src/
├── app.html             # HTML shell
├── app.css              # Global styles (Tailwind)
├── routes/              # SvelteKit pages
│   ├── +layout.svelte   # Root layout with auth
│   ├── +page.svelte     # Home/dashboard
│   ├── pricing/         # Pricing page
│   └── ...
└── lib/
    ├── api-client.ts    # Typed API client
    ├── types.ts         # TypeScript types
    ├── components/      # UI components
    │   ├── ui/          # Base components (buttons, inputs)
    │   ├── modals/      # Modal dialogs
    │   ├── panels/      # Side panels
    │   ├── views/       # Main view components
    │   ├── news/        # News-related components
    │   └── sidebars/    # Sidebar components
    ├── stores/          # Svelte stores (state)
    └── utils/           # Helper functions
        └── tooltip.ts   # Custom tooltip action for Svelte
```

## Key Components

| Directory | Purpose |
|-----------|---------|
| `components/ui/` | Reusable UI primitives (TopicChips, LocationAutocomplete, etc.) |
| `components/modals/` | Scout creation, settings, scheduling, UpgradeModal |
| `components/views/` | Main content views |
| `components/news/` | News article display (SmartScoutView, SocialScoutView) |

## State Management

Svelte stores in `lib/stores/`:
- `auth.ts` - MuckRock OAuth session state
- `extraction-state.ts` - Data extraction job state tracking
- `feed.ts` - Feed panel state (units, export)
- `location.ts` - Shared location state (used by Pulse, WebScout)
- `notifications.ts` - In-app notification state
- `onboarding-tour.ts` - Onboarding tour progress
- `pulse.ts` - Location Scout / Beat Scout (type `pulse`) shared state
- `recent-locations.ts` - Recently used locations cache
- `sidebar-nav.ts` - Sidebar navigation state
- `feed-refresh.ts` - Feed refresh trigger state

## API Client

`lib/api-client.ts` - Typed wrapper for backend API calls. Handles:
- Session cookie auth
- Error handling
- Type safety

**Key Methods:**
- `searchPulse()` - Smart Scout search with optional criteria (POST /pulse/search)

## Environment Variables (Build-time)

These must be set during Docker build:
- `PUBLIC_MAPTILER_API_KEY` - Geocoding for location autocomplete

## i18n (Paraglide)

Internationalization uses [Paraglide JS](https://inlang.com/m/gerre34r) with inlang message format.

**Message files:** `messages/{languageTag}.json` (e.g. `messages/en.json`)

**Generated output:** `src/lib/paraglide/` (gitignored, must be compiled)

**Adding a new i18n key:**

1. Add the key to `messages/en.json` (camelCase after prefix, e.g. `"feed_noLocations": "No locations")`)
2. **Add the same key to ALL 12 language files** — `da.json`, `de.json`, `es.json`, `fi.json`, `fr.json`, `it.json`, `nl.json`, `no.json`, `pl.json`, `pt.json`, `sv.json` (use English as fallback)
3. Recompile paraglide: `npm run paraglide:compile`
4. Import and use: `import * as m from '$lib/paraglide/messages'` → `m.feed_noLocations()`
5. **Verify:** Run `npm run check` — it will fail with "Property does not exist" if any key is missing

**CRITICAL: Always use `npm run paraglide:compile` (or the full command below).** Do NOT run the bare `npx @inlang/paraglide-js compile --project ./project.inlang` — it omits the `--outdir` and `--strategy` flags, compiling to the wrong directory (`src/paraglide/` instead of `src/lib/paraglide/`).

```bash
# Correct command (what npm run paraglide:compile runs):
paraglide-js compile --project ./project.inlang --outdir ./src/lib/paraglide --strategy localStorage globalVariable baseLocale

# If generated files seem stale, delete and recompile:
rm -rf src/lib/paraglide && npm run paraglide:compile
```

**How it works internally:**
- Each message key becomes a separate `.js` file (e.g. `feed_noLocations` → `feed_nolocations1.js`)
- All are re-exported from `messages/_index.js` with original casing via string alias exports
- `svelte-check` will fail with "Property does not exist" errors if paraglide wasn't recompiled after adding keys

**COMMON BUG — keys added to `en.json` but not other language files:**
Paraglide compiles successfully even if non-English files are missing keys (it falls back to English at runtime). But `svelte-check` validates against the generated TypeScript types from `en.json`. If you add a key to `en.json`, compile, and use it in a component — it works locally. But if the CI runs `npm run check` on a branch where the key was never added to `en.json` in the first place (e.g. keys referenced in code but never committed to message files), lint fails. **Always grep your `.svelte` files for new `m.*()` calls and confirm every key exists in all 12 message files before committing.**

## Pre-Commit Checklist

Before committing frontend changes, run:

```bash
cd frontend
npm run paraglide:compile   # Regenerate from message files
npm run check               # svelte-check (catches missing keys, type errors)
npm test                    # Vitest (unit tests)
```

If `npm run check` fails with "Property does not exist on type 'typeof messages'", a `m.*()` key is missing from `messages/en.json`. Add it to all 12 language files, recompile, and re-run.

## Build

```bash
npm run build  # Outputs to /build (static files)
```

Static files are copied into the FastAPI Docker image at `backend/app/frontend_client/`.
