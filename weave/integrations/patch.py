"""Explicit and implicit patching functions for each integration.

This module provides:
1. Explicit patch functions that users can call manually
2. Implicit patching for libraries imported before weave.init()
3. Import hook for automatic patching of libraries imported after weave.init()
"""

from __future__ import annotations

import importlib
import sys
import threading
from collections.abc import Callable
from importlib.abc import MetaPathFinder

from weave.trace.autopatch import IntegrationSettings
from weave.trace.settings import should_use_otel_v2

# Integrations that have actually been patched. Prevents double-patching
# when libraries are imported multiple times.
_PATCHED_INTEGRATIONS: set[str] = set()

# Integrations that another (higher-priority) integration has claimed and
# that should therefore be skipped. Example: ``patch_google_adk`` adds
# ``"google.genai"`` here because ADK's own OTel spans already cover
# google-genai calls, and double-logging would mean two spans per
# Gemini request.
#
# Membership semantics:
# - in ``_PATCHED_INTEGRATIONS`` → the patcher ran
# - in ``_SUPPRESSED_INTEGRATIONS`` → the patcher must not run
# - in both → impossible by construction (suppression guards run before
#   patcher attempts)
_SUPPRESSED_INTEGRATIONS: set[str] = set()

# Global reference to the import hook, so we can unregister it if needed
_IMPORT_HOOK: WeaveImportHook | None = None

# Guards _PATCHED_INTEGRATIONS, _IMPORT_HOOK, and attempt_patch calls.
_PATCH_LOCK = threading.RLock()


def _patch_integration(
    *,
    module_path: str,
    patcher_func_getter_name: str,
    triggering_symbols: list[str],
    settings: IntegrationSettings | None = None,
) -> None:
    """Helper to reduce boilerplate in patch functions.

    Args:
        module_path: The full module path to import from (e.g., "weave.integrations.openai.openai_sdk")
        get_patcher_func_name: The name of the patcher getter function (e.g., "get_openai_patcher")
        triggering_symbols: Symbols to add to _PATCHED_INTEGRATIONS on success (e.g. ["openai"])
        settings: Optional integration settings
    """
    # Double-checked locking: pre-check, import_module outside the lock to
    # avoid nesting it under Python's per-module import locks, then re-check
    # under the lock before mutating. Both checks also honor suppression — if
    # another integration has claimed this symbol, we defer.
    with _PATCH_LOCK:
        if any(
            name in _PATCHED_INTEGRATIONS or name in _SUPPRESSED_INTEGRATIONS
            for name in triggering_symbols
        ):
            return

    if settings is None:
        settings = IntegrationSettings()

    module = importlib.import_module(module_path)
    patcher_func = getattr(module, patcher_func_getter_name)
    patcher = patcher_func(settings)

    with _PATCH_LOCK:
        if any(
            name in _PATCHED_INTEGRATIONS or name in _SUPPRESSED_INTEGRATIONS
            for name in triggering_symbols
        ):
            return
        if patcher.attempt_patch():
            for name in triggering_symbols:
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
        module_path="weave.integrations.openai.openai_sdk",
        patcher_func_getter_name="get_openai_patcher",
        triggering_symbols=["openai"],
        settings=settings,
    )


def _dispatch_openai() -> None:
    """Implicit-patch entry for ``openai``.

    Under ``WEAVE_USE_OTEL_V2`` (now the default), openai itself is NOT patched.
    The Agents SDK integration is the system under observation and already
    exposes the LLM call data via ``ResponseSpanData`` / ``GenerationSpanData`` —
    instrumenting openai separately would dual-log every call from inside an
    agent. Direct (non-agent) calls to ``openai.*`` are temporarily untraced in
    OTel V2 mode.
    """
    if should_use_otel_v2():
        return
    patch_openai()


