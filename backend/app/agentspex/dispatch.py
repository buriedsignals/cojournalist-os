"""
AgentSPEX dispatcher — loads agent specs and executes workflows.

The dispatcher is the main entry point for running agent workflows.
It loads agent YAML definitions, resolves tool references through
the registry, evaluates step conditions, and executes steps in
sequence.

Backward compatibility: when no AgentSPEX YAML is found for a given
scout type, the dispatcher falls back to the existing hard-coded
``WORKERS`` dispatch table in ``execute-scout/index.ts``.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.agentspex.loader import load_all_agents, AgentSpecError
from app.agentspex.schema import AgentSpec, AgentType, StepSpec
from app.agentspex.tools import (
    StepContext,
    ToolNotFoundError,
    ToolRegistry,
    build_default_registry,
)

logger = logging.getLogger(__name__)

LEGACY_WORKERS: dict[str, str] = {
    "web": "scout-web-execute",
    "beat": "scout-beat-execute",
    "civic": "civic-execute",
    "social": "social-kickoff",
}

TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def _resolve_template(value: Any, context: StepContext) -> Any:
    """Resolve ``{{ ... }}`` placeholders in step params.

    Supports:
      - ``{{ steps.<step_id>.output }}`` — output of a previous step
      - ``{{ context.<field> }}`` — runtime context field
      - ``{{ env.<VAR> }}`` — environment variable (returns the key name,
        actual resolution deferred to tool implementation)
    """
    if not isinstance(value, str):
        return value

    match = TEMPLATE_RE.fullmatch(value)
    if not match:
        return value

    expr = match.group(1).strip()
    parts = expr.split(".")

    if parts[0] == "steps" and len(parts) >= 3:
        step_id = parts[1]
        output = context.step_outputs.get(step_id)
        if output is None:
            return value
        for key in parts[2:]:
            if isinstance(output, dict):
                output = output.get(key)
            else:
                return value
        return output

    if parts[0] == "context" and len(parts) == 2:
        return getattr(context, parts[1], value)

    if parts[0] == "env" and len(parts) == 2:
        import os
        return os.environ.get(parts[1], "")

    return value


def _resolve_params(params: dict[str, Any], context: StepContext) -> dict[str, Any]:
    """Resolve all template expressions in a params dict."""
    resolved = {}
    for key, value in params.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_params(value, context)
        elif isinstance(value, list):
            resolved[key] = [_resolve_template(v, context) for v in value]
        else:
            resolved[key] = _resolve_template(value, context)
    return resolved


def _evaluate_condition(condition: Optional[str], context: StepContext) -> bool:
    """Evaluate a step condition.

    Conditions reference step outputs via template syntax. A step runs
    if its condition resolves to a truthy value.
    """
    if condition is None:
        return True
    resolved = _resolve_template(condition, context)
    if resolved == condition:
        return True
    return bool(resolved)


class AgentDispatcher:
    """Loads agent specs and dispatches workflow execution."""

    def __init__(
        self,
        agents_dir: Optional[Path] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self._agents_dir = agents_dir
        self._registry = registry or build_default_registry()
        self._specs: Optional[dict[str, AgentSpec]] = None

    @property
    def specs(self) -> dict[str, AgentSpec]:
        if self._specs is None:
            self._specs = load_all_agents(self._agents_dir)
        return self._specs

    def reload(self) -> None:
        """Force reload of agent specs from disk."""
        self._specs = None

    def get_agent(self, name: str) -> Optional[AgentSpec]:
        return self.specs.get(name)

    def get_agents_by_type(self, agent_type: AgentType) -> list[AgentSpec]:
        return [s for s in self.specs.values() if s.agent_type == agent_type]

    def list_agents(self) -> list[str]:
        return sorted(self.specs.keys())

    def resolve_scout_type(self, scout_type: str) -> Optional[AgentSpec]:
        """Find an agent spec that handles a given scout type.

        Looks for agents whose metadata tags include the scout type.
        Returns the first match or None (caller should fall back to
        legacy dispatch).
        """
        for spec in self.specs.values():
            if scout_type in spec.metadata.tags:
                return spec
        return None

    def get_legacy_worker(self, scout_type: str) -> Optional[str]:
        """Return the legacy Edge Function name for a scout type."""
        return LEGACY_WORKERS.get(scout_type)

    async def execute(
        self,
        spec: AgentSpec,
        inputs: dict[str, Any],
        scout_id: Optional[str] = None,
        user_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute an agent workflow.

        Runs each step in sequence, passing outputs forward via template
        resolution. Returns a dict of step results keyed by step id,
        plus an ``outputs`` key with the spec's declared outputs.
        """
        context = StepContext(
            scout_id=scout_id,
            user_id=user_id,
            run_id=run_id,
            mcp_servers={s.name: s for s in spec.spec.mcp.servers},
        )

        for inp in spec.spec.inputs:
            if inp.required and inp.name not in inputs:
                raise ValueError(f"Missing required input: {inp.name}")

        results: dict[str, Any] = {}

        for step in spec.spec.steps:
            if not _evaluate_condition(step.condition, context):
                logger.info("Skipping step %s (condition not met)", step.id)
                results[step.id] = {"skipped": True}
                continue

            resolved_params = _resolve_params(step.params, context)
            resolved_params.update({
                k: v for k, v in inputs.items()
                if k not in resolved_params
            })

            try:
                tool_fn = self._registry.get(step.tool_ref())
            except ToolNotFoundError:
                logger.warning(
                    "Tool %s not found for step %s; using noop",
                    step.tool,
                    step.id,
                )
                tool_fn = self._registry.get(
                    __import__("app.agentspex.schema", fromlist=["ToolRef"])
                    .ToolRef.parse_ref("internal/noop")
                )

            attempt = 0
            last_error: Optional[Exception] = None
            while attempt <= step.retry:
                try:
                    result = await tool_fn(resolved_params, context)
                    results[step.id] = result
                    context.step_outputs[step.id] = result
                    break
                except Exception as exc:
                    last_error = exc
                    attempt += 1
                    if attempt <= step.retry:
                        logger.warning(
                            "Step %s attempt %d failed: %s; retrying",
                            step.id,
                            attempt,
                            exc,
                        )
            else:
                logger.error("Step %s failed after %d attempts", step.id, step.retry + 1)
                results[step.id] = {"error": str(last_error)}

        output_values = {}
        for out in spec.spec.outputs:
            output_values[out.name] = _resolve_template(out.from_ref, context)

        return {"steps": results, "outputs": output_values}

    async def dispatch(
        self,
        scout_type: str,
        inputs: dict[str, Any],
        scout_id: Optional[str] = None,
        user_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """High-level dispatch: try AgentSPEX first, fall back to legacy.

        Returns the execution result if an agent spec handles the scout
        type, or a ``{"legacy": True, "worker": "..."}`` dict indicating
        the caller should use the legacy Edge Function dispatch.
        """
        spec = self.resolve_scout_type(scout_type)
        if spec:
            logger.info(
                "Dispatching scout_type=%s via AgentSPEX agent %s",
                scout_type,
                spec.name,
            )
            return await self.execute(
                spec, inputs, scout_id=scout_id, user_id=user_id, run_id=run_id
            )

        worker = self.get_legacy_worker(scout_type)
        if worker:
            logger.info(
                "No AgentSPEX agent for scout_type=%s; falling back to legacy worker %s",
                scout_type,
                worker,
            )
            return {"legacy": True, "worker": worker, "scout_type": scout_type}

        raise ValueError(f"Unknown scout type: {scout_type}")
