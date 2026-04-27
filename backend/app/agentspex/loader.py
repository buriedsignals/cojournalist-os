"""
AgentSPEX loader — reads YAML agent definitions and validates them.

Agent definition files live in ``agentspex/agents/`` at the repo root.
The loader discovers them by glob, parses YAML, and validates against
the Pydantic schema.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError as PydanticValidationError

from app.agentspex.schema import AgentSpec, AgentType

logger = logging.getLogger(__name__)

DEFAULT_AGENTS_DIR = Path(__file__).resolve().parents[3] / "agentspex" / "agents"


class AgentSpecError(Exception):
    """Raised when an agent YAML file fails to parse or validate."""

    def __init__(self, path: Path, detail: str):
        self.path = path
        self.detail = detail
        super().__init__(f"{path}: {detail}")


def load_agent(path: Path) -> AgentSpec:
    """Load and validate a single agent YAML file."""
    if not path.exists():
        raise AgentSpecError(path, "file not found")
    if not path.suffix in (".yaml", ".yml"):
        raise AgentSpecError(path, "expected .yaml or .yml extension")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AgentSpecError(path, f"YAML parse error: {exc}") from exc

    if not isinstance(raw, dict):
        raise AgentSpecError(path, "top-level YAML must be a mapping")

    return validate_spec(raw, path)


def validate_spec(data: dict, source: Optional[Path] = None) -> AgentSpec:
    """Validate a parsed YAML dict against the AgentSPEX schema."""
    source = source or Path("<inline>")
    try:
        return AgentSpec.model_validate(data)
    except PydanticValidationError as exc:
        raise AgentSpecError(source, str(exc)) from exc


def load_all_agents(
    agents_dir: Optional[Path] = None,
) -> dict[str, AgentSpec]:
    """Load all agent YAML files from a directory.

    Returns a dict keyed by agent name (metadata.name).
    """
    agents_dir = agents_dir or DEFAULT_AGENTS_DIR
    if not agents_dir.is_dir():
        logger.warning("AgentSPEX agents directory not found: %s", agents_dir)
        return {}

    specs: dict[str, AgentSpec] = {}
    for path in sorted(agents_dir.glob("*.yaml")):
        try:
            spec = load_agent(path)
            if spec.name in specs:
                logger.warning(
                    "Duplicate agent name %r in %s (already loaded from earlier file)",
                    spec.name,
                    path,
                )
            specs[spec.name] = spec
            logger.info("Loaded AgentSPEX agent: %s (%s)", spec.name, spec.agent_type.value)
        except AgentSpecError as exc:
            logger.error("Failed to load agent spec %s: %s", path, exc.detail)

    return specs


def find_agents_by_type(
    agent_type: AgentType,
    agents_dir: Optional[Path] = None,
) -> list[AgentSpec]:
    """Return all loaded agents matching a given type."""
    all_agents = load_all_agents(agents_dir)
    return [spec for spec in all_agents.values() if spec.agent_type == agent_type]
