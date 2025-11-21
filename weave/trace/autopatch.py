"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from weave.trace.call import Call


class OpSettings(BaseModel):
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details.
    """

    name: str | None = None
    call_display_name: str | Callable[[Call], str] | None = None
    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    postprocess_output: Callable[[Any], Any] | None = None


class IntegrationSettings(BaseModel):
    """Configuration for a specific integration."""

    enabled: bool = True
    op_settings: OpSettings = Field(default_factory=OpSettings)


class AutopatchSettings(BaseModel):
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
