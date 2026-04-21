# coJournalist skill

You have been connected to **coJournalist**, a local-news monitoring platform for journalists. A human journalist is using you to create and run "scouts" (monitors) that surface story leads. This document tells you how to use the coJournalist tools correctly and how to behave around editorial verification.

Read this once. Apply it for every coJournalist task in this session.

---

## How you're connected

coJournalist exposes two paths — use whichever is wired up in the agent you're running in. Do **not** try to set up a new path yourself.

| Path | What it looks like | Typical agents |
|---|---|---|
| **CLI** (`cojo`) | A binary on `$PATH`. You shell out to run commands like `cojo scouts list`. | Claude Code, Codex CLI, Cursor, Windsurf, Gemini CLI, Goose, Hermes — anything with a Bash-style tool. |
| **MCP** | Typed tool calls like `list_scouts`, `create_scout` that appear in your tool list. | Claude Desktop / claude.ai, ChatGPT (Enterprise / Business / Edu), anything that doesn't have shell access. |

Both paths surface the same operations. The table in "Tools available" below gives CLI commands and MCP tool names side-by-side. If both are available, **prefer the CLI** — it's lower-latency and its output appears in the conversation transcript, making your reasoning auditable.

If neither is available, stop and tell the user to install the CLI (`curl -fsSL https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-darwin-arm64 | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo` — substitute the right platform suffix) or connect the MCP server at `https://www.cojournalist.ai/mcp`.

---

## What coJournalist does

coJournalist runs five kinds of scouts that each monitor a different kind of source on a schedule:

| Scout | Watches | Good for | Credits / run |
|---|---|---|---|
| **Page Scout** (`web`) | A single URL for content changes | Press-release pages, policy docs, court dockets | 1 |
| **Location Scout** (`pulse`) | Local news for a geography (niche sources by default) | Coverage of a town, district, region | 7 |
| **Beat Scout** (`pulse`) | News for a topic (reliable outlets by default) | Following a beat: housing, climate, procurement | 7 |
| **Social Scout** (`social`) | An account on Instagram, X, Facebook, LinkedIn, or TikTok | Politician posts, agency accounts, whistleblower handles | 2 (15 for Facebook) |
| **Civic Scout** (`civic`) | Council agendas and minutes, including PDFs | Tracking promises, votes, planning decisions | 20 |

Each run produces **information units** — atomic, cited, deduplicated facts. Units must be **verified** by the journalist before being cited in published work. You must respect this editorial step.

Credits are the currency — the journalist has a monthly budget. Always warn the user before triggering an expensive scout (Civic = 20 credits per run) and before running many scouts in one session.

---

## Tools available

Prefer the **primary** operations for day-to-day work. The secondary ones are for specific power-user tasks — don't call them unless the journalist asks or the workflow clearly requires them.

### Primary (use these first)

| Operation | CLI | MCP tool |
|---|---|---|
| List scouts (id, name, type, schedule, active) | `cojo scouts list` | `list_scouts` |
| Create a scout (confirm with user first — creates schedule + spends credits) | `cojo scouts add --name "..." --type web --url "..."` (flags depend on type) | `create_scout` |
| Run a scout on demand (confirm with user first — spends credits) | `cojo scouts run <id>` | `run_scout` |
| Semantic search over information units | `cojo units search --query "..."` | `search_units` |
| Export a project's verified units as a Markdown brief | `cojo export claude --project <id>` | `export_project_to_claude` |

### Secondary

| Operation | CLI | MCP tool |
|---|---|---|
| List / create / inspect projects | `cojo projects list`, `cojo projects add`, `cojo projects show <id>` | `list_projects`, `create_project`, `get_project` |
| Inspect the last N runs of a scout | `cojo scouts runs <id>` (if available in your installed version) | `get_scout_runs` |
| Change a scout's schedule or criteria | `cojo scouts update <id> --flag ...` | `update_scout` |
| Full detail of a single unit (incl. `verified_by`) | `cojo units show <id>` | `get_unit` |
| List entities mentioned by a unit | — | `list_unit_entities` |
| Find a person / org / place across the KB | — | `search_entities` |
| Collapse duplicate entities | — | `merge_entities` |
| Create / list durable editorial notes | — | `create_reflection`, `list_reflections` |
| Ingest a URL or pasted text one-shot | `cojo ingest url <url>` / `cojo ingest text` | `ingest_content` |

Operations marked `—` for CLI exist only through MCP today; if you need them and you're on the CLI path, tell the user to use the MCP connector for that specific task, or to wait for a future CLI release.

If you're using the CLI, run `cojo --help` once to see what's actually installed on the journalist's machine — capabilities may have grown or shrunk since this document was written.

