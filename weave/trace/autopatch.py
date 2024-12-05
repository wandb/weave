"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from weave.trace.weave_client import Call


def autopatch(settings: AutopatchSettings | None = None) -> None:
    from weave.integrations.anthropic.anthropic_sdk import anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import cohere_patcher
    from weave.integrations.dspy.dspy_sdk import dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import groq_patcher
    from weave.integrations.instructor.instructor_sdk import instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.litellm.litellm import litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mistral import mistral_patcher
    from weave.integrations.notdiamond.tracing import notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.vertexai.vertexai_sdk import vertexai_patcher

    if settings is None:
        settings = AutopatchSettings()

    get_openai_patcher(settings.openai).attempt_patch()
    mistral_patcher.attempt_patch()
    litellm_patcher.attempt_patch()
    llamaindex_patcher.attempt_patch()
    langchain_patcher.attempt_patch()
    anthropic_patcher.attempt_patch()
    groq_patcher.attempt_patch()
    instructor_patcher.attempt_patch()
    dspy_patcher.attempt_patch()
    cerebras_patcher.attempt_patch()
    cohere_patcher.attempt_patch()
    google_genai_patcher.attempt_patch()
    notdiamond_patcher.attempt_patch()
    vertexai_patcher.attempt_patch()


def reset_autopatch() -> None:
    from weave.integrations.anthropic.anthropic_sdk import anthropic_patcher
    from weave.integrations.cerebras.cerebras_sdk import cerebras_patcher
    from weave.integrations.cohere.cohere_sdk import cohere_patcher
    from weave.integrations.dspy.dspy_sdk import dspy_patcher
    from weave.integrations.google_ai_studio.google_ai_studio_sdk import (
        google_genai_patcher,
    )
    from weave.integrations.groq.groq_sdk import groq_patcher
    from weave.integrations.instructor.instructor_sdk import instructor_patcher
    from weave.integrations.langchain.langchain import langchain_patcher
    from weave.integrations.litellm.litellm import litellm_patcher
    from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
    from weave.integrations.mistral import mistral_patcher
    from weave.integrations.notdiamond.tracing import notdiamond_patcher
    from weave.integrations.openai.openai_sdk import get_openai_patcher
    from weave.integrations.vertexai.vertexai_sdk import vertexai_patcher

    get_openai_patcher().undo_patch()
    mistral_patcher.undo_patch()
    litellm_patcher.undo_patch()
    llamaindex_patcher.undo_patch()
    langchain_patcher.undo_patch()
    anthropic_patcher.undo_patch()
    groq_patcher.undo_patch()
    instructor_patcher.undo_patch()
    dspy_patcher.undo_patch()
    cerebras_patcher.undo_patch()
    cohere_patcher.undo_patch()
    google_genai_patcher.undo_patch()
    notdiamond_patcher.undo_patch()
    vertexai_patcher.undo_patch()


@dataclass
class OpSettings:
    """Op settings for a specific integration.
    These currently subset the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details."""

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

    openai: IntegrationSettings = field(default_factory=IntegrationSettings)
    anthropic: IntegrationSettings = field(default_factory=IntegrationSettings)
