"""Explicit and implicit patching functions for each integration.

This module provides:
1. Explicit patch functions that users can call manually
2. Implicit patching for libraries imported before weave.init()
3. Import hook for automatic patching of libraries imported after weave.init()
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from importlib.abc import MetaPathFinder

from weave.trace.autopatch import IntegrationSettings

# Global set to track which integrations have been patched
# This prevents double-patching when libraries are imported multiple times
_PATCHED_INTEGRATIONS: set[str] = set()

# Global reference to the import hook, so we can unregister it if needed
_IMPORT_HOOK: WeaveImportHook | None = None


def _patch_integration(
    module_path: str,
    getter_name: str,
    integration_names: str | list[str],
    settings: IntegrationSettings | None = None,
) -> None:
    """Helper to reduce boilerplate in patch functions.

    Args:
        module_path: The full module path to import from (e.g., "weave.integrations.openai.openai_sdk")
        getter_name: The name of the patcher getter function (e.g., "get_openai_patcher")
        integration_names: Name(s) to add to _PATCHED_INTEGRATIONS on success
        settings: Optional integration settings
    """
    if settings is None:
        settings = IntegrationSettings()

    module = importlib.import_module(module_path)
    getter = getattr(module, getter_name)

    if getter(settings).attempt_patch():
        if isinstance(integration_names, str):
            _PATCHED_INTEGRATIONS.add(integration_names)
        else:
            for name in integration_names:
                _PATCHED_INTEGRATIONS.add(name)


def patch_openai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI.

    This must be called after `weave.init()` to enable OpenAI tracing.

    Example:
        import weave
        weave.init("my-project")
        weave.integrations.patch_openai()
    """
    _patch_integration(
        "weave.integrations.openai.openai_sdk", "get_openai_patcher", "openai", settings
    )


def patch_anthropic(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Anthropic."""
    _patch_integration(
        "weave.integrations.anthropic.anthropic_sdk",
        "get_anthropic_patcher",
        "anthropic",
        settings,
    )


def patch_mistral(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Mistral."""
    _patch_integration(
        "weave.integrations.mistral.mistral_sdk",
        "get_mistral_patcher",
        "mistralai",
        settings,
    )


def patch_groq(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Groq."""
    _patch_integration(
        "weave.integrations.groq.groq_sdk", "get_groq_patcher", "groq", settings
    )


def patch_litellm(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for LiteLLM."""
    _patch_integration(
        "weave.integrations.litellm.litellm", "get_litellm_patcher", "litellm", settings
    )


def patch_cerebras(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cerebras."""
    _patch_integration(
        "weave.integrations.cerebras.cerebras_sdk",
        "get_cerebras_patcher",
        "cerebras",
        settings,
    )


def patch_cohere(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cohere."""
    _patch_integration(
        "weave.integrations.cohere.cohere_sdk", "get_cohere_patcher", "cohere", settings
    )


def patch_google_genai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Generative AI."""
    _patch_integration(
        "weave.integrations.google_genai.google_genai_sdk",
        "get_google_genai_patcher",
        "google.genai",
        settings,
    )


def patch_vertexai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Vertex AI."""
    _patch_integration(
        "weave.integrations.vertexai.vertexai_sdk",
        "get_vertexai_patcher",
        "vertexai",
        settings,
    )


def patch_huggingface(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Hugging Face."""
    _patch_integration(
        "weave.integrations.huggingface.huggingface_inference_client_sdk",
        "get_huggingface_patcher",
        "huggingface_hub",
        settings,
    )


def patch_instructor(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Instructor."""
    _patch_integration(
        "weave.integrations.instructor.instructor_sdk",
        "get_instructor_patcher",
        "instructor",
        settings,
    )


def patch_dspy(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for DSPy."""
    _patch_integration(
        "weave.integrations.dspy.dspy_sdk", "get_dspy_patcher", "dspy", settings
    )


def patch_crewai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for CrewAI."""
    _patch_integration(
        "weave.integrations.crewai",
        "get_crewai_patcher",
        ["crewai", "crewai_tools"],
        settings,
    )


def patch_notdiamond(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NotDiamond."""
    _patch_integration(
        "weave.integrations.notdiamond.tracing",
        "get_notdiamond_patcher",
        "notdiamond",
        settings,
    )


def patch_mcp(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for MCP (Model Context Protocol)."""
    from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher

    if settings is None:
        settings = IntegrationSettings()
    server_patched = get_mcp_server_patcher(settings).attempt_patch()
    client_patched = get_mcp_client_patcher(settings).attempt_patch()
    if server_patched or client_patched:
        _PATCHED_INTEGRATIONS.add("mcp")


def patch_nvidia(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NVIDIA AI endpoints."""
    _patch_integration(
        "weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints",
        "get_nvidia_ai_patcher",
        "langchain_nvidia_ai_endpoints",
        settings,
    )


def patch_smolagents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for SmolAgents."""
    _patch_integration(
        "weave.integrations.smolagents.smolagents_sdk",
        "get_smolagents_patcher",
        "smolagents",
        settings,
    )


def patch_openai_agents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI Agents."""
    _patch_integration(
        "weave.integrations.openai_agents.openai_agents",
        "get_openai_agents_patcher",
        "openai_agents",
        settings,
    )


def patch_verdict(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verdict."""
    _patch_integration(
        "weave.integrations.verdict.verdict_sdk",
        "get_verdict_patcher",
        "verdict",
        settings,
    )


def patch_verifiers(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verifiers."""
    _patch_integration(
        "weave.integrations.verifiers.verifiers",
        "get_verifiers_patcher",
        "verifiers",
        settings,
    )


def patch_autogen(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for AutoGen."""
    _patch_integration(
        "weave.integrations.autogen", "get_autogen_patcher", "autogen", settings
    )


def patch_langchain() -> None:
    """Enable Weave tracing for LangChain."""
    from weave.integrations.langchain.langchain import langchain_patcher

    if langchain_patcher.attempt_patch():
        _PATCHED_INTEGRATIONS.add("langchain")


def patch_llamaindex() -> None:
    """Enable Weave tracing for LlamaIndex."""
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher

    if llamaindex_patcher.attempt_patch():
        _PATCHED_INTEGRATIONS.add("llama_index")


def patch_openai_realtime(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI Realtime."""
    _patch_integration(
        "weave.integrations.openai_realtime",
        "get_openai_realtime_websocket_patcher",
        "openai_realtime",
        settings,
    )


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
    "google.genai": patch_google_genai,
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
    "agents": patch_openai_agents,
    "verdict": patch_verdict,
    "verifiers": patch_verifiers,
    "autogen": patch_autogen,
    "langchain": patch_langchain,
    "llama_index": patch_llamaindex,
    "openai_realtime": patch_openai_realtime,
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
