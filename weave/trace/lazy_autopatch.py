"""Lazy auto-patching with import hooks.

This module provides a mechanism to patch integrations lazily when they are imported,
rather than eagerly at initialization time.
"""

import importlib
import importlib.util
import logging
import sys
from typing import Any, Callable, Dict, Optional, Set

from weave.trace.autopatch import AutopatchSettings, IntegrationSettings

logger = logging.getLogger(__name__)

# Mapping of module names to their patcher factories
INTEGRATION_PATCHERS: Dict[str, Callable[[IntegrationSettings], Any]] = {
    "openai": lambda settings: _lazy_import(
        "weave.integrations.openai.openai_sdk", "get_openai_patcher", settings
    ),
    "anthropic": lambda settings: _lazy_import(
        "weave.integrations.anthropic.anthropic_sdk", "get_anthropic_patcher", settings
    ),
    "mistralai": lambda settings: _lazy_import(
        "weave.integrations.mistral.mistral_sdk", "get_mistral_patcher", settings
    ),
    "litellm": lambda settings: _lazy_import(
        "weave.integrations.litellm.litellm", "get_litellm_patcher", settings
    ),
    "groq": lambda settings: _lazy_import(
        "weave.integrations.groq.groq_sdk", "get_groq_patcher", settings
    ),
    "instructor": lambda settings: _lazy_import(
        "weave.integrations.instructor.instructor_sdk",
        "get_instructor_patcher",
        settings,
    ),
    "dspy": lambda settings: _lazy_import(
        "weave.integrations.dspy.dspy_sdk", "get_dspy_patcher", settings
    ),
    "cerebras": lambda settings: _lazy_import(
        "weave.integrations.cerebras.cerebras_sdk", "get_cerebras_patcher", settings
    ),
    "cohere": lambda settings: _lazy_import(
        "weave.integrations.cohere.cohere_sdk", "get_cohere_patcher", settings
    ),
    "google": lambda settings: _lazy_import(
        "weave.integrations.google_genai.google_genai_sdk",
        "get_google_genai_patcher",
        settings,
    ),
    "crewai": lambda settings: _lazy_import(
        "weave.integrations.crewai", "get_crewai_patcher", settings
    ),
    "notdiamond": lambda settings: _lazy_import(
        "weave.integrations.notdiamond.tracing", "get_notdiamond_patcher", settings
    ),
    "vertexai": lambda settings: _lazy_import(
        "weave.integrations.vertexai.vertexai_sdk", "get_vertexai_patcher", settings
    ),
    "langchain_nvidia_ai_endpoints": lambda settings: _lazy_import(
        "weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints",
        "get_nvidia_ai_patcher",
        settings,
    ),
    "huggingface_hub": lambda settings: _lazy_import(
        "weave.integrations.huggingface.huggingface_inference_client_sdk",
        "get_huggingface_patcher",
        settings,
    ),
    "smolagents": lambda settings: _lazy_import(
        "weave.integrations.smolagents.smolagents_sdk",
        "get_smolagents_patcher",
        settings,
    ),
    "verdict": lambda settings: _lazy_import(
        "weave.integrations.verdict.verdict_sdk", "get_verdict_patcher", settings
    ),
    "autogen": lambda settings: _lazy_import(
        "weave.integrations.autogen", "get_autogen_patcher", settings
    ),
    "langchain": lambda settings: _lazy_import(
        "weave.integrations.langchain.langchain",
        "langchain_patcher",
        None,
        return_directly=True,
    ),
    "llama_index": lambda settings: _lazy_import(
        "weave.integrations.llamaindex.llamaindex",
        "llamaindex_patcher",
        None,
        return_directly=True,
    ),
    "mcp": lambda settings: [
        _lazy_import("weave.integrations.mcp", "get_mcp_server_patcher", settings),
        _lazy_import("weave.integrations.mcp", "get_mcp_client_patcher", settings),
    ],
    "swarm": lambda settings: _lazy_import(
        "weave.integrations.openai_agents.openai_agents",
        "get_openai_agents_patcher",
        settings,
    ),
}


def _lazy_import(
    module_path: str, factory_name: str, settings: Any, return_directly: bool = False
):
    """Lazily import and return a patcher factory."""
    module = importlib.import_module(module_path)
    factory = getattr(module, factory_name)
    if return_directly:
        return factory
    return factory(settings) if settings is not None else factory()


