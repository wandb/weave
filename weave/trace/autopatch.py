"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

import sys
from typing import Any, Callable, Dict, Optional, Union

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
    smolagents: IntegrationSettings = Field(default_factory=IntegrationSettings)
    verdict: IntegrationSettings = Field(default_factory=IntegrationSettings)
    autogen: IntegrationSettings = Field(default_factory=IntegrationSettings)


class LazyPatchManager:
    """Manages lazy patching of integrations."""
    
    def __init__(self):
        self._settings: Optional[AutopatchSettings] = None
        self._patched: Dict[str, bool] = {}
        self._original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        
    def setup(self, settings: AutopatchSettings) -> None:
        """Set up the lazy patching with given settings."""
        self._settings = settings
        if not settings.disable_autopatch:
            self._install_import_hook()
    
    def _install_import_hook(self) -> None:
        """Install the import hook to patch libraries lazily."""
        def custom_import(name, *args, **kwargs):
            module = self._original_import(name, *args, **kwargs)
            self._check_and_patch(name)
            return module
        
        if hasattr(__builtins__, '__import__'):
            __builtins__.__import__ = custom_import
        else:
            __builtins__['__import__'] = custom_import
    
    def _check_and_patch(self, module_name: str) -> None:
        """Check if a module needs patching and patch it if necessary."""
        if self._settings is None or self._settings.disable_autopatch:
            return
            
        # Map module names to their patch functions
        patch_map = {
            'openai': ('openai', self._patch_openai),
            'anthropic': ('anthropic', self._patch_anthropic),
            'mistral': ('mistral', self._patch_mistral),
            'mcp': ('mcp', self._patch_mcp),
            'litellm': ('litellm', self._patch_litellm),
            'groq': ('groq', self._patch_groq),
            'instructor': ('instructor', self._patch_instructor),
            'dspy': ('dspy', self._patch_dspy),
            'cerebras': ('cerebras', self._patch_cerebras),
            'cohere': ('cohere', self._patch_cohere),
            'google.generativeai': ('google_generativeai', self._patch_google_generativeai),
            'google.genai': ('google_genai_sdk', self._patch_google_genai),
            'crewai': ('crewai', self._patch_crewai),
            'notdiamond': ('notdiamond', self._patch_notdiamond),
            'vertexai': ('vertexai', self._patch_vertexai),
            'langchain_nvidia_ai_endpoints': ('chatnvidia', self._patch_nvidia),
            'huggingface_hub': ('huggingface', self._patch_huggingface),
            'smolagents': ('smolagents', self._patch_smolagents),
            'swarm': ('openai_agents', self._patch_openai_agents),
            'verdict': ('verdict', self._patch_verdict),
            'langchain': ('langchain', self._patch_langchain),
            'llama_index': ('llamaindex', self._patch_llamaindex),
            'autogen': ('autogen', self._patch_autogen),
        }
        
        # Check if this module or its parent needs patching
        for trigger_module, (setting_name, patch_func) in patch_map.items():
            if module_name == trigger_module or module_name.startswith(trigger_module + '.'):
                if setting_name not in self._patched:
                    self._patched[setting_name] = True
                    patch_func()
    
    def _patch_openai(self) -> None:
        if self._settings and self._settings.openai.enabled:
            from weave.integrations.openai.openai_sdk import get_openai_patcher
            get_openai_patcher(self._settings.openai).attempt_patch()
    
    def _patch_anthropic(self) -> None:
        if self._settings and self._settings.anthropic.enabled:
            from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
            get_anthropic_patcher(self._settings.anthropic).attempt_patch()
    
    def _patch_mistral(self) -> None:
        if self._settings and self._settings.mistral.enabled:
            from weave.integrations.mistral.mistral_sdk import get_mistral_patcher
            get_mistral_patcher(self._settings.mistral).attempt_patch()
    
    def _patch_mcp(self) -> None:
        if self._settings and self._settings.mcp.enabled:
            from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher
            get_mcp_server_patcher(self._settings.mcp).attempt_patch()
            get_mcp_client_patcher(self._settings.mcp).attempt_patch()
    
    def _patch_litellm(self) -> None:
        if self._settings and self._settings.litellm.enabled:
            from weave.integrations.litellm.litellm import get_litellm_patcher
            get_litellm_patcher(self._settings.litellm).attempt_patch()
    
    def _patch_groq(self) -> None:
        if self._settings and self._settings.groq.enabled:
            from weave.integrations.groq.groq_sdk import get_groq_patcher
            get_groq_patcher(self._settings.groq).attempt_patch()
    
    def _patch_instructor(self) -> None:
        if self._settings and self._settings.instructor.enabled:
            from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
            get_instructor_patcher(self._settings.instructor).attempt_patch()
    
    def _patch_dspy(self) -> None:
        if self._settings and self._settings.dspy.enabled:
            from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
            get_dspy_patcher(self._settings.dspy).attempt_patch()
    
    def _patch_cerebras(self) -> None:
        if self._settings and self._settings.cerebras.enabled:
            from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
            get_cerebras_patcher(self._settings.cerebras).attempt_patch()
    
    def _patch_cohere(self) -> None:
        if self._settings and self._settings.cohere.enabled:
            from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
            get_cohere_patcher(self._settings.cohere).attempt_patch()
    
    def _patch_google_generativeai(self) -> None:
        if self._settings and self._settings.google_generativeai.enabled:
            from weave.integrations.google_ai_studio.google_ai_studio_sdk import get_google_generativeai_patcher
            get_google_generativeai_patcher(self._settings.google_generativeai).attempt_patch()
    
    def _patch_google_genai(self) -> None:
        if self._settings and self._settings.google_genai_sdk.enabled:
            from weave.integrations.google_genai.google_genai_sdk import get_google_genai_patcher
            get_google_genai_patcher(self._settings.google_genai_sdk).attempt_patch()
    
    def _patch_crewai(self) -> None:
        if self._settings and self._settings.crewai.enabled:
            from weave.integrations.crewai import get_crewai_patcher
            get_crewai_patcher(self._settings.crewai).attempt_patch()
    
    def _patch_notdiamond(self) -> None:
        if self._settings and self._settings.notdiamond.enabled:
            from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
            get_notdiamond_patcher(self._settings.notdiamond).attempt_patch()
    
    def _patch_vertexai(self) -> None:
        if self._settings and self._settings.vertexai.enabled:
            from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher
            get_vertexai_patcher(self._settings.vertexai).attempt_patch()
    
    def _patch_nvidia(self) -> None:
        if self._settings and self._settings.chatnvidia.enabled:
            from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import get_nvidia_ai_patcher
            get_nvidia_ai_patcher(self._settings.chatnvidia).attempt_patch()
    
    def _patch_huggingface(self) -> None:
        if self._settings and self._settings.huggingface.enabled:
            from weave.integrations.huggingface.huggingface_inference_client_sdk import get_huggingface_patcher
            get_huggingface_patcher(self._settings.huggingface).attempt_patch()
    
    def _patch_smolagents(self) -> None:
        if self._settings and self._settings.smolagents.enabled:
            from weave.integrations.smolagents.smolagents_sdk import get_smolagents_patcher
            get_smolagents_patcher(self._settings.smolagents).attempt_patch()
    
    def _patch_openai_agents(self) -> None:
        if self._settings and self._settings.openai_agents.enabled:
            from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher
            get_openai_agents_patcher(self._settings.openai_agents).attempt_patch()
    
    def _patch_verdict(self) -> None:
        if self._settings and self._settings.verdict.enabled:
            from weave.integrations.verdict.verdict_sdk import get_verdict_patcher
            get_verdict_patcher(self._settings.verdict).attempt_patch()
    
    def _patch_langchain(self) -> None:
        from weave.integrations.langchain.langchain import langchain_patcher
        langchain_patcher.attempt_patch()
    
    def _patch_llamaindex(self) -> None:
        from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
        llamaindex_patcher.attempt_patch()
    
    def _patch_autogen(self) -> None:
        if self._settings and self._settings.autogen.enabled:
            from weave.integrations.autogen import get_autogen_patcher
            get_autogen_patcher(self._settings.autogen).attempt_patch()


