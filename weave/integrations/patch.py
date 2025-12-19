"""Explicit and implicit patching functions for each integration.

This module provides:
1. Explicit patch functions that users can call manually
2. Implicit patching for libraries imported before weave.init()
3. Import hook for automatic patching of libraries imported after weave.init()
"""

import sys
from collections.abc import Callable
from importlib.abc import MetaPathFinder
from typing import Optional

from weave.trace.autopatch import IntegrationSettings

# Global set to track which integrations have been patched
# This prevents double-patching when libraries are imported multiple times
_PATCHED_INTEGRATIONS: set[str] = set()

# Global reference to the import hook, so we can unregister it if needed
_IMPORT_HOOK: Optional["WeaveImportHook"] = None

OPENAI_IMPORT_TARGET = "openai"
ANTHROPIC_IMPORT_TARGET = "anthropic"
MISTRALAI_IMPORT_TARGET = "mistralai"
GROQ_IMPORT_TARGET = "groq"
LITELLM_IMPORT_TARGET = "litellm"
CEREBRAS_IMPORT_TARGET = "cerebras"
COHERE_IMPORT_TARGET = "cohere"
GOOGLE_GENAI_IMPORT_TARGET = "google.genai"
VERTEXAI_IMPORT_TARGET = "vertexai"
HUGGINGFACE_HUB_IMPORT_TARGET = "huggingface_hub"
INSTRUCTOR_IMPORT_TARGET = "instructor"
DSPY_IMPORT_TARGET = "dspy"
CREWAI_IMPORT_TARGET = "crewai"
CREWAI_TOOLS_IMPORT_TARGET = "crewai_tools"
NOTDIAMOND_IMPORT_TARGET = "notdiamond"
MCP_IMPORT_TARGET = "mcp"
LANGCHAIN_NVIDIA_AI_ENDPOINTS_IMPORT_TARGET = "langchain_nvidia_ai_endpoints"
SMOLAGENTS_IMPORT_TARGET = "smolagents"
AGENTS_IMPORT_TARGET = "agents"
OPENAI_AGENTS_IMPORT_TARGET = "openai_agents"
VERDICT_IMPORT_TARGET = "verdict"
VERIFIERS_IMPORT_TARGET = "verifiers"
AUTOGEN_IMPORT_TARGET = "autogen"
LANGCHAIN_IMPORT_TARGET = "langchain"
LLAMA_INDEX_IMPORT_TARGET = "llama_index"
OPENAI_REALTIME_IMPORT_TARGET = "openai_realtime"


def patch_openai(settings: IntegrationSettings | None = None) -> None:
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
    if get_openai_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(OPENAI_IMPORT_TARGET)


