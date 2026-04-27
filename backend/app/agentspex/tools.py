"""
AgentSPEX tool registry — maps tool references to callables.

Tools are organised by namespace. The ``internal`` namespace provides
built-in coJournalist capabilities (Supabase Edge Function forwarding,
LLM calls, dedup). External namespaces correspond to MCP server bindings
declared in agent YAML (e.g. ``firecrawl``, ``resend``).

Each registered tool is an async callable with signature:
    async def tool(params: dict, context: StepContext) -> Any
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from app.agentspex.schema import McpServerBinding, ToolRef

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class StepContext:
    """Runtime context passed to every tool invocation."""
    scout_id: Optional[str] = None
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    step_outputs: dict[str, Any] = field(default_factory=dict)
    mcp_servers: dict[str, McpServerBinding] = field(default_factory=dict)


class ToolNotFoundError(Exception):
    def __init__(self, ref: ToolRef):
        super().__init__(f"No tool registered for {ref.namespace}/{ref.tool_name}")
        self.ref = ref


class ToolRegistry:
    """Registry of tool callables keyed by ``namespace/tool_name``."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolCallable] = {}

    def register(self, namespace: str, tool_name: str, fn: ToolCallable) -> None:
        key = f"{namespace}/{tool_name}"
        self._tools[key] = fn
        logger.debug("Registered tool: %s", key)

    def get(self, ref: ToolRef) -> ToolCallable:
        key = f"{ref.namespace}/{ref.tool_name}"
        fn = self._tools.get(key)
        if fn is None:
            raise ToolNotFoundError(ref)
        return fn

    def has(self, ref: ToolRef) -> bool:
        return f"{ref.namespace}/{ref.tool_name}" in self._tools

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())


# ---------------------------------------------------------------------------
# Built-in tools (internal namespace)
# ---------------------------------------------------------------------------

async def _noop(params: dict, context: StepContext) -> dict:
    """Placeholder tool for steps that haven't been wired yet."""
    return {"status": "noop", "params": params}


async def _forward_edge_function(params: dict, context: StepContext) -> dict:
    """Forward a call to a Supabase Edge Function.

    Expects ``params["function"]`` and ``params["path"]`` to identify
    the target EF. In production this would use the service-role key;
    during prototyping it returns a stub.
    """
    fn_name = params.get("function", "unknown")
    path = params.get("path", "/")
    return {
        "status": "dispatched",
        "function": fn_name,
        "path": path,
        "scout_id": context.scout_id,
    }


async def _llm_analyze(params: dict, context: StepContext) -> dict:
    """Stub for LLM analysis — would call Gemini/OpenRouter in production."""
    return {
        "status": "analyzed",
        "model": params.get("model", "gemini-2.5-flash-lite"),
        "input_length": len(str(params.get("input", ""))),
    }


async def _dedup_check(params: dict, context: StepContext) -> dict:
    """Stub for deduplication check against execution history."""
    return {
        "status": "checked",
        "items_in": params.get("count", 0),
        "items_out": params.get("count", 0),
    }


async def _notify(params: dict, context: StepContext) -> dict:
    """Stub for sending notifications via Resend."""
    return {
        "status": "notification_queued",
        "channel": params.get("channel", "email"),
    }


async def _firecrawl_search(params: dict, context: StepContext) -> dict:
    """Stub for Firecrawl web search."""
    return {
        "status": "searched",
        "query": params.get("query", ""),
        "results_count": 0,
    }


async def _firecrawl_scrape(params: dict, context: StepContext) -> dict:
    """Stub for Firecrawl page scraping."""
    return {
        "status": "scraped",
        "url": params.get("url", ""),
    }


async def _summarize(params: dict, context: StepContext) -> dict:
    """Stub for LLM-based summarization."""
    return {
        "status": "summarized",
        "format": params.get("format", "bullets"),
    }


def build_default_registry() -> ToolRegistry:
    """Create a registry with all built-in tools pre-registered."""
    reg = ToolRegistry()

    reg.register("internal", "noop", _noop)
    reg.register("internal", "forward_ef", _forward_edge_function)
    reg.register("internal", "dedup", _dedup_check)
    reg.register("internal", "notify", _notify)

    reg.register("llm", "analyze", _llm_analyze)
    reg.register("llm", "summarize", _summarize)

    reg.register("firecrawl", "search", _firecrawl_search)
    reg.register("firecrawl", "scrape", _firecrawl_scrape)

    return reg