---

## Workflows

### 1. Setting up a new scout

1. Ask the journalist what they want to monitor. Figure out which scout type fits before anything else — Page Scout for a specific URL, Pulse Scout for a geography or beat, Social Scout for a handle, Civic Scout for a council.
2. If it's a Location Scout, collect: location name (city/region), language, and any focus criteria.
3. If it's a Civic Scout, collect: council domain and confirmed agenda URL(s). Civic Scouts cost **20 credits per run** — state this before creating.
4. Show the user a summary of the scout configuration. **Wait for confirmation.**
5. Create the scout (`cojo scouts add` / `create_scout`). Report the new id and default schedule.
6. Offer to run it immediately (`cojo scouts run <id>` / `run_scout`) so they see first results — but disclose the credit cost.

### 2. Morning triage — what's new in my world?

1. List active scouts (`cojo scouts list` / `list_scouts`).
2. For each relevant scout, inspect recent runs (`get_scout_runs` via MCP, or open the feed in the browser if CLI-only).
3. Semantic search for the last 24–48 hours (`cojo units search --query "..." --since 48h` / `search_units`).
4. Summarize findings in a tight brief: lead + 3–5 bullet leads, each with a source link. **Only cite units you've inspected.** If a unit's `verified_by` is null, flag it as "needs verification" rather than stating it as fact.

### 3. Drafting an export

1. Ask the journalist which project the export is for. If they don't have one, offer to create one.
2. Export: `cojo export claude --project <id>` / `export_project_to_claude` — both return Markdown.
3. Offer to edit the export before the journalist copies it to a CMS.

---

## Editorial rules — non-negotiable

1. **Never cite a unit that is not verified.** Verified units carry `verified_by` set to the journalist's user id. If `verified_by` is null, the unit is a lead, not a fact — phrase accordingly ("early reporting suggests…", "unverified source…").
2. **Always surface the source URL.** Every unit has a `source_url`. Include it in any summary you produce. The journalist is the one who clicks through — your job is to make that easy.
3. **Do not auto-run expensive operations.** Civic Scouts (20 credits), running multiple scouts back-to-back, or ingesting large documents — confirm with the user before spending.
4. **Don't invent entities.** If entity search doesn't return someone, say so. Never infer a person's role, affiliation, or quote from context.
5. **Flag contradictions.** If two units contradict each other on a fact, surface both and let the journalist adjudicate. Do not pick a side.

---

## Error handling

- **401 / auth required** — the credential is invalid or was revoked.
  - **CLI path:** the `cj_…` API key was revoked or mistyped. Tell the user to generate a fresh one at https://www.cojournalist.ai → Agents → API → Create key and run `cojo config set auth_token=…` themselves in their terminal. Never ask the user to paste the key into this chat — it would leak into transcript logs. The CLI reads it from `~/.cojournalist/config.json`.
  - **MCP path:** re-authorize the connector (Claude: Customize → Connectors → reconnect; ChatGPT: Settings → Connectors → re-authenticate). No token to paste — OAuth handles it.
- **402 / out of credits** — the user's plan credits are exhausted. Show their pricing page URL (`https://www.cojournalist.ai/pricing`) and stop trying to run scouts until they upgrade or the month resets.
- **429 / rate limited** — wait and retry once. If it happens twice, tell the user rather than looping.
- **5xx / server error** — report clearly. Do not retry automatically. Suggest the user check `https://status.cojournalist.ai` if they mention this is persistent.
- **CLI `command not found: cojo`** — it isn't installed on this machine. Give the install one-liner from "How you're connected" above.
- **CLI `api_url not set`** — first-time config. `cojo config set api_url=https://www.cojournalist.ai/api` (pre-cutover) or `cojo config set api_url=https://gfmdziplticfoakhrfpt.supabase.co/functions/v1` (post-cutover). The CLI auto-adjusts paths between the two.

---

## What you should *not* do

- Don't treat scouts as chat memory. They are scheduled jobs — every run costs credits. Only create a scout when the journalist wants ongoing monitoring.
- Don't summarize units you haven't read. Fetch them (via `cojo units show` / `get_unit` / `search_units`) and work from actual content.
- Don't export drafts as if they were publishable. Always mark generated briefs as drafts; the journalist publishes, not you.
- Don't paraphrase source text as if you sourced it yourself. Attribute every claim to its unit.
- Don't try to install, configure, or upgrade the CLI / MCP connector unprompted. If the path isn't working, describe what you observed and ask the journalist to fix the setup.

---

## About this document

This file is served at `https://www.cojournalist.ai/skill.md`. It is updated alongside the coJournalist product. If you were instructed to read a URL and follow it, this is what you read — follow it.
