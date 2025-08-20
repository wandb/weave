"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

import importlib
import os
import sys
import threading
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field, validate_call

from weave.trace.weave_client import Call

# Debug flag - can be set via environment variable WEAVE_DEBUG_AUTOPATCH=1
_DEBUG_AUTOPATCH = os.environ.get("WEAVE_DEBUG_AUTOPATCH", "").lower() in ("1", "true", "yes")

# Track which integrations have been patched
_patched_integrations = set()
_patch_lock = threading.Lock()

# Global settings for autopatching
_autopatch_settings: Optional['AutopatchSettings'] = None


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


# Mapping of integration names to their module paths and patcher functions
_INTEGRATION_CONFIGS = {
    "openai": {
        "module": "weave.integrations.openai.openai_sdk",
        "patcher_func": "get_openai_patcher",
        "trigger_modules": ["openai"],  # When these modules are imported, trigger patching
    },
    "mistral": {
        "module": "weave.integrations.mistral.mistral_sdk",
        "patcher_func": "get_mistral_patcher",
        "trigger_modules": ["mistralai"],
    },
    "mcp_server": {
        "module": "weave.integrations.mcp",
        "patcher_func": "get_mcp_server_patcher",
        "settings_attr": "mcp",
        "trigger_modules": ["mcp"],
    },
    "mcp_client": {
        "module": "weave.integrations.mcp",
        "patcher_func": "get_mcp_client_patcher",
        "settings_attr": "mcp",
        "trigger_modules": ["mcp"],
    },
    "litellm": {
        "module": "weave.integrations.litellm.litellm",
        "patcher_func": "get_litellm_patcher",
        "trigger_modules": ["litellm"],
    },
    "anthropic": {
        "module": "weave.integrations.anthropic.anthropic_sdk",
        "patcher_func": "get_anthropic_patcher",
        "trigger_modules": ["anthropic"],
    },
    "groq": {
        "module": "weave.integrations.groq.groq_sdk",
        "patcher_func": "get_groq_patcher",
        "trigger_modules": ["groq"],
    },
    "instructor": {
        "module": "weave.integrations.instructor.instructor_sdk",
        "patcher_func": "get_instructor_patcher",
        "trigger_modules": ["instructor"],
    },
    "dspy": {
        "module": "weave.integrations.dspy.dspy_sdk",
        "patcher_func": "get_dspy_patcher",
        "trigger_modules": ["dspy"],
    },
    "cerebras": {
        "module": "weave.integrations.cerebras.cerebras_sdk",
        "patcher_func": "get_cerebras_patcher",
        "trigger_modules": ["cerebras"],
    },
    "cohere": {
        "module": "weave.integrations.cohere.cohere_sdk",
        "patcher_func": "get_cohere_patcher",
        "trigger_modules": ["cohere"],
    },
    "google_genai": {
        "module": "weave.integrations.google_genai.google_genai_sdk",
        "patcher_func": "get_google_genai_patcher",
        "settings_attr": "google_genai_sdk",
        "trigger_modules": ["google.generativeai"],
    },
    "crewai": {
        "module": "weave.integrations.crewai",
        "patcher_func": "get_crewai_patcher",
        "trigger_modules": ["crewai"],
    },
    "notdiamond": {
        "module": "weave.integrations.notdiamond.tracing",
        "patcher_func": "get_notdiamond_patcher",
        "trigger_modules": ["notdiamond"],
    },
    "vertexai": {
        "module": "weave.integrations.vertexai.vertexai_sdk",
        "patcher_func": "get_vertexai_patcher",
        "trigger_modules": ["vertexai"],
    },
    "chatnvidia": {
        "module": "weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints",
        "patcher_func": "get_nvidia_ai_patcher",
        "trigger_modules": ["langchain_nvidia_ai_endpoints"],
    },
    "huggingface": {
        "module": "weave.integrations.huggingface.huggingface_inference_client_sdk",
        "patcher_func": "get_huggingface_patcher",
        "trigger_modules": ["huggingface_hub"],
    },
    "smolagents": {
        "module": "weave.integrations.smolagents.smolagents_sdk",
        "patcher_func": "get_smolagents_patcher",
        "trigger_modules": ["smolagents"],
    },
    "openai_agents": {
        "module": "weave.integrations.openai_agents.openai_agents",
        "patcher_func": "get_openai_agents_patcher",
        "trigger_modules": ["swarm"],
    },
    "verdict": {
        "module": "weave.integrations.verdict.verdict_sdk",
        "patcher_func": "get_verdict_patcher",
        "trigger_modules": ["verdict"],
    },
    "langchain": {
        "module": "weave.integrations.langchain.langchain",
        "patcher_func": None,  # Uses module.langchain_patcher directly
        "trigger_modules": ["langchain"],
    },
    "llamaindex": {
        "module": "weave.integrations.llamaindex.llamaindex",
        "patcher_func": None,  # Uses module.llamaindex_patcher directly
        "trigger_modules": ["llama_index"],
    },
    "autogen": {
        "module": "weave.integrations.autogen",
        "patcher_func": "get_autogen_patcher",
        "trigger_modules": ["autogen"],
    },
}


