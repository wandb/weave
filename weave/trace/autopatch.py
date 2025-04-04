"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field, validate_call

from weave.trace.weave_client import Call


class OpSettings(BaseModel):
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details."""

    name: Optional[str] = None
    call_display_name: Optional[Union[str, Callable[[Call], str]]] = None
    postprocess_inputs: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    postprocess_output: Optional[Callable[[Any], Any]] = None


class IntegrationSettings(BaseModel):
    """Configuration for a specific integration."""

    enabled: bool = True
    op_settings: OpSettings = Field(default_factory=OpSettings)


class AutopatchSettings(BaseModel):
    """Settings for auto-patching integrations."""

    # If True, other autopatch settings are ignored.
    disable_autopatch: bool = False

    anthropic: IntegrationSettings = Field(default_factory=IntegrationSettings)
    cerebras: IntegrationSettings = Field(default_factory=IntegrationSettings)
    cohere: IntegrationSettings = Field(default_factory=IntegrationSettings)
    crewai: IntegrationSettings = Field(default_factory=IntegrationSettings)
    dspy: IntegrationSettings = Field(default_factory=IntegrationSettings)
    google_generativeai: IntegrationSettings = Field(
        default_factory=IntegrationSettings
    )
    google_genai_sdk: IntegrationSettings = Field(default_factory=IntegrationSettings)
    groq: IntegrationSettings = Field(default_factory=IntegrationSettings)
    huggingface: IntegrationSettings = Field(default_factory=IntegrationSettings)
    instructor: IntegrationSettings = Field(default_factory=IntegrationSettings)
    litellm: IntegrationSettings = Field(default_factory=IntegrationSettings)
    mistral: IntegrationSettings = Field(default_factory=IntegrationSettings)
    mcp: IntegrationSettings = Field(default_factory=IntegrationSettings)
    notdiamond: IntegrationSettings = Field(default_factory=IntegrationSettings)
    openai: IntegrationSettings = Field(default_factory=IntegrationSettings)
    openai_agents: IntegrationSettings = Field(default_factory=IntegrationSettings)
    vertexai: IntegrationSettings = Field(default_factory=IntegrationSettings)
    chatnvidia: IntegrationSettings = Field(default_factory=IntegrationSettings)


@validate_call
def autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    if settings is None:
        settings = AutopatchSettings()
    if settings.disable_autopatch:
        return

    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
    from weave.integrations.crewai import get_crewai_patcher
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        get_google_generativeai_patcher,
    )
    from weave.integrations.google_genai.google_genai_sdk import (
        get_google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import get_groq_patcher
    from weave.integrations.huggingface.huggingface_inference_client_sdk import (
        get_huggingface_patcher,
    )
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import (
        get_nvidia_ai_patcher,
    )
    from weave.integrations.litellm.litellm import get_litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher
    from weave.integrations.mistral import get_mistral_patcher
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    get_openai_patcher(settings.openai).attempt_patch()
    get_mistral_patcher(settings.mistral).attempt_patch()
    get_mcp_server_patcher(settings.mcp).attempt_patch()
    get_mcp_client_patcher(settings.mcp).attempt_patch()
    get_litellm_patcher(settings.litellm).attempt_patch()
    get_anthropic_patcher(settings.anthropic).attempt_patch()
    get_groq_patcher(settings.groq).attempt_patch()
    get_instructor_patcher(settings.instructor).attempt_patch()
    get_dspy_patcher(settings.dspy).attempt_patch()
    get_cerebras_patcher(settings.cerebras).attempt_patch()
    get_cohere_patcher(settings.cohere).attempt_patch()
    get_google_generativeai_patcher(settings.google_generativeai).attempt_patch()
    get_google_genai_patcher(settings.google_genai_sdk).attempt_patch()
    get_crewai_patcher(settings.crewai).attempt_patch()
    get_notdiamond_patcher(settings.notdiamond).attempt_patch()
    get_vertexai_patcher(settings.vertexai).attempt_patch()
    get_nvidia_ai_patcher(settings.chatnvidia).attempt_patch()
    get_huggingface_patcher(settings.huggingface).attempt_patch()
    get_openai_agents_patcher(settings.openai_agents).attempt_patch()

    llamaindex_patcher.attempt_patch()
    langchain_patcher.attempt_patch()


def reset_autopatch() -> None:
    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
    from weave.integrations.crewai import get_crewai_patcher
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        get_google_generativeai_patcher,
    )
    from weave.integrations.google_genai.google_genai_sdk import (
        get_google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import get_groq_patcher
    from weave.integrations.huggingface.huggingface_inference_client_sdk import (
        get_huggingface_patcher,
    )
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import (
        get_nvidia_ai_patcher,
    )
    from weave.integrations.litellm.litellm import get_litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher
    from weave.integrations.mistral import get_mistral_patcher
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    get_openai_patcher().undo_patch()
    get_mistral_patcher().undo_patch()
    get_mcp_server_patcher().undo_patch()
    get_mcp_client_patcher().undo_patch()
    get_litellm_patcher().undo_patch()
    get_anthropic_patcher().undo_patch()
    get_groq_patcher().undo_patch()
    get_instructor_patcher().undo_patch()
    get_dspy_patcher().undo_patch()
    get_cerebras_patcher().undo_patch()
    get_cohere_patcher().undo_patch()
    get_google_generativeai_patcher().undo_patch()
    get_crewai_patcher().undo_patch()
    get_google_genai_patcher().undo_patch()
    get_notdiamond_patcher().undo_patch()
    get_vertexai_patcher().undo_patch()
    get_nvidia_ai_patcher().undo_patch()
    get_huggingface_patcher().undo_patch()
    get_openai_agents_patcher().undo_patch()

    llamaindex_patcher.undo_patch()
    langchain_patcher.undo_patch()
