"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""


def autopatch() -> None:
    from ..integrations.anthropic.anthropic_sdk import anthropic_patcher
    from ..integrations.cerebras.cerebras_sdk import cerebras_patcher
    from ..integrations.cohere.cohere_sdk import cohere_patcher
    from ..integrations.dspy.dspy_sdk import dspy_patcher
    from ..integrations.groq.groq_sdk import groq_patcher
    from ..integrations.langchain.langchain import langchain_patcher
    from ..integrations.litellm.litellm import litellm_patcher
    from ..integrations.llamaindex.llamaindex import llamaindex_patcher
    from ..integrations.mistral.mistral import mistral_patcher
    from ..integrations.openai.openai_sdk import openai_patcher

    openai_patcher.attempt_patch()
    mistral_patcher.attempt_patch()
    litellm_patcher.attempt_patch()
    llamaindex_patcher.attempt_patch()
    langchain_patcher.attempt_patch()
    anthropic_patcher.attempt_patch()
    groq_patcher.attempt_patch()
    dspy_patcher.attempt_patch()
    cerebras_patcher.attempt_patch()
    cohere_patcher.attempt_patch()


def reset_autopatch() -> None:
    from ..integrations.anthropic.anthropic_sdk import anthropic_patcher
    from ..integrations.cerebras.cerebras_sdk import cerebras_patcher
    from ..integrations.cohere.cohere_sdk import cohere_patcher
    from ..integrations.dspy.dspy_sdk import dspy_patcher
    from ..integrations.groq.groq_sdk import groq_patcher
    from ..integrations.langchain.langchain import langchain_patcher
    from ..integrations.litellm.litellm import litellm_patcher
    from ..integrations.llamaindex.llamaindex import llamaindex_patcher
    from ..integrations.mistral.mistral import mistral_patcher
    from ..integrations.openai.openai_sdk import openai_patcher

    openai_patcher.undo_patch()
    mistral_patcher.undo_patch()
    litellm_patcher.undo_patch()
    llamaindex_patcher.undo_patch()
    langchain_patcher.undo_patch()
    anthropic_patcher.undo_patch()
    groq_patcher.undo_patch()
    dspy_patcher.undo_patch()
    cerebras_patcher.undo_patch()
    cohere_patcher.undo_patch()
