"""Explicit patching functions for each integration.

Instead of automatic patching, users must explicitly call these functions
to enable tracing for specific integrations.
"""

import sys
from typing import Callable, Optional

from weave.trace.autopatch import IntegrationSettings


def patch_openai(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for OpenAI.

    This must be called after `weave.init()` to enable OpenAI tracing.

    Example:
        import weave
        weave.init("my-project")
        weave.integrations.patch_openai()
    """
    from weave.integrations.openai.openai_sdk import get_openai_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_openai_patcher(settings).attempt_patch()


def patch_anthropic(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Anthropic."""
    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_anthropic_patcher(settings).attempt_patch()


def patch_mistral(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Mistral."""
    from weave.integrations.mistral.mistral_sdk import get_mistral_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_mistral_patcher(settings).attempt_patch()


def patch_groq(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Groq."""
    from weave.integrations.groq.groq_sdk import get_groq_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_groq_patcher(settings).attempt_patch()


def patch_litellm(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for LiteLLM."""
    from weave.integrations.litellm.litellm import get_litellm_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_litellm_patcher(settings).attempt_patch()


def patch_cerebras(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Cerebras."""
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_cerebras_patcher(settings).attempt_patch()


def patch_cohere(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Cohere."""
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_cohere_patcher(settings).attempt_patch()


def patch_google_genai(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Google Generative AI."""
    from weave.integrations.google_genai.google_genai_sdk import (
        get_google_genai_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    get_google_genai_patcher(settings).attempt_patch()


def patch_vertexai(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Google Vertex AI."""
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_vertexai_patcher(settings).attempt_patch()


def patch_huggingface(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Hugging Face."""
    from weave.integrations.huggingface.huggingface_inference_client_sdk import (
        get_huggingface_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    get_huggingface_patcher(settings).attempt_patch()


def patch_instructor(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Instructor."""
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_instructor_patcher(settings).attempt_patch()


def patch_dspy(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for DSPy."""
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_dspy_patcher(settings).attempt_patch()


def patch_crewai(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for CrewAI."""
    from weave.integrations.crewai import get_crewai_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_crewai_patcher(settings).attempt_patch()


def patch_notdiamond(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for NotDiamond."""
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_notdiamond_patcher(settings).attempt_patch()


def patch_mcp(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for MCP (Model Context Protocol)."""
    from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_mcp_server_patcher(settings).attempt_patch()
    get_mcp_client_patcher(settings).attempt_patch()


def patch_nvidia(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for NVIDIA AI endpoints."""
    from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import (
        get_nvidia_ai_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    get_nvidia_ai_patcher(settings).attempt_patch()


def patch_smolagents(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for SmolAgents."""
    from weave.integrations.smolagents.smolagents_sdk import get_smolagents_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_smolagents_patcher(settings).attempt_patch()


def patch_openai_agents(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for OpenAI Agents."""
    from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_openai_agents_patcher(settings).attempt_patch()


def patch_verdict(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for Verdict."""
    from weave.integrations.verdict.verdict_sdk import get_verdict_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_verdict_patcher(settings).attempt_patch()


def patch_autogen(settings: Optional[IntegrationSettings] = None) -> None:
    """Enable Weave tracing for AutoGen."""
    from weave.integrations.autogen import get_autogen_patcher

    if settings is None:
        settings = IntegrationSettings()
    get_autogen_patcher(settings).attempt_patch()


def patch_langchain() -> None:
    """Enable Weave tracing for LangChain."""
    from weave.integrations.langchain.langchain import langchain_patcher

    langchain_patcher.attempt_patch()


def patch_llamaindex() -> None:
    """Enable Weave tracing for LlamaIndex."""
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher

    llamaindex_patcher.attempt_patch()


# Mapping of module names to patch functions for implicit patching
# When a module is already imported, we'll automatically call its patch function

INTEGRATION_MODULE_MAPPING: dict[str, Callable[[], None]] = {
    "openai": patch_openai,
    "anthropic": patch_anthropic,
    "mistralai": patch_mistral,
    "groq": patch_groq,
    "litellm": patch_litellm,
    "cerebras": patch_cerebras,
    "cohere": patch_cohere,
    "google.generativeai": patch_google_genai,
    "vertexai": patch_vertexai,
    "huggingface_hub": patch_huggingface,
    "instructor": patch_instructor,
    "dspy": patch_dspy,
    "crewai": patch_crewai,
    "crewai_tools": patch_crewai,
    "notdiamond": patch_notdiamond,
    "mcp": patch_mcp,
    "langchain_nvidia_ai_endpoints": patch_nvidia,
    "smolagents": patch_smolagents,
    "openai_agents": patch_openai_agents,
    "verdict": patch_verdict,
    "autogen": patch_autogen,
    "langchain": patch_langchain,
    "llama_index": patch_llamaindex,
}


def implicit_patch() -> None:
    """Check sys.modules and automatically patch any already-imported integrations.

    This function is called during weave.init() to enable implicit patching.
    If a library is already imported when weave.init() is called, we automatically
    patch it without requiring an explicit patch_X() call.
    """
    already_patched = set()

    for module_name, patch_func in INTEGRATION_MODULE_MAPPING.items():
        # Check if the module is already imported and not yet patched
        if module_name in sys.modules and patch_func not in already_patched:
            try:
                patch_func()
                already_patched.add(patch_func)
            except Exception:
                # Silently skip if patching fails - this maintains backward compatibility
                # and doesn't break existing code if an integration can't be patched
                pass
