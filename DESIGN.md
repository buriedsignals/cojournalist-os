# coJournalist — Design System

> Reference spec for the visual language of coJournalist. Source of truth for
> tokens, typography, spacing, material rules, and component recipes.
>
> **Who reads this:** any human or agent touching the UI. Update this file
> when you change a token or introduce a new recipe.

---

## 1. Visual DNA

coJournalist is a **journalism tool**, not a SaaS product. The interface should read the way a well-set news page reads: warm paper, firm hierarchy, confident type, nothing decorative that doesn't carry meaning.

- **Surface:** warm cream paper. Never pure white.
- **Grid:** strong, generous, editorial. Prefer 2–3 visual columns of hierarchy over a sea of equal-weight cards.
- **Edges:** **sharp**. Everything is `radius: 0`. Pills are the only exception (they are tags, not panels).
- **Texture:** hairline borders do the work, not shadows. One shadow allowed for modal elevation.
- **Type:** serif display for authority, sans for operation, mono uppercase for labels — the investigative-zine combination.
- **Color:** plum purple as brand, warm ochre as counterpoint, ink-near-black for text. No cold grays.
- **Motion:** fast, small, color-level. Nothing bounces.

**The palette in one sentence:** plum and ochre, on warm cream, with ink text.

---

## 2. Color

All colors are declared once as CSS custom properties on `:root` in `frontend/src/app.css`. Components reference them via `var(--color-*)` — never hardcode hex.

### 2.1 Tokens

| Token | Hex | Role |
|---|---|---|
| `--color-bg` | `#F5EFE3` | Page background (warm cream) |
| `--color-surface` | `#EBE4D4` | Elevated surfaces, inset panels (stone) |
| `--color-surface-alt` | `#F9F4E9` | Higher-contrast inset — cards lifting off cream |
| `--color-primary` | `#6B3FA0` | Primary brand (plum purple) — CTAs, active states, headline accents |
| `--color-primary-soft` | `#E7DBF1` | Primary wash — hover backgrounds, active rows, icon tiles |
| `--color-primary-deep` | `#4E2C78` | Pressed / high-contrast primary |
| `--color-secondary` | `#C77A1D` | Secondary accent (warm ochre) — eyebrows, badges, counters |
| `--color-secondary-soft` | `#F4E7CF` | Ochre wash |
| `--color-ink` | `#201A2A` | Primary text, dark-inverted surfaces (hero CTAs) |
| `--color-ink-muted` | `#6E6380` | Secondary text |
| `--color-ink-subtle` | `#9A8FAA` | Tertiary text, disabled, placeholder |
| `--color-border` | `#D9D0BE` | Hairline borders, dividers |
| `--color-border-strong` | `#B8AC93` | Emphasis borders |
| `--color-success` | `#2F8F5F` | Success states (retinted green to sit on cream) |
| `--color-warning` | `#B87A1A` | Warning states (near secondary — use sparingly) |
| `--color-error` | `#B33E2E` | Error states (editorial red, not alert red) |
| `--color-info` | `#3F5EA6` | Neutral info |

### 2.2 Legacy aliases

During the progressive sweep, `app.css` keeps legacy var names aliased to the new tokens:

```css
--color-bg-primary:    var(--color-bg);
--color-bg-secondary:  var(--color-surface-alt);
--color-bg-tertiary:   var(--color-surface);
--color-text-primary:  var(--color-ink);
--color-text-secondary:var(--color-ink-muted);
--color-text-tertiary: var(--color-ink-subtle);
--color-border:        var(--color-border);
--color-border-hover:  var(--color-border-strong);
```

Unconverted components keep working; converted components use the new names.

### 2.3 Usage rules

- **Primary (`--color-primary`)** — CTAs, active nav items, headline accent word, scout-type icon tiles, selected filters.
- **Secondary (`--color-secondary`)** — eyebrow labels, badges (BETA, NEW, REVIEW), unit counts, "needs review" pill, newsletter signup CTA.
- **Never** place primary on secondary or vice versa at full saturation — always go through a soft variant or ink.
- **Text hierarchy:** ink → ink-muted → ink-subtle. Don't invent new grays.
- **Status colors** live only on status surfaces (toast, error state, success flash). Don't decorate with them.

### 2.4 Gradient border shell (hero cards only)

Reserved for the single most-important surface on the landing page (the auth card). Emulates the "premium paper edge" treatment.

```html
<div class="shell">
  <div class="surface">…</div>
</div>

<style>
  .shell {
    padding: 1px;
    background: linear-gradient(
      to bottom right,
      rgba(107, 63, 160, 0.45),   /* plum */
      var(--color-border) 45%,
      transparent 100%
    );
  }
  .surface {
    background: var(--color-surface-alt);
  }
</style>
```

One instance per page, maximum.

---

## 3. Typography

Fonts load via `@import` in `frontend/src/app.css`.

