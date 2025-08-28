"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field, validate_call

from weave.trace.call import Call


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
    smolagents: IntegrationSettings = Field(default_factory=IntegrationSettings)
    verdict: IntegrationSettings = Field(default_factory=IntegrationSettings)
    autogen: IntegrationSettings = Field(default_factory=IntegrationSettings)


@validate_call
def autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    if settings is None:
        settings = AutopatchSettings()
    if settings.disable_autopatch:
        return

    # Use lazy patching with import hooks
    from weave.trace.lazy_autopatch import setup_lazy_autopatch
    setup_lazy_autopatch(settings)


def reset_autopatch() -> None:
    from weave.trace.lazy_autopatch import teardown_lazy_autopatch
    teardown_lazy_autopatch()
    
    # Also undo patches for already-imported modules
    import sys
    
    # Check which integrations are already imported and undo their patches
    patch_undoers = {}
    
    if "openai" in sys.modules:
        from weave.integrations.openai.openai_sdk import get_openai_patcher
        patch_undoers["openai"] = get_openai_patcher
    if "anthropic" in sys.modules:
        from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
        patch_undoers["anthropic"] = get_anthropic_patcher
    if "mistral" in sys.modules:
        from weave.integrations.mistral.mistral_sdk import get_mistral_patcher
        patch_undoers["mistral"] = get_mistral_patcher
    if "litellm" in sys.modules:
        from weave.integrations.litellm.litellm import get_litellm_patcher
        patch_undoers["litellm"] = get_litellm_patcher
    if "groq" in sys.modules:
        from weave.integrations.groq.groq_sdk import get_groq_patcher
        patch_undoers["groq"] = get_groq_patcher
    if "instructor" in sys.modules:
        from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
        patch_undoers["instructor"] = get_instructor_patcher
    if "dspy" in sys.modules:
        from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
        patch_undoers["dspy"] = get_dspy_patcher
    if "cerebras" in sys.modules:
        from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
        patch_undoers["cerebras"] = get_cerebras_patcher
    if "cohere" in sys.modules:
        from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
        patch_undoers["cohere"] = get_cohere_patcher
    if "google.generativeai" in sys.modules:
        from weave.integrations.google_genai.google_genai_sdk import get_google_genai_patcher
        patch_undoers["google.generativeai"] = get_google_genai_patcher
    if "crewai" in sys.modules:
        from weave.integrations.crewai import get_crewai_patcher
        patch_undoers["crewai"] = get_crewai_patcher
    if "notdiamond" in sys.modules:
        from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
        patch_undoers["notdiamond"] = get_notdiamond_patcher
    if "vertexai" in sys.modules:
        from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher
        patch_undoers["vertexai"] = get_vertexai_patcher
    if "langchain_nvidia_ai_endpoints" in sys.modules:
        from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import get_nvidia_ai_patcher
        patch_undoers["langchain_nvidia_ai_endpoints"] = get_nvidia_ai_patcher
    if "huggingface_hub" in sys.modules:
        from weave.integrations.huggingface.huggingface_inference_client_sdk import get_huggingface_patcher
        patch_undoers["huggingface_hub"] = get_huggingface_patcher
    if "smolagents" in sys.modules:
        from weave.integrations.smolagents.smolagents_sdk import get_smolagents_patcher
        patch_undoers["smolagents"] = get_smolagents_patcher
    if "verdict" in sys.modules:
        from weave.integrations.verdict.verdict_sdk import get_verdict_patcher
        patch_undoers["verdict"] = get_verdict_patcher
    if "autogen" in sys.modules:
        from weave.integrations.autogen import get_autogen_patcher
        patch_undoers["autogen"] = get_autogen_patcher
    if "swarm" in sys.modules:
        from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher
        patch_undoers["swarm"] = get_openai_agents_patcher
    
    # Special handling for MCP
    if "mcp" in sys.modules:
        from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher
        get_mcp_server_patcher().undo_patch()
        get_mcp_client_patcher().undo_patch()
    
    # Special handling for langchain and llamaindex (they don't use settings)
    if "langchain" in sys.modules:
        from weave.integrations.langchain.langchain import langchain_patcher
        langchain_patcher.undo_patch()
    if "llama_index" in sys.modules:
        from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
        llamaindex_patcher.undo_patch()
    
    # Undo patches for regular integrations
    for name, getter in patch_undoers.items():
        if name not in ["mcp"]:  # Skip mcp as we handled it above
            getter().undo_patch()