def patch_anthropic(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Anthropic."""
    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_anthropic_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(ANTHROPIC_IMPORT_TARGET)


def patch_mistral(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Mistral."""
    from weave.integrations.mistral.mistral_sdk import get_mistral_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_mistral_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(MISTRALAI_IMPORT_TARGET)


def patch_groq(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Groq."""
    from weave.integrations.groq.groq_sdk import get_groq_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_groq_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(GROQ_IMPORT_TARGET)


def patch_litellm(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for LiteLLM."""
    from weave.integrations.litellm.litellm import get_litellm_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_litellm_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(LITELLM_IMPORT_TARGET)


def patch_cerebras(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cerebras."""
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_cerebras_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(CEREBRAS_IMPORT_TARGET)


def patch_cohere(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cohere."""
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_cohere_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(COHERE_IMPORT_TARGET)


def patch_google_genai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Generative AI."""
    from weave.integrations.google_genai.google_genai_sdk import (
        get_google_genai_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    if get_google_genai_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(GOOGLE_GENAI_IMPORT_TARGET)


def patch_vertexai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Vertex AI."""
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_vertexai_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(VERTEXAI_IMPORT_TARGET)


def patch_huggingface(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Hugging Face."""
    from weave.integrations.huggingface.huggingface_inference_client_sdk import (
        get_huggingface_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    if get_huggingface_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(HUGGINGFACE_HUB_IMPORT_TARGET)


def patch_instructor(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Instructor."""
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_instructor_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(INSTRUCTOR_IMPORT_TARGET)


def patch_dspy(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for DSPy."""
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_dspy_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(DSPY_IMPORT_TARGET)


def patch_crewai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for CrewAI."""
    from weave.integrations.crewai import get_crewai_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_crewai_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(CREWAI_IMPORT_TARGET)
        _PATCHED_INTEGRATIONS.add(CREWAI_TOOLS_IMPORT_TARGET)


def patch_notdiamond(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NotDiamond."""
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_notdiamond_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(NOTDIAMOND_IMPORT_TARGET)


def patch_mcp(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for MCP (Model Context Protocol)."""
    from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher

    if settings is None:
        settings = IntegrationSettings()
    server_patched = get_mcp_server_patcher(settings).attempt_patch()
    client_patched = get_mcp_client_patcher(settings).attempt_patch()
    if server_patched or client_patched:
        _PATCHED_INTEGRATIONS.add(MCP_IMPORT_TARGET)


def patch_nvidia(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NVIDIA AI endpoints."""
    from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import (
        get_nvidia_ai_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    if get_nvidia_ai_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(LANGCHAIN_NVIDIA_AI_ENDPOINTS_IMPORT_TARGET)


def patch_smolagents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for SmolAgents."""
    from weave.integrations.smolagents.smolagents_sdk import get_smolagents_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_smolagents_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(SMOLAGENTS_IMPORT_TARGET)


def patch_openai_agents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI Agents."""
    from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_openai_agents_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(OPENAI_AGENTS_IMPORT_TARGET)


def patch_verdict(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verdict."""
    from weave.integrations.verdict.verdict_sdk import get_verdict_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_verdict_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(VERDICT_IMPORT_TARGET)


def patch_verifiers(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verifiers."""
    from weave.integrations.verifiers.verifiers import get_verifiers_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_verifiers_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(VERIFIERS_IMPORT_TARGET)


def patch_autogen(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for AutoGen."""
    from weave.integrations.autogen import get_autogen_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_autogen_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(AUTOGEN_IMPORT_TARGET)


def patch_langchain() -> None:
    """Enable Weave tracing for LangChain."""
    from weave.integrations.langchain.langchain import langchain_patcher

    if langchain_patcher.attempt_patch():
        _PATCHED_INTEGRATIONS.add(LANGCHAIN_IMPORT_TARGET)


def patch_llamaindex() -> None:
    """Enable Weave tracing for LlamaIndex."""
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher

    if llamaindex_patcher.attempt_patch():
        _PATCHED_INTEGRATIONS.add(LLAMA_INDEX_IMPORT_TARGET)


def patch_openai_realtime(settings: IntegrationSettings | None = None) -> None:
    from weave.integrations.openai_realtime import get_openai_realtime_websocket_patcher

    if settings is None:
        settings = IntegrationSettings()
    if get_openai_realtime_websocket_patcher(settings).attempt_patch():
        _PATCHED_INTEGRATIONS.add(OPENAI_REALTIME_IMPORT_TARGET)


# Mapping of module names to patch functions for implicit patching
# When a module is already imported, we'll automatically call its patch function

INTEGRATION_MODULE_MAPPING: dict[str, Callable[[], None]] = {
    OPENAI_IMPORT_TARGET: patch_openai,
    ANTHROPIC_IMPORT_TARGET: patch_anthropic,
    MISTRALAI_IMPORT_TARGET: patch_mistral,
    GROQ_IMPORT_TARGET: patch_groq,
    LITELLM_IMPORT_TARGET: patch_litellm,
    CEREBRAS_IMPORT_TARGET: patch_cerebras,
    COHERE_IMPORT_TARGET: patch_cohere,
    GOOGLE_GENAI_IMPORT_TARGET: patch_google_genai,
    VERTEXAI_IMPORT_TARGET: patch_vertexai,
    HUGGINGFACE_HUB_IMPORT_TARGET: patch_huggingface,
    INSTRUCTOR_IMPORT_TARGET: patch_instructor,
    DSPY_IMPORT_TARGET: patch_dspy,
    CREWAI_IMPORT_TARGET: patch_crewai,
    CREWAI_TOOLS_IMPORT_TARGET: patch_crewai,
    NOTDIAMOND_IMPORT_TARGET: patch_notdiamond,
    MCP_IMPORT_TARGET: patch_mcp,
    LANGCHAIN_NVIDIA_AI_ENDPOINTS_IMPORT_TARGET: patch_nvidia,
    SMOLAGENTS_IMPORT_TARGET: patch_smolagents,
    AGENTS_IMPORT_TARGET: patch_openai_agents,
    VERDICT_IMPORT_TARGET: patch_verdict,
    VERIFIERS_IMPORT_TARGET: patch_verifiers,
    AUTOGEN_IMPORT_TARGET: patch_autogen,
    LANGCHAIN_IMPORT_TARGET: patch_langchain,
    LLAMA_INDEX_IMPORT_TARGET: patch_llamaindex,
    OPENAI_REALTIME_IMPORT_TARGET: patch_openai_realtime,
}


class WeaveImportHook(MetaPathFinder):
    """Import hook that automatically patches supported integrations when they are imported."""

    def find_spec(self, fullname, path, target=None):  # type: ignore
        """Called by Python's import system to find a module spec.

        We don't actually find or load modules - we just detect when a supported
        integration is being imported and schedule it for patching after import.
        """
        # Check if this is a root module we support (not a submodule)
        root_module = fullname.split(".")[0]

        # If this is one of our supported integrations and not yet patched,
        # we'll patch it after it's imported
        if (
            root_module in INTEGRATION_MODULE_MAPPING
            and root_module not in _PATCHED_INTEGRATIONS
        ):
            # We don't actually find the spec - let the normal import system do that
            # But we'll use a Loader wrapper to patch after import
            spec = None
            for finder in sys.meta_path:
                if finder is self:
                    continue
                if hasattr(finder, "find_spec"):
                    spec = finder.find_spec(fullname, path, target)
                    if spec is not None:
                        break

            if spec is not None and fullname == root_module:
                # Wrap the loader to patch after import
                spec.loader = PatchingLoader(spec.loader, root_module)
                return spec

        # Not our concern, let other finders handle it
        return None

    def find_module(self, fullname, path=None):  # type: ignore
        """Legacy method for backwards compatibility with older Python versions."""
        return None


class PatchingLoader:
    """Loader wrapper that patches an integration after it's imported."""

    def __init__(self, original_loader, module_name: str):  # type: ignore
        self.original_loader = original_loader
        self.module_name = module_name

    def load_module(self, fullname):  # type: ignore
        """Load the module using the original loader, then patch it."""
        # Use the original loader to actually load the module
        if hasattr(self.original_loader, "load_module"):
            module = self.original_loader.load_module(fullname)
        else:
            # Fallback for loaders that don't have load_module
            module = sys.modules.get(fullname)

        # Now patch it if it's the root module
        if fullname == self.module_name:
            _patch_if_needed(self.module_name)

        return module

    def exec_module(self, module):  # type: ignore
        """Execute the module using the original loader, then patch it."""
        # Use the original loader to execute the module
        if hasattr(self.original_loader, "exec_module"):
            self.original_loader.exec_module(module)

        # Now patch it if it's the root module
        if module.__name__ == self.module_name:
            _patch_if_needed(self.module_name)

    def create_module(self, spec):  # type: ignore
        """Delegate module creation to the original loader."""
        if hasattr(self.original_loader, "create_module"):
            return self.original_loader.create_module(spec)
        return None

    def __getattr__(self, name):  # type: ignore
        """Delegate any other attributes to the original loader."""
        return getattr(self.original_loader, name)


def _patch_if_needed(module_name: str) -> None:
    """Apply patching for a module if it hasn't been patched yet."""
    if (
        module_name not in _PATCHED_INTEGRATIONS
        and module_name in INTEGRATION_MODULE_MAPPING
    ):
        patch_func = INTEGRATION_MODULE_MAPPING[module_name]
        try:
            patch_func()
            _PATCHED_INTEGRATIONS.add(module_name)
        except Exception:
            # Silently skip if patching fails - this maintains backward compatibility
            # and doesn't break existing code if an integration can't be patched
            pass


def implicit_patch() -> None:
    """Check sys.modules and automatically patch any already-imported integrations.

    This function is called during weave.init() to enable implicit patching.
    If a library is already imported when weave.init() is called, we automatically
    patch it without requiring an explicit patch_X() call.

    This respects the implicitly_patch_integrations setting - if disabled, no automatic
    patching will occur.
    """
    from weave.trace.settings import should_implicitly_patch_integrations

    # Check if implicit patching is enabled
    if not should_implicitly_patch_integrations():
        return

    for module_name, patch_func in INTEGRATION_MODULE_MAPPING.items():
        # Check if the module is already imported and not yet patched
        if module_name in sys.modules and module_name not in _PATCHED_INTEGRATIONS:
            try:
                patch_func()
                _PATCHED_INTEGRATIONS.add(module_name)
            except Exception:
                # Silently skip if patching fails - this maintains backward compatibility
                # and doesn't break existing code if an integration can't be patched
                pass


def register_import_hook() -> None:
    """Register the import hook to automatically patch integrations imported after weave.init().

    This respects the implicitly_patch_integrations setting - if disabled, the import hook
    will not be registered.
    """
    from weave.trace.settings import should_implicitly_patch_integrations

    # Check if implicit patching is enabled
    if not should_implicitly_patch_integrations():
        return

    global _IMPORT_HOOK

    # Only register if not already registered
    if _IMPORT_HOOK is None:
        _IMPORT_HOOK = WeaveImportHook()
        # Insert at the beginning of meta_path to ensure we intercept imports early
        sys.meta_path.insert(0, _IMPORT_HOOK)


def unregister_import_hook() -> None:
    """Unregister the import hook (useful for testing or cleanup)."""
    global _IMPORT_HOOK

    if _IMPORT_HOOK is not None:
        try:
            sys.meta_path.remove(_IMPORT_HOOK)
        except ValueError:
            pass  # Already removed
        _IMPORT_HOOK = None


def reset_patched_integrations() -> None:
    """Reset the set of patched integrations (useful for testing)."""
    global _PATCHED_INTEGRATIONS
    _PATCHED_INTEGRATIONS = set()
