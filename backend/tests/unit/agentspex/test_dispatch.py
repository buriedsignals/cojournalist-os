"""Tests for AgentSPEX dispatcher."""
import pytest
from pathlib import Path

from app.agentspex.dispatch import (
    AgentDispatcher,
    _resolve_template,
    _evaluate_condition,
)
from app.agentspex.tools import StepContext, ToolRegistry, build_default_registry
from app.agentspex.schema import AgentType

AGENTS_DIR = Path(__file__).resolve().parents[4] / "agentspex" / "agents"


class TestTemplateResolution:
    def test_no_template(self):
        ctx = StepContext()
        assert _resolve_template("plain string", ctx) == "plain string"

    def test_non_string(self):
        ctx = StepContext()
        assert _resolve_template(42, ctx) == 42

    def test_context_field(self):
        ctx = StepContext(scout_id="abc-123")
        assert _resolve_template("{{ context.scout_id }}", ctx) == "abc-123"

    def test_step_output(self):
        ctx = StepContext(step_outputs={"search": {"results": [1, 2, 3]}})
        result = _resolve_template("{{ steps.search.results }}", ctx)
        assert result == [1, 2, 3]

    def test_missing_step(self):
        ctx = StepContext()
        raw = "{{ steps.missing.output }}"
        assert _resolve_template(raw, ctx) == raw

    def test_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        ctx = StepContext()
        assert _resolve_template("{{ env.TEST_VAR }}", ctx) == "hello"


class TestConditionEvaluation:
    def test_none_is_true(self):
        assert _evaluate_condition(None, StepContext()) is True

    def test_truthy_output(self):
        ctx = StepContext(step_outputs={"s1": {"data": [1]}})
        assert _evaluate_condition("{{ steps.s1.data }}", ctx) is True

    def test_falsy_output(self):
        ctx = StepContext(step_outputs={"s1": {"data": []}})
        assert _evaluate_condition("{{ steps.s1.data }}", ctx) is False

    def test_unresolvable_is_true(self):
        assert _evaluate_condition("{{ steps.nope.x }}", StepContext()) is True


class TestDispatcher:
    @pytest.fixture
    def dispatcher(self):
        return AgentDispatcher(agents_dir=AGENTS_DIR)

    def test_loads_agents(self, dispatcher):
        agents = dispatcher.list_agents()
        assert "monitor" in agents
        assert "summarize" in agents

    def test_get_agent(self, dispatcher):
        agent = dispatcher.get_agent("monitor")
        assert agent is not None
        assert agent.agent_type == AgentType.MONITOR

    def test_get_agents_by_type(self, dispatcher):
        monitors = dispatcher.get_agents_by_type(AgentType.MONITOR)
        assert len(monitors) >= 1

    def test_resolve_scout_type_beat(self, dispatcher):
        spec = dispatcher.resolve_scout_type("beat")
        assert spec is not None
        assert spec.name == "monitor"

    def test_resolve_scout_type_unknown(self, dispatcher):
        spec = dispatcher.resolve_scout_type("unknown-type")
        assert spec is None

    def test_legacy_fallback(self, dispatcher):
        assert dispatcher.get_legacy_worker("web") == "scout-web-execute"
        assert dispatcher.get_legacy_worker("social") == "social-kickoff"
        assert dispatcher.get_legacy_worker("nope") is None

    @pytest.mark.asyncio
    async def test_execute_monitor(self, dispatcher):
        spec = dispatcher.get_agent("monitor")
        result = await dispatcher.execute(
            spec,
            inputs={"criteria": "housing policy"},
            scout_id="test-scout-123",
        )
        assert "steps" in result
        assert "outputs" in result
        assert "discover_sources" in result["steps"]
        assert "analyze_relevance" in result["steps"]
        assert "deduplicate" in result["steps"]

    @pytest.mark.asyncio
    async def test_execute_summarize(self, dispatcher):
        spec = dispatcher.get_agent("summarize")
        result = await dispatcher.execute(
            spec,
            inputs={"format": "bullets"},
            scout_id="test-scout-456",
        )
        assert "steps" in result
        assert "fetch_units" in result["steps"]
        assert "generate_summary" in result["steps"]

    @pytest.mark.asyncio
    async def test_dispatch_beat_uses_agentspex(self, dispatcher):
        result = await dispatcher.dispatch(
            "beat",
            inputs={"criteria": "local elections"},
            scout_id="test-123",
        )
        assert "steps" in result
        assert "legacy" not in result

    @pytest.mark.asyncio
    async def test_dispatch_social_falls_back(self, dispatcher):
        result = await dispatcher.dispatch(
            "social",
            inputs={},
            scout_id="test-456",
        )
        assert result["legacy"] is True
        assert result["worker"] == "social-kickoff"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_raises(self, dispatcher):
        with pytest.raises(ValueError, match="Unknown scout type"):
            await dispatcher.dispatch("invalid", inputs={})

    def test_reload(self, dispatcher):
        _ = dispatcher.specs
        dispatcher.reload()
        assert dispatcher._specs is None
        _ = dispatcher.specs
        assert dispatcher._specs is not None
