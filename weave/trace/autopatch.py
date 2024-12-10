"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from weave.trace.weave_client import Call


def autopatch(settings: AutopatchSettings | None = None) -> None:
    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        get_google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import get_groq_patcher
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.litellm.litellm import get_litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mistral import get_mistral_patcher
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    if settings is None:
        settings = AutopatchSettings()

        get_openai_patcher(settings.openai).attempt_patch()
        get_openai_patcher(settings.openai).attempt_patch()

    if settings.mistral.enabled:
    get_openai_patcher(settings.openai).attempt_patch()

    if settings.mistral.enabled:
        get_mistral_patcher(settings.mistral).attempt_patch()
        get_mistral_patcher(settings.mistral).attempt_patch()

    if settings.litellm.enabled:
    get_mistral_patcher(settings.mistral).attempt_patch()

    if settings.litellm.enabled:
        get_litellm_patcher(settings.litellm).attempt_patch()
        get_litellm_patcher(settings.litellm).attempt_patch()

    if settings.anthropic.enabled:
    get_litellm_patcher(settings.litellm).attempt_patch()

    if settings.anthropic.enabled:
        get_anthropic_patcher(settings.anthropic).attempt_patch()
        get_anthropic_patcher(settings.anthropic).attempt_patch()

    if settings.groq.enabled:
    get_anthropic_patcher(settings.anthropic).attempt_patch()

    if settings.groq.enabled:
        get_groq_patcher(settings.groq).attempt_patch()
        get_groq_patcher(settings.groq).attempt_patch()

    if settings.instructor.enabled:
    get_groq_patcher(settings.groq).attempt_patch()

    if settings.instructor.enabled:
        get_instructor_patcher(settings.instructor).attempt_patch()
        get_instructor_patcher(settings.instructor).attempt_patch()

    if settings.dspy.enabled:
    get_instructor_patcher(settings.instructor).attempt_patch()

    if settings.dspy.enabled:
        get_dspy_patcher(settings.dspy).attempt_patch()
        get_dspy_patcher(settings.dspy).attempt_patch()

    if settings.cerebras.enabled:
    get_dspy_patcher(settings.dspy).attempt_patch()

    if settings.cerebras.enabled:
        get_cerebras_patcher(settings.cerebras).attempt_patch()
        get_cerebras_patcher(settings.cerebras).attempt_patch()

    if settings.cohere.enabled:
    get_cerebras_patcher(settings.cerebras).attempt_patch()

    if settings.cohere.enabled:
        get_cohere_patcher(settings.cohere).attempt_patch()
        get_cohere_patcher(settings.cohere).attempt_patch()

    if settings.google_ai_studio.enabled:
    get_cohere_patcher(settings.cohere).attempt_patch()

    if settings.google_ai_studio.enabled:
        get_google_genai_patcher(settings.google_ai_studio).attempt_patch()
        get_google_genai_patcher(settings.google_ai_studio).attempt_patch()

    if settings.notdiamond.enabled:
    get_google_genai_patcher(settings.google_ai_studio).attempt_patch()

    if settings.notdiamond.enabled:
        get_notdiamond_patcher(settings.notdiamond).attempt_patch()
        get_notdiamond_patcher(settings.notdiamond).attempt_patch()

    if settings.vertexai.enabled:
    get_notdiamond_patcher(settings.notdiamond).attempt_patch()

    if settings.vertexai.enabled:
    get_vertexai_patcher(settings.vertexai).attempt_patch()

    # These integrations don't use the op decorator, so there are no settings to pass through
    llamaindex_patcher.attempt_patch()
    langchain_patcher.attempt_patch()


def reset_autopatch() -> None:
    from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import get_cohere_patcher
    from weave.integrations.dspy.dspy_sdk import get_dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        get_google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import get_groq_patcher
    from weave.integrations.instructor.instructor_sdk import get_instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.litellm.litellm import get_litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mistral import get_mistral_patcher
    from weave.integrations.notdiamond.tracing import get_notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.vertexai.vertexai_sdk import get_vertexai_patcher

    get_openai_patcher().undo_patch()
    get_mistral_patcher().undo_patch()
    get_litellm_patcher().undo_patch()
    get_anthropic_patcher().undo_patch()
    get_groq_patcher().undo_patch()
    get_instructor_patcher().undo_patch()
    get_dspy_patcher().undo_patch()
    get_cerebras_patcher().undo_patch()
    get_cohere_patcher().undo_patch()
    get_google_genai_patcher().undo_patch()
    get_notdiamond_patcher().undo_patch()
    get_vertexai_patcher().undo_patch()

    llamaindex_patcher.undo_patch()
    langchain_patcher.undo_patch()


@dataclass
class OpSettings:
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details."""

    name: str | None = None
    call_display_name: str | Callable[[Call], str] | None = None
    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    postprocess_output: Callable[[Any], Any] | None = None


@dataclass
class IntegrationSettings:
    """Configuration for a specific integration."""

    enabled: bool = True
    op_settings: OpSettings = field(default_factory=OpSettings)


@dataclass
class AutopatchSettings:
    """Settings for auto-patching integrations."""

    anthropic: IntegrationSettings = field(default_factory=IntegrationSettings)
    cerebras: IntegrationSettings = field(default_factory=IntegrationSettings)
    cohere: IntegrationSettings = field(default_factory=IntegrationSettings)
    dspy: IntegrationSettings = field(default_factory=IntegrationSettings)
    google_ai_studio: IntegrationSettings = field(default_factory=IntegrationSettings)
    groq: IntegrationSettings = field(default_factory=IntegrationSettings)
    instructor: IntegrationSettings = field(default_factory=IntegrationSettings)
    langchain: IntegrationSettings = field(default_factory=IntegrationSettings)
    litellm: IntegrationSettings = field(default_factory=IntegrationSettings)
    llamaindex: IntegrationSettings = field(default_factory=IntegrationSettings)
    mistral: IntegrationSettings = field(default_factory=IntegrationSettings)
    notdiamond: IntegrationSettings = field(default_factory=IntegrationSettings)
    openai: IntegrationSettings = field(default_factory=IntegrationSettings)
    vertexai: IntegrationSettings = field(default_factory=IntegrationSettings)