# Global instance of the lazy patch manager
_lazy_patch_manager = LazyPatchManager()


@validate_call
def autopatch(settings: Optional[AutopatchSettings] = None) -> None:
    """Initialize lazy patching with the given settings."""
    if settings is None:
        settings = AutopatchSettings()
    _lazy_patch_manager.setup(settings)


def reset_autopatch() -> None:
    """Reset all patches that have been applied lazily."""
    # Restore original import if it was modified
    if hasattr(_lazy_patch_manager, '_original_import'):
        if hasattr(__builtins__, '__import__'):
            __builtins__.__import__ = _lazy_patch_manager._original_import
        else:
            __builtins__['__import__'] = _lazy_patch_manager._original_import
    
    # Only undo patches for modules that were actually patched
    for patched_module in _lazy_patch_manager._patched.keys():
        if patched_module == 'openai':
            from weave.integrations.openai.openai_sdk import get_openai_patcher
            get_openai_patcher().undo_patch()
        elif patched_module == 'anthropic':
            from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
            get_anthropic_patcher().undo_patch()
        elif patched_module == 'mistral':
            from weave.integrations.mistral.mistral_sdk import get_mistral_patcher
            get_mistral_patcher().undo_patch()
        elif patched_module == 'mcp':
            from weave.integrations.mcp import get_mcp_client_patcher, get_mcp_server_patcher
            get_mcp_server_patcher().undo_patch()
            get_mcp_client_patcher().undo_patch()
        elif patched_module == 'litellm':
            from weave.integrations.litellm.litellm import get_litellm_patcher
            get_litellm_patcher().undo_patch()
        elif patched_module == 'groq':
            from weave.integrations.groq.groq_sdk import get_groq_patcher
            get_groq_patcher().undo_patch()
        elif patched_module == 'instructor':
            from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
            get_instructor_patcher().undo_patch()
        elif patched_module == 'dspy':
            from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
            get_dspy_patcher().undo_patch()
        elif patched_module == 'cerebras':
            from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
            get_cerebras_patcher().undo_patch()
        elif patched_module == 'cohere':
            from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
            get_cohere_patcher().undo_patch()
        elif patched_module == 'google_generativeai':
            from weave.integrations.google_ai_studio.google_ai_studio_sdk import get_google_generativeai_patcher
            get_google_generativeai_patcher().undo_patch()
        elif patched_module == 'google_genai_sdk':
            from weave.integrations.google_genai.google_genai_sdk import get_google_genai_patcher
            get_google_genai_patcher().undo_patch()
        elif patched_module == 'crewai':
            from weave.integrations.crewai import get_crewai_patcher
            get_crewai_patcher().undo_patch()
        elif patched_module == 'notdiamond':
            from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
            get_notdiamond_patcher().undo_patch()
        elif patched_module == 'vertexai':
            from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher
            get_vertexai_patcher().undo_patch()
        elif patched_module == 'chatnvidia':
            from weave.integrations.langchain_nvidia_ai_endpoints.langchain_nv_ai_endpoints import get_nvidia_ai_patcher
            get_nvidia_ai_patcher().undo_patch()
        elif patched_module == 'huggingface':
            from weave.integrations.huggingface.huggingface_inference_client_sdk import get_huggingface_patcher
            get_huggingface_patcher().undo_patch()
        elif patched_module == 'smolagents':
            from weave.integrations.smolagents.smolagents_sdk import get_smolagents_patcher
            get_smolagents_patcher().undo_patch()
        elif patched_module == 'openai_agents':
            from weave.integrations.openai_agents.openai_agents import get_openai_agents_patcher
            get_openai_agents_patcher().undo_patch()
        elif patched_module == 'verdict':
            from weave.integrations.verdict.verdict_sdk import get_verdict_patcher
            get_verdict_patcher().undo_patch()
        elif patched_module == 'langchain':
            from weave.integrations.langchain.langchain import langchain_patcher
            langchain_patcher.undo_patch()
        elif patched_module == 'llamaindex':
            from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
            llamaindex_patcher.undo_patch()
        elif patched_module == 'autogen':
            from weave.integrations.autogen import get_autogen_patcher
            get_autogen_patcher().undo_patch()
    
    # Clear the patched modules record
    _lazy_patch_manager._patched.clear()
