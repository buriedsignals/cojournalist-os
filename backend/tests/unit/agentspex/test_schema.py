"""Tests for AgentSPEX schema validation."""
import pytest
from app.agentspex.schema import (
    AgentSpec,
    AgentType,
    InputSpec,
    MetadataSpec,
    StepSpec,
    ToolRef,
    WorkflowSpec,
)


class TestToolRef:
    def test_parse_valid(self):
        ref = ToolRef.parse_ref("firecrawl/search")
        assert ref.namespace == "firecrawl"
        assert ref.tool_name == "search"

    def test_parse_internal(self):
        ref = ToolRef.parse_ref("internal/dedup")
        assert ref.namespace == "internal"
        assert ref.tool_name == "dedup"

    def test_parse_invalid_no_slash(self):
        with pytest.raises(ValueError, match="namespace/name"):
            ToolRef.parse_ref("noseparator")


class TestStepSpec:
    def test_valid_tool_ref(self):
        step = StepSpec(id="s1", tool="llm/analyze")
        assert step.tool_ref().namespace == "llm"

    def test_invalid_tool_ref(self):
        with pytest.raises(ValueError):
            StepSpec(id="s1", tool="bad-ref")


class TestWorkflowSpec:
    def test_duplicate_step_ids_rejected(self):
        with pytest.raises(ValueError, match="Duplicate step ids"):
            WorkflowSpec(
                steps=[
                    StepSpec(id="dup", tool="internal/noop"),
                    StepSpec(id="dup", tool="internal/noop"),
                ]
            )

    def test_unique_step_ids_accepted(self):
        spec = WorkflowSpec(
            steps=[
                StepSpec(id="a", tool="internal/noop"),
                StepSpec(id="b", tool="internal/noop"),
            ]
        )
        assert len(spec.steps) == 2


class TestAgentSpec:
    def test_minimal_valid(self):
        data = {
            "apiVersion": "agentspex/v1",
            "kind": "AgentWorkflow",
            "metadata": {
                "name": "test-agent",
                "type": "monitor",
            },
            "spec": {
                "steps": [
                    {"id": "s1", "tool": "internal/noop"},
                ],
            },
        }
        agent = AgentSpec.model_validate(data)
        assert agent.name == "test-agent"
        assert agent.agent_type == AgentType.MONITOR
        assert agent.step_ids() == ["s1"]

    def test_invalid_api_version(self):
        data = {
            "apiVersion": "agentspex/v99",
            "kind": "AgentWorkflow",
            "metadata": {"name": "bad", "type": "monitor"},
            "spec": {"steps": []},
        }
        with pytest.raises(Exception):
            AgentSpec.model_validate(data)

    def test_full_spec_with_mcp(self):
        data = {
            "apiVersion": "agentspex/v1",
            "kind": "AgentWorkflow",
            "metadata": {
                "name": "full-agent",
                "description": "A fully specified agent",
                "type": "summarize",
                "version": "1.0.0",
                "tags": ["beat", "web"],
            },
            "spec": {
                "inputs": [
                    {"name": "criteria", "type": "string", "required": True},
                ],
                "steps": [
                    {
                        "id": "search",
                        "tool": "firecrawl/search",
                        "params": {"query": "{{ context.criteria }}"},
                    },
                    {
                        "id": "analyze",
                        "tool": "llm/analyze",
                        "params": {"input": "{{ steps.search.output }}"},
                        "condition": "{{ steps.search.output }}",
                    },
                ],
                "mcp": {
                    "servers": [
                        {
                            "name": "firecrawl",
                            "uri": "mcp://firecrawl.dev/v1",
                            "auth_env": "FIRECRAWL_API_KEY",
                            "capabilities": ["search"],
                        }
                    ]
                },
                "outputs": [
                    {"name": "results", "type": "list", "from": "{{ steps.analyze.output }}"},
                ],
            },
        }
        agent = AgentSpec.model_validate(data)
        assert agent.agent_type == AgentType.SUMMARIZE
        assert agent.mcp_server_names() == ["firecrawl"]
        assert len(agent.spec.outputs) == 1
