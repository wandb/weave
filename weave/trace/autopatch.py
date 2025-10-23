"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field

from weave.trace.call import Call


class OpSettings(BaseModel):
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details.
    """

    name: Optional[str] = None
    call_display_name: Optional[Union[str, Callable[[Call], str]]] = None
    postprocess_inputs: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    postprocess_output: Optional[Callable[[Any], Any]] = None


class IntegrationSettings(BaseModel):
    """Configuration for a specific integration."""

    enabled: bool = True
    op_settings: OpSettings = Field(default_factory=OpSettings)


class AutopatchSettings(BaseModel):
    """Configuration for autopatch integrations.

    This class is deprecated. Please use explicit patching instead.
    For example: weave.integrations.patch_openai()
    """

    openai: Optional[IntegrationSettings] = None
    anthropic: Optional[IntegrationSettings] = None
    mistral: Optional[IntegrationSettings] = None
    groq: Optional[IntegrationSettings] = None
    litellm: Optional[IntegrationSettings] = None
    cerebras: Optional[IntegrationSettings] = None
    cohere: Optional[IntegrationSettings] = None
    google_genai: Optional[IntegrationSettings] = None
    vertexai: Optional[IntegrationSettings] = None
    huggingface: Optional[IntegrationSettings] = None
    instructor: Optional[IntegrationSettings] = None
    dspy: Optional[IntegrationSettings] = None
    crewai: Optional[IntegrationSettings] = None
    notdiamond: Optional[IntegrationSettings] = None
    mcp: Optional[IntegrationSettings] = None
    nvidia: Optional[IntegrationSettings] = None
    smolagents: Optional[IntegrationSettings] = None
    openai_agents: Optional[IntegrationSettings] = None
    verdict: Optional[IntegrationSettings] = None
    autogen: Optional[IntegrationSettings] = None
    langchain: Optional[IntegrationSettings] = None
    llamaindex: Optional[IntegrationSettings] = None
    openai_realtime: Optional[IntegrationSettings] = None
