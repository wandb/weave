"""Pydantic models for agent_eval configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class HarnessType(str, Enum):
    """Supported harness types."""

    CODEX = "codex"
    CLAUDE = "claude"
    OPENCODE = "opencode"
    GENERIC = "generic"


class DriverType(str, Enum):
    """Supported driver types."""

    DOCKER = "docker"
    MODAL = "modal"


class CheckType(str, Enum):
    """Deterministic check types."""

    FILE_EXISTS = "file_exists"
    FILE_CONTAINS = "file_contains"
    TRAJECTORY_CONTAINS = "trajectory_contains"
    COMMAND_EXECUTED = "command_executed"


# --- Harness Configuration ---


class HarnessConfig(BaseModel):
    """Configuration for an agent harness."""

    type: HarnessType
    model: str
    args: list[str] = Field(default_factory=list)

    def required_env_keys(self) -> list[str]:
        """Return environment variable names this harness requires."""
        if self.type == HarnessType.CODEX:
            return ["OPENAI_API_KEY"]
        elif self.type == HarnessType.CLAUDE:
            return ["ANTHROPIC_API_KEY"]
        elif self.type == HarnessType.OPENCODE:
            return ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
        return []


# --- Driver Configuration ---


class DriverConfig(BaseModel):
    """Configuration for the sandbox driver."""

    type: DriverType = DriverType.DOCKER
    # Docker-specific options
    docker_host: str | None = None
    # Modal-specific options (future)
    modal_app: str | None = None


# --- Environment Configuration ---


class GitConfig(BaseModel):
    """Git repository configuration for environment."""

    repo: str
    ref: str = "main"


class EnvironmentConfig(BaseModel):
    """Configuration for the execution environment."""

    base_image: str = "python:3.12-slim"
    git: GitConfig | None = None
    layers: list[str] = Field(default_factory=list)
    setup: list[str] = Field(default_factory=list)
    additional_env_keys: list[str] = Field(default_factory=list)


# --- Skill Configuration ---


class SkillConfig(BaseModel):
    """Configuration for the skill being evaluated."""

    path: str


# --- Task Configuration ---


class TaskConfig(BaseModel):
    """Configuration for a single evaluation task."""

    id: str
    prompt: str
    timeout: int = 300
    expected_trigger: bool | None = None


# --- Scoring Configuration ---


class DeterministicCheck(BaseModel):
    """A single deterministic check."""

    type: CheckType
    path: str | None = None
    pattern: str | None = None


class DeterministicScorerConfig(BaseModel):
    """Configuration for deterministic scoring."""

    checks: list[DeterministicCheck] = Field(default_factory=list)


class LLMRubricConfig(BaseModel):
    """Configuration for LLM-based rubric scoring."""

    model: str = "gpt-4o"
    prompt: str
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    class Config:
        populate_by_name = True


class CustomScorerConfig(BaseModel):
    """Configuration for a custom scorer container."""

    image: str
    config: str | None = None
    command: list[str] | None = None


class ScoringConfig(BaseModel):
    """Configuration for all scoring."""

    deterministic: DeterministicScorerConfig | None = None
    rubric: LLMRubricConfig | None = None
    custom: list[CustomScorerConfig] = Field(default_factory=list)


# --- Network Configuration ---


class NetworkConfig(BaseModel):
    """Network access configuration for scorer containers."""

    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["api.openai.com", "api.anthropic.com"]
    )


# --- Output Configuration ---


class WeaveOutputConfig(BaseModel):
    """Weave output configuration."""

    project: str


class OutputConfig(BaseModel):
    """Output configuration."""

    weave: WeaveOutputConfig | None = None
    directory: str = "./results"


# --- Matrix Configuration ---


class MatrixConfig(BaseModel):
    """Matrix expansion configuration."""

    harness: list[HarnessConfig] = Field(default_factory=list)


# --- Top-level Configuration ---


class EvalConfig(BaseModel):
    """Top-level evaluation configuration."""

    version: str = "1.0"
    name: str
    description: str = ""

    matrix: MatrixConfig | None = None
    driver: DriverConfig = Field(default_factory=DriverConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    skill: SkillConfig
    tasks: list[TaskConfig]
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    def expand_matrix(self) -> list[tuple[HarnessConfig, TaskConfig]]:
        """Expand matrix into list of (harness, task) combinations."""
        harnesses = self.matrix.harness if self.matrix else []
        if not harnesses:
            # Default to codex with gpt-4o if no matrix specified
            harnesses = [HarnessConfig(type=HarnessType.CODEX, model="gpt-4o")]

        return [(h, t) for h in harnesses for t in self.tasks]