- **Display** — `Crimson Pro` (serif, 600/700). Headlines, page titles, card titles.
- **Body / UI** — `Inter` (sans, 300/400/500/600). Paragraphs, controls, navigation, descriptions.
- **Mono / Label** — `JetBrains Mono` (300/400/500). **Uppercase, `letter-spacing: 0.1em`.** Eyebrows, badges, button labels on landing, code, data chips.

### 3.1 Scale

| Role | Family | Size / Leading | Weight | Tracking |
|---|---|---|---|---|
| Display-XL (hero) | Crimson Pro | `56 / 60` | 600 | `-0.03em` |
| Display-L (H1) | Crimson Pro | `40 / 44` | 600 | `-0.02em` |
| H2 | Crimson Pro | `28 / 32` | 600 | `-0.015em` |
| H3 | Crimson Pro | `22 / 28` | 600 | `-0.01em` |
| Body-L | Inter | `18 / 28` | 300 | `0` |
| Body (default) | Inter | `15 / 24` | 400 | `0` |
| Body-S | Inter | `13 / 20` | 400 | `0` |
| UI label | Inter | `13 / 18` | 500 | `0` |
| Button label (landing) | JetBrains Mono | `12 / 16` | 500 | `0.1em`, UPPERCASE |
| Button label (dashboard) | Inter | `13 / 16` | 600 | `0.01em` |
| Eyebrow | JetBrains Mono | `11 / 16` | 500 | `0.1em`, UPPERCASE |
| Data chip | JetBrains Mono | `11 / 14` | 400 | `0.08em`, UPPERCASE |
| Code | JetBrains Mono | `13 / 20` | 400 | `0` |

### 3.2 Rules

- **Don't** mix Crimson Pro italic with JetBrains Mono in the same block.
- **Don't** stretch Crimson Pro below 18px — it loses its authority.
- **Do** use JetBrains Mono tracked-uppercase for *structural* labels (section headers, categories, badges). Never for sentences.
- **Do** set Inter at weight 300 for long-form body on landing; weight 400 in dense UI.
- **Do** prefer numerical weight values (300, 400, 500, 600) over keywords.

---

## 4. Spacing

4px base unit. Scale: **`4, 8, 12, 16, 20, 24, 32, 48, 64, 96`**.

Tokens in `app.css`:

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-12: 48px;
--space-16: 64px;
--space-24: 96px;
```

- **Section padding (landing):** `96px` vertical on desktop, `48px` on mobile.
- **Card padding:** `24px` default, `32px` for hero-tier.
- **Stack gap inside a card:** `12px` between header/body, `8px` between body items.
- **Grid gutters:** `24px` desktop, `16px` mobile.

---

## 5. Material

### 5.1 Radius

Everything is `radius: 0`. Full stop.

- Pills (`--radius-pill: 9999px`) are the exception, used for tags and counts only.
- No other radius token exists.

### 5.2 Borders

- **Hairline:** `1px solid var(--color-border)` — default on cards, inputs, dividers.
- **Strong:** `1px solid var(--color-border-strong)` — active inputs, hovered cards.
- **Primary:** `1px solid var(--color-primary)` — focused or selected state.
- **Ink:** `1px solid var(--color-ink)` — dark-surface buttons, emphasis cards.

### 5.3 Shadows

Used sparsely. Two approved recipes:

```css
/* Modal elevation */
--shadow-modal: 0 24px 48px -16px rgba(32, 26, 42, 0.24);

/* Card hover lift (dashboard only) */
--shadow-card-hover: 0 2px 8px -4px rgba(32, 26, 42, 0.12);
```

Landing page uses zero shadows. Only hairlines.

### 5.4 Focus

```css
outline: 2px solid var(--color-primary);
outline-offset: 2px;
```

Always visible, never `outline: none` without a replacement.

---

## 6. Motion

- **Timings:** `150ms` for color/opacity, `300ms` for position/size, `2000ms` for ambient loops.
- **Easings:** `ease` for idle, `cubic-bezier(0.4, 0, 0.2, 1)` for hover, `cubic-bezier(0.2, 0, 0.2, 1)` for exit.
- **Hover patterns:** color change, stroke change, underline draw. No translations, no scale.
- **Reveal:** IntersectionObserver fade-in on landing section cards is OK (300ms, opacity + 8px y-offset).
- **No bouncing**, no elastic, no wobble, no confetti.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
```

---

## 7. Icons

- Library: **`lucide-svelte`** (already installed — do not swap).
- Default size: **18px** in dashboard chrome, **20px** in content, **16px** in dense controls.
- Default stroke: **1.5**.
- Color: inherit from text color (`currentColor`). Never set icon color in isolation.

Feature/illustration icons on landing may be inline SVGs (kept from the current build) — but new icons should be Lucide.

---

## 8. Component Recipes

### 8.1 Button

Three variants. All `radius: 0`, transition `150ms ease`.

