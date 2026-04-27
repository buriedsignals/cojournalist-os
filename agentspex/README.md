# AgentSPEX — Agent Specification & Execution Language

AgentSPEX is a declarative YAML format for defining journalist agent
workflows in coJournalist. Instead of writing Python code to wire up new
monitoring or analysis pipelines, you describe the agent as a sequence of
steps that reference tools — and the dispatch layer handles execution.

## Quick start

1. Copy an existing agent YAML from `agents/` as a template
2. Edit the metadata, inputs, steps, and MCP bindings
3. Place the file in `agentspex/agents/`
4. The dispatcher auto-discovers it on next load

## File structure

```
agentspex/
├── agents/
│   ├── monitor.yaml      # Monitor beat-agent — watches for new content
│   └── summarize.yaml    # Summarize beat-agent — produces editorial briefs
└── README.md             # This file
```

## YAML schema reference

Every agent file follows this structure:

```yaml
apiVersion: agentspex/v1        # Required, always "agentspex/v1"
kind: AgentWorkflow             # Required, always "AgentWorkflow"

metadata:
  name: my-agent                # Unique identifier (used for dispatch)
  description: What this agent does
  type: monitor                 # monitor | summarize | investigate | extract
  version: "0.1.0"
  author: Your Name
  tags:                         # Scout types this agent handles
    - beat
    - web

spec:
  inputs:                       # What the agent needs to run
    - name: criteria
      type: string
      required: true
      description: What to look for

  steps:                        # Sequential workflow steps
    - id: search                # Unique within this agent
      tool: firecrawl/search    # namespace/tool_name
      description: Search for content
      params:
        query: "{{ context.criteria }}"
      timeout_seconds: 120
      retry: 1                  # Retry once on failure

    - id: analyze
      tool: llm/analyze
      condition: "{{ steps.search.output }}"  # Skip if search found nothing
      params:
        input: "{{ steps.search.output }}"

  mcp:                          # MCP server bindings
    servers:
      - name: firecrawl
        uri: mcp://firecrawl.dev/v1
        auth_env: FIRECRAWL_API_KEY
        capabilities: [search, scrape]

  outputs:                      # What the agent returns
    - name: results
      type: list
      from: "{{ steps.analyze.output }}"
```

## Template expressions

Step params and conditions support `{{ ... }}` expressions:

| Expression | Resolves to |
|---|---|
| `{{ context.scout_id }}` | Runtime scout ID |
| `{{ context.user_id }}` | Runtime user ID |
| `{{ steps.search.output }}` | Output of the "search" step |
| `{{ steps.search.results }}` | Nested field from step output |
| `{{ env.FIRECRAWL_API_KEY }}` | Environment variable |

## Available tools

### Internal (`internal/`)

| Tool | Description |
|---|---|
| `internal/forward_ef` | Forward to a Supabase Edge Function |
| `internal/dedup` | Check against execution history |
| `internal/notify` | Send notification (email via Resend) |
| `internal/noop` | No-op placeholder |

### LLM (`llm/`)

| Tool | Description |
|---|---|
| `llm/analyze` | AI analysis / filtering |
| `llm/summarize` | AI summarization |

### Firecrawl (`firecrawl/`)

| Tool | Description |
|---|---|
| `firecrawl/search` | Web search across news sources |
| `firecrawl/scrape` | Scrape a specific URL |

## Agent types

| Type | Purpose | Example |
|---|---|---|
| `monitor` | Watch for new content matching criteria | Beat monitoring, page watching |
| `summarize` | Produce editorial briefs from collected data | Daily digests, timeline reports |
| `investigate` | Deep-dive analysis of a lead (future) | — |
| `extract` | Structured data extraction (future) | — |

## How dispatch works

When a scout runs, the dispatcher:

1. Checks if any AgentSPEX YAML has the scout's type in its `tags`
2. If found → executes the YAML workflow (steps in sequence)
3. If not found → falls back to the legacy Edge Function dispatch
   (`execute-scout/index.ts` WORKERS table)

This means existing scouts keep working unchanged during the transition.

## Authoring tips for journalists

- **Start from a template.** Copy `monitor.yaml` or `summarize.yaml` and modify.
- **Use descriptive step IDs.** They appear in logs and error messages.
- **Set `condition` on notification steps** so you don't get empty alerts.
- **Use `retry: 1`** on flaky external calls (search, scrape).
- **Keep `timeout_seconds` reasonable** — 60s for LLM, 120s for search.

## MCP integration

Each agent can declare MCP server bindings. These tell the dispatcher which
external services the agent depends on and how to authenticate:

```yaml
mcp:
  servers:
    - name: firecrawl
      uri: mcp://firecrawl.dev/v1
      auth_env: FIRECRAWL_API_KEY    # env var holding the API key
      capabilities: [search, scrape]
```

The MCP bindings are available to tools at runtime via `context.mcp_servers`.
This enables tools to discover and connect to MCP servers dynamically rather
than hardcoding API endpoints.

## Running tests

```bash
cd backend
python3 -m pytest tests/unit/agentspex/ -v
```
