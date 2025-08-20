"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

import importlib
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field, validate_call

from weave.trace.weave_client import Call

# Track which integrations have been patched
_patched_integrations = set()


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
    },
    "mistral": {
        "module": "weave.integrations.mistral.mistral_sdk",
        "patcher_func": "get_mistral_patcher",
    },
    "mcp_server": {
        "module": "weave.integrations.mcp",
        "patcher_func": "get_mcp_server_patcher",
        "settings_attr": "mcp",
    },
    "mcp_client": {
        "module": "weave.integrations.mcp",
        "patcher_func": "get_mcp_client_patcher",
        "settings_attr": "mcp",
    },
    "litellm": {
        "module": "weave.integrations.litellm.litellm",
        "patcher_func": "get_litellm_patcher",
    },
    "anthropic": {
        "module": "weave.integrations.anthropic.anthropic_sdk",
        "patcher_func": "get_anthropic_patcher",
    },
    "groq": {
        "module": "weave.integrations.groq.groq_sdk",
        "patcher_func": "get_groq_patcher",
    },
    "instructor": {
        "module": "weave.integrations.instructor.instructor_sdk",
        "patcher_func": "get_instructor_patcher",
    },
    "dspy": {
        "module": "weave.integrations.dspy.dspy_sdk",
        "patcher_func": "get_dspy_patcher",
    },
    "cerebras": {
        "module": "weave.integrations.cerebras.cerebras_sdk",
        "patcher_func": "get_cerebras_patcher",
    },
    "cohere": {
        "module": "weave.integrations.cohere.cohere_sdk",
        "patcher_func": "get_cohere_patcher",
    },
    "google_genai": {
        "module": "weave.integrations.google_genai.google_genai_sdk",
        "patcher_func": "get_google_genai_patcher",
        "settings_attr": "google_genai_sdk",
    },
    "crewai": {
        "module": "weave.integrations.crewai",
        "patcher_func": "get_crewai_patcher",
    },
    "notdiamond": {
        "module": "weave.integrations.notdiamond.tracing",
        "patcher_func": "get_notdiamond_patcher",
    },
    "vertexai": {
        "module": "weave.integrations.vertexai.vertexai_sdk",
        "patcher_func": "get_vertexai_patcher",
    },
    "chatnvidia": {
        "module": "weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints",
        "patcher_func": "get_nvidia_ai_patcher",
    },
    "huggingface": {
        "module": "weave.integrations.huggingface.huggingface_inference_client_sdk",
        "patcher_func": "get_huggingface_patcher",
    },
    "smolagents": {
        "module": "weave.integrations.smolagents.smolagents_sdk",
        "patcher_func": "get_smolagents_patcher",
    },
    "openai_agents": {
        "module": "weave.integrations.openai_agents.openai_agents",
        "patcher_func": "get_openai_agents_patcher",
    },
    "verdict": {
        "module": "weave.integrations.verdict.verdict_sdk",
        "patcher_func": "get_verdict_patcher",
    },
    "langchain": {
        "module": "weave.integrations.langchain.langchain",
        "patcher_func": None,  # Uses module.langchain_patcher directly
    },
    "llamaindex": {
        "module": "weave.integrations.llamaindex.llamaindex",
        "patcher_func": None,  # Uses module.llamaindex_patcher directly
    },
    "autogen": {
        "module": "weave.integrations.autogen",
        "patcher_func": "get_autogen_patcher",
    },
}


def _lazy_load_and_patch(integration_name: str, settings: Optional[IntegrationSettings] = None):
    """Lazily load an integration module and attempt to patch it."""
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


def _lazy_load_and_unpatch(integration_name: str):
    """Lazily load an integration module and undo its patches."""
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


@validate_call
def autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    if settings is None:
        settings = AutopatchSettings()
    if settings.disable_autopatch:
        return

    # Define the order of patching
    patch_order = [
        "openai",
        "mistral",
        "mcp_server",
        "mcp_client",
        "litellm",
        "anthropic",
        "groq",
        "instructor",
        "dspy",
        "cerebras",
        "cohere",
        "google_genai",
        "crewai",
        "notdiamond",
        "vertexai",
        "chatnvidia",
        "huggingface",
        "smolagents",
        "openai_agents",
        "verdict",
        "langchain",
        "llamaindex",
        "autogen",
    ]
    
    for integration_name in patch_order:
        # Get the settings attribute name (usually same as integration name, but not always)
        config = _INTEGRATION_CONFIGS.get(integration_name)
        if not config:
            continue
            
        settings_attr = config.get("settings_attr", integration_name)
        
        # Skip mcp_server and mcp_client special handling
        if integration_name in ["mcp_server", "mcp_client"]:
            settings_attr = "mcp"
        
        # Get the settings for this integration
        integration_settings = getattr(settings, settings_attr, None)
        
        # Only patch if enabled
        if integration_settings and integration_settings.enabled:
            _lazy_load_and_patch(integration_name, integration_settings)


def reset_autopatch() -> None:
    # Only unpatch integrations that were actually patched
    # Create a copy of the set to avoid modifying while iterating
    patched = list(_patched_integrations)
    
    for integration_name in patched:
        _lazy_load_and_unpatch(integration_name)