**Primary** — plum fill, cream text, mono uppercase label on landing, Inter on dashboard.

```css
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 24px;
  background: var(--color-primary);
  color: var(--color-bg);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  border: 1px solid var(--color-primary);
  cursor: pointer;
}
.btn-primary:hover  { background: var(--color-primary-deep); border-color: var(--color-primary-deep); }
.btn-primary:active { transform: none; background: var(--color-primary-deep); }
```

**Secondary** — cream fill, hairline border, ink text.

```css
.btn-secondary {
  background: var(--color-surface-alt);
  color: var(--color-ink);
  border: 1px solid var(--color-border);
  padding: 14px 24px;
  /* same type + layout as primary, but Inter for dashboard */
}
.btn-secondary:hover { border-color: var(--color-border-strong); }
```

**Ghost** — transparent, ink text, underlines on hover.

```css
.btn-ghost {
  background: transparent;
  color: var(--color-primary);
  padding: 8px 0;
  border: 0;
}
.btn-ghost:hover { text-decoration: underline; text-underline-offset: 4px; }
```

**Dashboard buttons** use Inter 600 label at 13/16 `+0.01em` instead of mono — less shouty during extended use.

### 8.2 Card

```css
.card {
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  padding: var(--space-6);
}
.card--hero      { padding: var(--space-8); }
.card--interactive:hover { border-color: var(--color-border-strong); }
.card--selected  { border-color: var(--color-primary); background: var(--color-primary-soft); }
```

### 8.3 Eyebrow label

Use on every section header and in-card category marker.

```css
.eyebrow {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 16px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.eyebrow--primary   { color: var(--color-primary); }
.eyebrow--secondary { color: var(--color-secondary); }
```

### 8.4 Chip / Pill

Only true rounded surfaces in the system.

```css
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  color: var(--color-ink-muted);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
}
.chip--primary   { background: var(--color-primary-soft);   color: var(--color-primary-deep); }
.chip--secondary { background: var(--color-secondary-soft); color: var(--color-secondary); }
```

### 8.5 Input

```css
.form-input {
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  color: var(--color-ink);
  font-family: var(--font-body);
  font-size: 15px;
  padding: 12px 14px;
  border-radius: 0;
}
.form-input:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}
```

### 8.6 Modal

```css
.modal-backdrop {
  background: rgba(32, 26, 42, 0.65);
}
.modal-panel {
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-modal);
  /* no radius */
}
.modal-header {
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-6) var(--space-8);
}
```

### 8.7 Section header (landing)

```
┌──────────────────────────────────────────┐
│ HOW IT WORKS                             │  ← eyebrow (mono, ochre)
│                                          │
│ Monitor the noise.                       │  ← Crimson Pro 48/52
│ Surface leads.                           │    plum on active phrase
│                                          │
│ Connect your AI agent to scouts that     │  ← Inter 300 18/28
│ watch pages, social, and councils.       │
│                                          │
│ [GET STARTED] [VIEW DOCS ↗]              │  ← mono uppercase buttons
└──────────────────────────────────────────┘
```

---

## 9. Do / Don't

- ✅ Use eyebrow labels above every section and inside cards.
- ✅ Let hairlines do the work. One shadow per screen, max.
- ✅ Keep plum + ochre far apart — at least one neutral surface between them.
- ✅ Favor Inter 300 on landing prose. It breathes.
- ❌ No pure white (`#fff`) anywhere. Default surface is `--color-surface-alt`.
- ❌ No gradient fills on text except the auth card's gradient border shell.
- ❌ No rounded buttons, cards, or panels. Pills only.
- ❌ No cold grays (`#9ca3af`, etc.). Use ink tokens.
- ❌ No decorative iconography. Every icon must carry meaning.
- ❌ Don't mix Crimson Pro italic with JetBrains Mono in the same block.

---

## 10. File Map

| Concern | File |
|---|---|
| Tokens, base styles, utility classes | `frontend/src/app.css` |
| Font preload hints | `frontend/src/app.html` |
| Landing page | `frontend/src/routes/login/+page.svelte` |
| Pricing page | `frontend/src/routes/pricing/+page.svelte` |
| Dashboard shell (topnav inline) | `frontend/src/routes/+page.svelte` |
| Sidebar | `frontend/src/lib/components/sidebars/UnifiedSidebar.svelte` |
| Workspace components | `frontend/src/lib/components/workspace/*` |
| UI primitives | `frontend/src/lib/components/ui/*` |
| Modals | `frontend/src/lib/components/modals/*` |
| News views | `frontend/src/lib/components/news/*` |
| Feed components | `frontend/src/lib/components/feed/*` |

---

## 11. Changelog

| Date | Change |
|---|---|
| 2026-04-21 | Initial spec. Plum + ochre on cream. Crimson Pro × Inter × JetBrains Mono. Radius 0. |