class WeaveImportHook:
    """Import hook that patches modules when they are imported."""

    def __init__(self, settings: AutopatchSettings):
        self.settings = settings
        self.patched_modules: Set[str] = set()
        self.enabled = not settings.disable_autopatch

    def find_module(
        self, fullname: str, path: Optional[str] = None
    ) -> Optional["WeaveImportHook"]:
        """Check if this module should be patched."""
        if not self.enabled:
            return None

        # Check if this module is one we want to patch
        if fullname in INTEGRATION_PATCHERS and fullname not in self.patched_modules:
            return self

        return None

    def find_spec(self, fullname: str, path: Any, target: Any = None) -> Any:
        """Modern import hook method (Python 3.4+)."""
        return None

    def load_module(self, fullname: str) -> Any:
        """Load and patch the module."""
        # Check if module is already loaded
        if fullname in sys.modules:
            module = sys.modules[fullname]
        else:
            # Load the module normally
            spec = importlib.util.find_spec(fullname)
            if spec is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[fullname] = module
            if spec.loader:
                spec.loader.exec_module(module)

        # Apply patches if not already done
        if fullname not in self.patched_modules:
            self._patch_module(fullname)
            self.patched_modules.add(fullname)

        return module

    def _patch_module(self, module_name: str) -> None:
        """Apply patches to a specific module."""
        try:
            # Get the appropriate settings for this integration
            settings_map = {
                "openai": self.settings.openai,
                "anthropic": self.settings.anthropic,
                "mistralai": self.settings.mistral,
                "litellm": self.settings.litellm,
                "groq": self.settings.groq,
                "instructor": self.settings.instructor,
                "dspy": self.settings.dspy,
                "cerebras": self.settings.cerebras,
                "cohere": self.settings.cohere,
                "google": self.settings.google_genai_sdk,
                "crewai": self.settings.crewai,
                "notdiamond": self.settings.notdiamond,
                "vertexai": self.settings.vertexai,
                "langchain_nvidia_ai_endpoints": self.settings.chatnvidia,
                "huggingface_hub": self.settings.huggingface,
                "smolagents": self.settings.smolagents,
                "verdict": self.settings.verdict,
                "autogen": self.settings.autogen,
                "mcp": self.settings.mcp,
                "swarm": self.settings.openai_agents,
                "langchain": IntegrationSettings(),  # Uses default settings
                "llama_index": IntegrationSettings(),  # Uses default settings
            }

            integration_settings = settings_map.get(module_name)
            if integration_settings and integration_settings.enabled:
                patcher_factory = INTEGRATION_PATCHERS.get(module_name)
                if patcher_factory:
                    patchers = patcher_factory(integration_settings)
                    # Handle cases where multiple patchers are returned
                    if isinstance(patchers, list):
                        for patcher in patchers:
                            patcher.attempt_patch()
                    else:
                        patchers.attempt_patch()
                    logger.debug(f"Applied patches to {module_name}")
        except Exception as e:
            logger.warning(f"Failed to patch {module_name}: {e}")


def setup_lazy_autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    """Set up lazy auto-patching with import hooks.

    This function checks which modules are already imported and patches them immediately,
    then sets up import hooks to patch modules that haven't been imported yet.
    """
    if settings is None:
        settings = AutopatchSettings()

    if settings.disable_autopatch:
        return

    # Check which modules are already imported and patch them
    for module_name in INTEGRATION_PATCHERS:
        if module_name in sys.modules:
            logger.debug(f"Module {module_name} already imported, patching now")
            _patch_already_imported_module(module_name, settings)

    # Set up import hook for modules not yet imported
    hook = WeaveImportHook(settings)
    if hook not in sys.meta_path:
        sys.meta_path.insert(0, hook)


def _patch_already_imported_module(
    module_name: str, settings: AutopatchSettings
) -> None:
    """Patch a module that has already been imported."""
    settings_map = {
        "openai": settings.openai,
        "anthropic": settings.anthropic,
        "mistralai": settings.mistral,
        "litellm": settings.litellm,
        "groq": settings.groq,
        "instructor": settings.instructor,
        "dspy": settings.dspy,
        "cerebras": settings.cerebras,
        "cohere": settings.cohere,
        "google": settings.google_genai_sdk,
        "crewai": settings.crewai,
        "notdiamond": settings.notdiamond,
        "vertexai": settings.vertexai,
        "langchain_nvidia_ai_endpoints": settings.chatnvidia,
        "huggingface_hub": settings.huggingface,
        "smolagents": settings.smolagents,
        "verdict": settings.verdict,
        "autogen": settings.autogen,
        "mcp": settings.mcp,
        "swarm": settings.openai_agents,
        "langchain": IntegrationSettings(),
        "llama_index": IntegrationSettings(),
    }

    integration_settings = settings_map.get(module_name)
    if integration_settings and integration_settings.enabled:
        try:
            patcher_factory = INTEGRATION_PATCHERS.get(module_name)
            if patcher_factory:
                patchers = patcher_factory(integration_settings)
                if isinstance(patchers, list):
                    for patcher in patchers:
                        patcher.attempt_patch()
                else:
                    patchers.attempt_patch()
                logger.debug(
                    f"Applied patches to already imported module {module_name}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to patch already imported module {module_name}: {e}"
            )


def teardown_lazy_autopatch() -> None:
    """Remove import hooks and reset patched modules."""
    # Remove our import hook from sys.meta_path
    sys.meta_path = [
        hook for hook in sys.meta_path if not isinstance(hook, WeaveImportHook)
    ]
