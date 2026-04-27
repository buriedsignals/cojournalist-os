"""
AgentSPEX schema — Pydantic models that validate YAML agent definitions.

An AgentSpec describes a complete agent workflow: metadata, inputs, a
sequence of steps with tool references, MCP server bindings, and an
output mapping. The schema is versioned via ``api_version``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ApiVersion(str, Enum):
    V1 = "agentspex/v1"


class AgentKind(str, Enum):
    WORKFLOW = "AgentWorkflow"


class AgentType(str, Enum):
    MONITOR = "monitor"
    SUMMARIZE = "summarize"
    INVESTIGATE = "investigate"
    EXTRACT = "extract"


class InputSpec(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    description: str = ""
    default: Any = None


class ToolRef(BaseModel):
    """Reference to a tool: ``namespace/tool_name`` or ``internal/name``."""
    namespace: str
    tool_name: str

    @classmethod
    def parse_ref(cls, ref: str) -> "ToolRef":
        parts = ref.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Tool ref must be 'namespace/name', got: {ref!r}")
        return cls(namespace=parts[0], tool_name=parts[1])


class StepSpec(BaseModel):
    id: str
    tool: str
    description: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None
    retry: int = 0
    timeout_seconds: int = 300

    @field_validator("tool")
    @classmethod
    def validate_tool_ref(cls, v: str) -> str:
        ToolRef.parse_ref(v)
        return v

    def tool_ref(self) -> ToolRef:
        return ToolRef.parse_ref(self.tool)


class McpServerBinding(BaseModel):
    name: str
    uri: str
    auth_env: str = ""
    capabilities: list[str] = Field(default_factory=list)


class McpBinding(BaseModel):
    servers: list[McpServerBinding] = Field(default_factory=list)


class OutputSpec(BaseModel):
    name: str
    type: str = "any"
    from_ref: str = Field(alias="from")

    model_config = {"populate_by_name": True}


class MetadataSpec(BaseModel):
    name: str
    description: str = ""
    type: AgentType
    version: str = "0.1.0"
    author: str = ""
    tags: list[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    """Top-level AgentSPEX document."""
    api_version: ApiVersion = Field(alias="apiVersion")
    kind: AgentKind
    metadata: MetadataSpec
    spec: WorkflowSpec

    model_config = {"populate_by_name": True}

    @property
    def agent_type(self) -> AgentType:
        return self.metadata.type

    @property
    def name(self) -> str:
        return self.metadata.name

    def step_ids(self) -> list[str]:
        return [s.id for s in self.spec.steps]

    def mcp_server_names(self) -> list[str]:
        return [s.name for s in self.spec.mcp.servers]


class WorkflowSpec(BaseModel):
    inputs: list[InputSpec] = Field(default_factory=list)
    steps: list[StepSpec] = Field(default_factory=list)
    mcp: McpBinding = Field(default_factory=McpBinding)
    outputs: list[OutputSpec] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def validate_unique_step_ids(cls, v: list[StepSpec]) -> list[StepSpec]:
        ids = [s.id for s in v]
        dupes = [x for x in ids if ids.count(x) > 1]
        if dupes:
            raise ValueError(f"Duplicate step ids: {set(dupes)}")
        return v