def _lazy_load_and_patch(integration_name: str, settings: Optional[IntegrationSettings] = None):
    """Lazily load an integration module and attempt to patch it."""
    with _patch_lock:
        # Check if already patched
        if integration_name in _patched_integrations:
            if _DEBUG_AUTOPATCH:
                print(f"[WEAVE AUTOPATCH] {integration_name} already patched, skipping")
            return
        
        if _DEBUG_AUTOPATCH:
            print(f"[WEAVE AUTOPATCH] Patching {integration_name}...")
        
        config = _INTEGRATION_CONFIGS.get(integration_name)
        if not config:
            raise ValueError(f"Unknown integration: {integration_name}")
        
        module = importlib.import_module(config["module"])
        
        if config["patcher_func"]:
            patcher_func = getattr(module, config["patcher_func"])
            if settings is not None:
                patcher = patcher_func(settings)
            else:
                patcher = patcher_func()
            patcher.attempt_patch()
        else:
            # Special case for langchain and llamaindex
            if integration_name == "langchain":
                module.langchain_patcher.attempt_patch()
            elif integration_name == "llamaindex":
                module.llamaindex_patcher.attempt_patch()
        
        # Track that this integration has been patched
        _patched_integrations.add(integration_name)
        if _DEBUG_AUTOPATCH:
            print(f"[WEAVE AUTOPATCH] Successfully patched {integration_name}")


def _lazy_load_and_unpatch(integration_name: str):
    """Lazily load an integration module and undo its patches."""
    with _patch_lock:
        # Only unpatch if it was patched
        if integration_name not in _patched_integrations:
            return
            
        config = _INTEGRATION_CONFIGS.get(integration_name)
        if not config:
            raise ValueError(f"Unknown integration: {integration_name}")
        
        module = importlib.import_module(config["module"])
        
        if config["patcher_func"]:
            patcher_func = getattr(module, config["patcher_func"])
            patcher = patcher_func()
            patcher.undo_patch()
        else:
            # Special case for langchain and llamaindex
            if integration_name == "langchain":
                module.langchain_patcher.undo_patch()
            elif integration_name == "llamaindex":
                module.llamaindex_patcher.undo_patch()
        
        # Remove from tracked patched integrations
        _patched_integrations.discard(integration_name)


