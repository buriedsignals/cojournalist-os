"""
AgentSPEX — Agent Specification & Execution Language for coJournalist.

Declarative YAML-based agent workflow definitions with MCP tool bindings.
Replaces ad-hoc dispatch routing with structured, journalist-authorable
agent specifications.
"""

from app.agentspex.schema import AgentSpec, StepSpec, McpBinding, ToolRef
from app.agentspex.loader import load_agent, load_all_agents, validate_spec
from app.agentspex.dispatch import AgentDispatcher

__all__ = [
    "AgentSpec",
    "StepSpec",
    "McpBinding",
    "ToolRef",
    "load_agent",
    "load_all_agents",
    "validate_spec",
    "AgentDispatcher",
]