def patch_anthropic(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Anthropic."""
    _patch_integration(
        module_path="weave.integrations.anthropic.anthropic_sdk",
        patcher_func_getter_name="get_anthropic_patcher",
        triggering_symbols=["anthropic"],
        settings=settings,
    )


def patch_mistral(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Mistral."""
    _patch_integration(
        module_path="weave.integrations.mistral.mistral_sdk",
        patcher_func_getter_name="get_mistral_patcher",
        triggering_symbols=["mistralai"],
        settings=settings,
    )


def patch_groq(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Groq."""
    _patch_integration(
        module_path="weave.integrations.groq.groq_sdk",
        patcher_func_getter_name="get_groq_patcher",
        triggering_symbols=["groq"],
        settings=settings,
    )


def patch_litellm(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for LiteLLM."""
    _patch_integration(
        module_path="weave.integrations.litellm.litellm",
        patcher_func_getter_name="get_litellm_patcher",
        triggering_symbols=["litellm"],
        settings=settings,
    )


def patch_cerebras(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cerebras."""
    _patch_integration(
        module_path="weave.integrations.cerebras.cerebras_sdk",
        patcher_func_getter_name="get_cerebras_patcher",
        triggering_symbols=["cerebras"],
        settings=settings,
    )


def patch_cohere(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Cohere."""
    _patch_integration(
        module_path="weave.integrations.cohere.cohere_sdk",
        patcher_func_getter_name="get_cohere_patcher",
        triggering_symbols=["cohere"],
        settings=settings,
    )


def patch_google_genai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Generative AI."""
    _patch_integration(
        module_path="weave.integrations.google_genai.google_genai_sdk",
        patcher_func_getter_name="get_google_genai_patcher",
        triggering_symbols=["google.genai"],
        settings=settings,
    )


def patch_vertexai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Vertex AI."""
    _patch_integration(
        module_path="weave.integrations.vertexai.vertexai_sdk",
        patcher_func_getter_name="get_vertexai_patcher",
        triggering_symbols=["vertexai"],
        settings=settings,
    )


def patch_google_adk(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Google Agent Development Kit (ADK).

    ADK uses ``google.genai`` internally, and ADK's own OTel spans
    already cover the model calls Weave's ``google_genai`` integration
    targets. When ADK is patched we therefore suppress
    ``patch_google_genai`` to avoid double-logging the same Gemini
    request/response on the new agents pipeline and the legacy
    call-level integration.

    Note: the import hook currently matches only root modules, so
    ``import google.adk`` after ``weave.init()`` will *not* auto-trigger
    this patch (the root module ``google`` is not in the mapping).
    Either import ADK before calling ``weave.init()`` so
    ``implicit_patch()`` catches it, or call ``patch_google_adk()``
    explicitly after init. Follow-up work will extend the hook to match
    dotted paths.
    """
    _patch_integration(
        module_path="weave.integrations.google_adk.google_adk_sdk",
        patcher_func_getter_name="get_google_adk_patcher",
        triggering_symbols=["google.adk"],
        settings=settings,
    )
    # Only suppress google-genai if ADK actually patched (i.e.
    # ``settings.enabled`` wasn't False). Both wire names go in so
    # explicit calls and ``implicit_patch`` both defer.
    if "google.adk" in _PATCHED_INTEGRATIONS:
        _SUPPRESSED_INTEGRATIONS.add("google.genai")
        _SUPPRESSED_INTEGRATIONS.add("google.generativeai")


def patch_huggingface(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Hugging Face."""
    _patch_integration(
        module_path="weave.integrations.huggingface.huggingface_inference_client_sdk",
        patcher_func_getter_name="get_huggingface_patcher",
        triggering_symbols=["huggingface_hub"],
        settings=settings,
    )


def patch_instructor(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Instructor."""
    _patch_integration(
        module_path="weave.integrations.instructor.instructor_sdk",
        patcher_func_getter_name="get_instructor_patcher",
        triggering_symbols=["instructor"],
        settings=settings,
    )


def patch_dspy(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for DSPy."""
    _patch_integration(
        module_path="weave.integrations.dspy.dspy_sdk",
        patcher_func_getter_name="get_dspy_patcher",
        triggering_symbols=["dspy"],
        settings=settings,
    )


def patch_gepa(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for GEPA."""
    _patch_integration(
        module_path="weave.integrations.gepa.gepa_sdk",
        patcher_func_getter_name="get_gepa_patcher",
        triggering_symbols=["gepa"],
        settings=settings,
    )


def patch_crewai(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for CrewAI."""
    _patch_integration(
        module_path="weave.integrations.crewai",
        patcher_func_getter_name="get_crewai_patcher",
        triggering_symbols=["crewai", "crewai_tools"],
        settings=settings,
    )


def patch_notdiamond(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NotDiamond."""
    _patch_integration(
        module_path="weave.integrations.notdiamond.tracing",
        patcher_func_getter_name="get_notdiamond_patcher",
        triggering_symbols=["notdiamond"],
        settings=settings,
    )


def patch_fastmcp(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for FastMCP (Model Context Protocol)."""
    # Double-checked locking — see _patch_integration.
    with _PATCH_LOCK:
        if "mcp" in _PATCHED_INTEGRATIONS:
            return

    from weave.integrations.fastmcp import (
        get_fastmcp_client_patcher,
        get_fastmcp_server_patcher,
    )

    if settings is None:
        settings = IntegrationSettings()
    server_patcher = get_fastmcp_server_patcher(settings)
    client_patcher = get_fastmcp_client_patcher(settings)

    with _PATCH_LOCK:
        if "mcp" in _PATCHED_INTEGRATIONS:
            return
        server_patched = server_patcher.attempt_patch()
        client_patched = client_patcher.attempt_patch()
        if server_patched or client_patched:
            _PATCHED_INTEGRATIONS.add("mcp")


def patch_nvidia(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for NVIDIA AI endpoints."""
    _patch_integration(
        module_path="weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints",
        patcher_func_getter_name="get_nvidia_ai_patcher",
        triggering_symbols=["langchain_nvidia_ai_endpoints"],
        settings=settings,
    )


def patch_smolagents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for SmolAgents."""
    _patch_integration(
        module_path="weave.integrations.smolagents.smolagents_sdk",
        patcher_func_getter_name="get_smolagents_patcher",
        triggering_symbols=["smolagents"],
        settings=settings,
    )


def patch_openai_agents(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI Agents (calls-based processor)."""
    _patch_integration(
        module_path="weave.integrations.openai_agents.patcher",
        patcher_func_getter_name="get_openai_agents_patcher",
        triggering_symbols=["openai_agents"],
        settings=settings,
    )


def patch_openai_agents_otel(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave OTel tracing for OpenAI Agents (Agents-tab destination)."""
    _patch_integration(
        module_path="weave.integrations.openai_agents.patcher",
        patcher_func_getter_name="get_openai_agents_otel_patcher",
        triggering_symbols=["openai_agents_otel"],
        settings=settings,
    )


def _dispatch_openai_agents() -> None:
    """Implicit-patch entry: route to OTel processor when WEAVE_USE_OTEL_V2 is set.

    Explicit ``patch_openai_agents()`` / ``patch_openai_agents_otel()`` calls
    are unaffected — they always do exactly what their name says.
    """
    if should_use_otel_v2():
        patch_openai_agents_otel()
        return
    patch_openai_agents()


def patch_verdict(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verdict."""
    _patch_integration(
        module_path="weave.integrations.verdict.verdict_sdk",
        patcher_func_getter_name="get_verdict_patcher",
        triggering_symbols=["verdict"],
        settings=settings,
    )


def patch_verifiers(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Verifiers."""
    _patch_integration(
        module_path="weave.integrations.verifiers.verifiers",
        patcher_func_getter_name="get_verifiers_patcher",
        triggering_symbols=["verifiers"],
        settings=settings,
    )


def patch_autogen(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for AutoGen."""
    _patch_integration(
        module_path="weave.integrations.autogen",
        patcher_func_getter_name="get_autogen_patcher",
        triggering_symbols=["autogen"],
        settings=settings,
    )


def patch_claude_agent_sdk(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for Claude Agent SDK (calls-based)."""
    _patch_integration(
        module_path="weave.integrations.claude_agent_sdk",
        patcher_func_getter_name="get_claude_agent_sdk_patcher",
        triggering_symbols=["claude_agent_sdk"],
        settings=settings,
    )


def patch_claude_agent_sdk_otel(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave OTel tracing for Claude Agent SDK (Agents-tab destination)."""
    _patch_integration(
        module_path="weave.integrations.claude_agent_sdk.otel_integration",
        patcher_func_getter_name="get_claude_agent_sdk_otel_patcher",
        triggering_symbols=["claude_agent_sdk_otel"],
        settings=settings,
    )


def _dispatch_claude_agent_sdk() -> None:
    """Implicit-patch entry: route to OTel variant when WEAVE_USE_OTEL_V2 is set.

    Explicit ``patch_claude_agent_sdk()`` / ``patch_claude_agent_sdk_otel()``
    calls are unaffected — they always do exactly what their name says.
    """
    if should_use_otel_v2():
        patch_claude_agent_sdk_otel()
        return
    patch_claude_agent_sdk()


def patch_langchain() -> None:
    """Enable Weave tracing for LangChain."""
    # Double-checked locking — see _patch_integration.
    with _PATCH_LOCK:
        if "langchain" in _PATCHED_INTEGRATIONS:
            return

    from weave.integrations.langchain.langchain import langchain_patcher

    with _PATCH_LOCK:
        if "langchain" in _PATCHED_INTEGRATIONS:
            return
        if langchain_patcher.attempt_patch():
            _PATCHED_INTEGRATIONS.add("langchain")
            _PATCHED_INTEGRATIONS.add("langchain_core")


def patch_llamaindex() -> None:
    """Enable Weave tracing for LlamaIndex."""
    # Double-checked locking — see _patch_integration.
    with _PATCH_LOCK:
        if "llama_index" in _PATCHED_INTEGRATIONS:
            return

    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher

    with _PATCH_LOCK:
        if "llama_index" in _PATCHED_INTEGRATIONS:
            return
        if llamaindex_patcher.attempt_patch():
            _PATCHED_INTEGRATIONS.add("llama_index")


def patch_openai_realtime(settings: IntegrationSettings | None = None) -> None:
    """Enable Weave tracing for OpenAI Realtime."""
    _patch_integration(
        module_path="weave.integrations.openai_realtime",
        patcher_func_getter_name="get_openai_realtime_websocket_patcher",
        triggering_symbols=["openai_realtime"],
        settings=settings,
    )


# Mapping of module names to patch functions for implicit patching
# When a module is already imported, we'll automatically call its patch function

INTEGRATION_MODULE_MAPPING: dict[str, Callable[[], None]] = {
    "openai": _dispatch_openai,
    "anthropic": patch_anthropic,
    "mistralai": patch_mistral,
    "groq": patch_groq,
    "litellm": patch_litellm,
    "cerebras": patch_cerebras,
    "cohere": patch_cohere,
    # ADK must come before ``google.genai`` / ``google.generativeai``:
    # patching ADK suppresses google-genai (see ``patch_google_adk``), but
    # the suppression only takes effect if ADK is patched first.
    "google.adk": patch_google_adk,
    "google.generativeai": patch_google_genai,
    "google.genai": patch_google_genai,
    "vertexai": patch_vertexai,
    "huggingface_hub": patch_huggingface,
    "instructor": patch_instructor,
    "dspy": patch_dspy,
    "gepa": patch_gepa,
    "crewai": patch_crewai,
    "crewai_tools": patch_crewai,
    "notdiamond": patch_notdiamond,
    "mcp": patch_fastmcp,
    "langchain_nvidia_ai_endpoints": patch_nvidia,
    "smolagents": patch_smolagents,
    "agents": _dispatch_openai_agents,
    "claude_agent_sdk": _dispatch_claude_agent_sdk,
    "verdict": patch_verdict,
    "verifiers": patch_verifiers,
    "autogen": patch_autogen,
    "langchain": patch_langchain,
    "langchain_core": patch_langchain,
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
        module_name in INTEGRATION_MODULE_MAPPING
        and module_name not in _PATCHED_INTEGRATIONS
        and module_name not in _SUPPRESSED_INTEGRATIONS
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
        # Check if the module is already imported, not yet patched, and
        # not suppressed by a sibling integration (e.g. ADK suppresses
        # google.genai).
        if (
            module_name in sys.modules
            and module_name not in _PATCHED_INTEGRATIONS
            and module_name not in _SUPPRESSED_INTEGRATIONS
        ):
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

    global _IMPORT_HOOK  # noqa: PLW0603

    with _PATCH_LOCK:
        # Only register if not already registered
        if _IMPORT_HOOK is None:
            _IMPORT_HOOK = WeaveImportHook()
            # Insert at the beginning of meta_path to ensure we intercept imports early
            sys.meta_path.insert(0, _IMPORT_HOOK)


def unregister_import_hook() -> None:
    """Unregister the import hook (useful for testing or cleanup)."""
    global _IMPORT_HOOK  # noqa: PLW0603

    with _PATCH_LOCK:
        if _IMPORT_HOOK is not None:
            try:
                sys.meta_path.remove(_IMPORT_HOOK)
            except ValueError:
                pass  # Already removed
            _IMPORT_HOOK = None


def reset_patched_integrations() -> None:
    """Reset the patched + suppressed integration sets (useful for testing)."""
    global _PATCHED_INTEGRATIONS, _SUPPRESSED_INTEGRATIONS  # noqa: PLW0603
    with _PATCH_LOCK:
        _PATCHED_INTEGRATIONS = set()
        _SUPPRESSED_INTEGRATIONS = set()