def _check_and_patch_if_needed(called_from_init=False):
    """Check if any libraries that need patching have been imported and patch them."""
    global _autopatch_settings
    
    if _autopatch_settings is None or _autopatch_settings.disable_autopatch:
        return
    
    # Check each integration to see if its trigger modules are imported
    for integration_name, config in _INTEGRATION_CONFIGS.items():
        # Skip if already patched
        if integration_name in _patched_integrations:
            continue
            
        # Check if any trigger modules are imported
        trigger_modules = config.get("trigger_modules", [])
        for trigger_module in trigger_modules:
            if trigger_module in sys.modules:
                if _DEBUG_AUTOPATCH:
                    if called_from_init:
                        # This is problematic - library was imported before weave.init()
                        print(f"[WEAVE AUTOPATCH] WARNING: {trigger_module} was already imported before weave.init()!")
                        print(f"[WEAVE AUTOPATCH]          This means patching happens immediately instead of on-demand.")
                        print(f"[WEAVE AUTOPATCH]          Consider importing {trigger_module} after weave.init() for better performance.")
                    print(f"[WEAVE AUTOPATCH] Detected {trigger_module} import, checking if {integration_name} should be patched")
                
                # The library is imported, check if we should patch it
                settings_attr = config.get("settings_attr", integration_name)
                
                # Skip mcp_server and mcp_client special handling
                if integration_name in ["mcp_server", "mcp_client"]:
                    settings_attr = "mcp"
                
                # Get the settings for this integration
                integration_settings = getattr(_autopatch_settings, settings_attr, None)
                
                # Only patch if enabled
                if integration_settings and integration_settings.enabled:
                    _lazy_load_and_patch(integration_name, integration_settings)
                    break  # Once we've found a trigger module, no need to check others


# Custom import hook to detect when libraries are imported
class WeaveImportHook:
    """Import hook that detects when specific libraries are imported and triggers patching."""
    
    def find_module(self, fullname, path=None):
        # Check if this is a library we're interested in
        for config in _INTEGRATION_CONFIGS.values():
            if fullname in config.get("trigger_modules", []):
                # Return ourselves as the loader
                return self
        return None
    
    def load_module(self, fullname):
        # If the module is already loaded, return it
        if fullname in sys.modules:
            return sys.modules[fullname]
        
        if _DEBUG_AUTOPATCH:
            print(f"[WEAVE AUTOPATCH] Import hook triggered for {fullname}")
        
        # Remove ourselves temporarily to avoid infinite recursion
        sys.meta_path.remove(self)
        try:
            # Import the module normally
            module = importlib.import_module(fullname)
            sys.modules[fullname] = module
            
            # After the module is imported, check if we need to patch anything
            _check_and_patch_if_needed(called_from_init=False)
            
            return module
        finally:
            # Re-add ourselves
            if self not in sys.meta_path:
                sys.meta_path.insert(0, self)


# Install the import hook when this module is imported
_import_hook = WeaveImportHook()


@validate_call
def autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    """Configure autopatch settings and enable the import hook.
    
    This function no longer immediately patches integrations. Instead, it:
    1. Stores the settings for later use
    2. Installs an import hook that will patch integrations when they are first imported
    3. Checks if any integrations are already imported and patches them if needed
    """
    global _autopatch_settings
    
    if settings is None:
        settings = AutopatchSettings()
    
    _autopatch_settings = settings
    
    if settings.disable_autopatch:
        # Remove the import hook if autopatch is disabled
        if _import_hook in sys.meta_path:
            if _DEBUG_AUTOPATCH:
                print("[WEAVE AUTOPATCH] Removing import hook (autopatch disabled)")
            sys.meta_path.remove(_import_hook)
        return
    
    # Install the import hook if not already installed
    if _import_hook not in sys.meta_path:
        if _DEBUG_AUTOPATCH:
            print("[WEAVE AUTOPATCH] Installing import hook for on-demand patching")
        sys.meta_path.insert(0, _import_hook)
    elif _DEBUG_AUTOPATCH:
        print("[WEAVE AUTOPATCH] Import hook already installed")
    
    # Check if any libraries are already imported and patch them
    if _DEBUG_AUTOPATCH:
        print("[WEAVE AUTOPATCH] Checking for already-imported libraries...")
    _check_and_patch_if_needed(called_from_init=True)


def reset_autopatch() -> None:
    """Reset autopatch by unpatching all patched integrations and removing the import hook."""
    global _autopatch_settings
    
    # Remove the import hook
    if _import_hook in sys.meta_path:
        sys.meta_path.remove(_import_hook)
    
    # Only unpatch integrations that were actually patched
    # Create a copy of the set to avoid modifying while iterating
    patched = list(_patched_integrations)
    
    for integration_name in patched:
        _lazy_load_and_unpatch(integration_name)
    
    # Clear the settings
    _autopatch_settings = None