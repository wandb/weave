"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from weave.trace.call import Call


@dataclass
class OpSettings:
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details.
    """

    name: str | None = None
    call_display_name: str | Callable[[Call], str] | None = None
    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    postprocess_output: Callable[[Any], Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary. Provided for backward compatibility."""
        return asdict(self)

    def model_copy(self, update: dict[str, Any] | None = None) -> OpSettings:
        """Create a copy with optional updates. Provided for backward compatibility."""
        if update is None:
            return replace(self)
        return replace(self, **update)


@dataclass
class IntegrationSettings:
    """Configuration for a specific integration."""

    enabled: bool = True
    op_settings: OpSettings = field(default_factory=OpSettings)

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary. Provided for backward compatibility."""
        return {
            "enabled": self.enabled,
            "op_settings": self.op_settings.model_dump(),
        }

    def model_copy(self, update: dict[str, Any] | None = None) -> IntegrationSettings:
        """Create a copy with optional updates. Provided for backward compatibility."""
        if update is None:
            return replace(self)
        return replace(self, **update)


@dataclass
class AutopatchSettings:
    """Configuration for autopatch integrations.

    This class is deprecated. Please use explicit patching instead.
    For example: weave.integrations.patch_openai()
    """

    openai: IntegrationSettings | None = None
    anthropic: IntegrationSettings | None = None
    mistral: IntegrationSettings | None = None
    groq: IntegrationSettings | None = None
    litellm: IntegrationSettings | None = None
    cerebras: IntegrationSettings | None = None
    cohere: IntegrationSettings | None = None
    google_genai: IntegrationSettings | None = None
    vertexai: IntegrationSettings | None = None
    huggingface: IntegrationSettings | None = None
    instructor: IntegrationSettings | None = None
    dspy: IntegrationSettings | None = None
    crewai: IntegrationSettings | None = None
    notdiamond: IntegrationSettings | None = None
    mcp: IntegrationSettings | None = None
    nvidia: IntegrationSettings | None = None
    smolagents: IntegrationSettings | None = None
    openai_agents: IntegrationSettings | None = None
    verdict: IntegrationSettings | None = None
    autogen: IntegrationSettings | None = None
    langchain: IntegrationSettings | None = None
    llamaindex: IntegrationSettings | None = None
    openai_realtime: IntegrationSettings | None = None
