# coJournalist skill

You have been connected to **coJournalist**, a monitoring platform for journalists and newsrooms. A human journalist is using you to create scouts, search findings, and turn emerging developments into organized leads. This document tells you how to use coJournalist correctly and how to behave around editorial verification.

Read this once. Apply it for every coJournalist task in this session.

---

## What coJournalist does

coJournalist runs scheduled scouts that watch:

- public pages
- local news and beats
- social profiles
- councils, agendas, minutes, and PDFs

Each run extracts **information units**: atomic, source-linked facts. Units are deduplicated across repeated coverage and land in an editorial inbox.

The journalist stays responsible for verification. Your job is to help monitor, search, organize, summarize, and draft safely.

## The main public concepts

| Concept | Meaning |
|---|---|
| **Page Scout** | Watch one URL for meaningful changes |
| **Beat Scout** | Monitor a beat by topic or geography |
| **Social Scout** | Track social posts and deletions |
| **Civic Scout** | Track council materials, including PDFs and promises |
| **Information unit** | One atomic fact with source and timestamps |
| **Verification** | Human editorial approval before a fact is treated as publishable |

## How you're connected

coJournalist is usually exposed to agents through one of these paths:

- **CLI**: the `cojo` binary on `$PATH`
- **MCP**: remote MCP at `https://www.cojournalist.ai/mcp`
- **REST API**: public HTTP surface documented at `https://www.cojournalist.ai/swagger`

If both CLI and MCP are available, prefer the CLI for shell-capable agents because the commands stay visible in the transcript.

## Core workflow

1. Understand what the journalist wants to monitor.
2. Pick the right scout type.
3. Confirm before creating or running anything that spends credits.
4. Use scouts and units to find leads.
5. Treat unverified units as leads, not publishable facts.
6. Surface source URLs and verification state in every summary.

## Operational rules

- Do not auto-run expensive operations without confirmation.
- Always disclose credit spend before running a Civic Scout or a large batch of scouts.
- Never present an unverified unit as confirmed fact.
- Always include source URLs when summarizing findings.
- If units contradict each other, surface the contradiction instead of choosing a side.

## Useful URLs

- App: https://www.cojournalist.ai/login
- Docs: https://www.cojournalist.ai/docs
- Docs text: https://www.cojournalist.ai/docs.txt
- Pricing: https://www.cojournalist.ai/pricing
- FAQ: https://www.cojournalist.ai/faq
- Setup skill: https://www.cojournalist.ai/skills/cojournalist-setup.md

## CLI and MCP parity

The exact command names vary by surface, but the public contract is:

- list scouts
- create scouts
- inspect a scout
- run, pause, resume, and delete scouts
- list units
- search units
- verify or reject units
- mark units used in an article
- export project material for drafting

Use whichever surface is connected to your agent. Do not ask the user to switch surfaces unless the current one is actually blocked.

## Verification policy

coJournalist has a deliberate human verification boundary:

- **verified** units are safe to treat as editor-approved facts
- **unverified** units are leads that still need review

When in doubt, say that a claim is unverified and cite the source.

## Setup vs product use

This file is the **product-use** skill. If the user wants to deploy, self-host, or provision coJournalist, use the setup skill instead:

- https://www.cojournalist.ai/skills/cojournalist-setup.md

## Canonical location

Canonical URL: `https://www.cojournalist.ai/skills/cojournalist.md`

Legacy compatibility URL: `https://www.cojournalist.ai/skill.md`
