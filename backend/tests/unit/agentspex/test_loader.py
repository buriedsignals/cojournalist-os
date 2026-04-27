"""Tests for AgentSPEX YAML loader."""
import pytest
from pathlib import Path

from app.agentspex.loader import (
    load_agent,
    load_all_agents,
    find_agents_by_type,
    validate_spec,
    AgentSpecError,
)
from app.agentspex.schema import AgentType

AGENTS_DIR = Path(__file__).resolve().parents[4] / "agentspex" / "agents"


class TestLoadAgent:
    def test_load_monitor(self):
        spec = load_agent(AGENTS_DIR / "monitor.yaml")
        assert spec.name == "monitor"
        assert spec.agent_type == AgentType.MONITOR
        assert len(spec.spec.steps) >= 3

    def test_load_summarize(self):
        spec = load_agent(AGENTS_DIR / "summarize.yaml")
        assert spec.name == "summarize"
        assert spec.agent_type == AgentType.SUMMARIZE
        assert len(spec.spec.steps) >= 3

    def test_missing_file(self):
        with pytest.raises(AgentSpecError, match="file not found"):
            load_agent(AGENTS_DIR / "nonexistent.yaml")

    def test_wrong_extension(self, tmp_path):
        bad = tmp_path / "agent.txt"
        bad.write_text("apiVersion: agentspex/v1")
        with pytest.raises(AgentSpecError, match="extension"):
            load_agent(bad)


class TestLoadAllAgents:
    def test_loads_both_agents(self):
        agents = load_all_agents(AGENTS_DIR)
        assert "monitor" in agents
        assert "summarize" in agents
        assert len(agents) >= 2

    def test_empty_dir(self, tmp_path):
        agents = load_all_agents(tmp_path)
        assert agents == {}

    def test_nonexistent_dir(self, tmp_path):
        agents = load_all_agents(tmp_path / "nope")
        assert agents == {}


class TestFindAgentsByType:
    def test_find_monitor(self):
        monitors = find_agents_by_type(AgentType.MONITOR, AGENTS_DIR)
        assert len(monitors) >= 1
        assert all(a.agent_type == AgentType.MONITOR for a in monitors)

    def test_find_summarize(self):
        summarizers = find_agents_by_type(AgentType.SUMMARIZE, AGENTS_DIR)
        assert len(summarizers) >= 1

    def test_find_nonexistent_type(self):
        investigators = find_agents_by_type(AgentType.INVESTIGATE, AGENTS_DIR)
        assert investigators == []


class TestValidateSpec:
    def test_valid_dict(self):
        data = {
            "apiVersion": "agentspex/v1",
            "kind": "AgentWorkflow",
            "metadata": {"name": "inline", "type": "monitor"},
            "spec": {"steps": [{"id": "s1", "tool": "internal/noop"}]},
        }
        spec = validate_spec(data)
        assert spec.name == "inline"

    def test_invalid_dict(self):
        with pytest.raises(AgentSpecError):
            validate_spec({"bad": "data"})
