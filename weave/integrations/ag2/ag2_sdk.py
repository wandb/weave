"""AG2 (formerly AutoGen) integration for Weave.

Patches AG2's core methods to capture traces:
- ConversableAgent.initiate_chat — conversation-level trace
- ConversableAgent.generate_reply — agent response trace
- OpenAIWrapper.create — LLM call trace
- initiate_group_chat — group chat trace
"""

import importlib
import logging
from collections.abc import Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

logger = logging.getLogger(__name__)

_ag2_patcher: MultiPatcher | None = None


def _postprocess_chat_inputs(inputs: dict) -> dict:
    """Sanitize initiate_chat / initiate_group_chat inputs
    for serialization.
    """
    sanitized = {}
    for key, value in inputs.items():
        if key == "self":
            sanitized["agent_name"] = getattr(
                value, "name", str(type(value).__name__)
            )
        elif key == "messages":
            sanitized["messages"] = (
                value
                if isinstance(value, (str, list))
                else str(value)
            )
        elif key in {"pattern", "recipient"}:
            sanitized[key] = str(type(value).__name__)
        elif key in {"max_rounds", "max_turns", "clear_history"}:
            sanitized[key] = value
        # Skip non-serializable args (agents, callbacks, etc.)
    return sanitized


def _postprocess_llm_inputs(inputs: dict) -> dict:
    """Sanitize OpenAIWrapper.create inputs."""
    sanitized = {}
    for key, value in inputs.items():
        if key == "self":
            continue
        elif key == "messages":
            sanitized["messages"] = value
        elif key in {"model", "cache_seed", "max_tokens"}:
            sanitized[key] = value
    return sanitized


def ag2_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_ag2_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    global _ag2_patcher  # noqa: PLW0603
    if _ag2_patcher is not None:
        return _ag2_patcher

    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()

    base = settings.op_settings

    initiate_chat_settings = base.model_copy(
        update={
            "name": "ag2.ConversableAgent.initiate_chat",
            "postprocess_inputs": _postprocess_chat_inputs,
            "kind": "agent",
        }
    )

    generate_reply_settings = base.model_copy(
        update={
            "name": "ag2.ConversableAgent.generate_reply",
            "kind": "agent",
        }
    )

    openai_wrapper_create_settings = base.model_copy(
        update={
            "name": "ag2.OpenAIWrapper.create",
            "postprocess_inputs": _postprocess_llm_inputs,
            "kind": "llm",
        }
    )

    initiate_group_chat_settings = base.model_copy(
        update={
            "name": "ag2.initiate_group_chat",
            "postprocess_inputs": _postprocess_chat_inputs,
            "kind": "agent",
        }
    )

    patchers = [
        # --- ConversableAgent.initiate_chat ---
        SymbolPatcher(
            lambda: importlib.import_module("autogen"),
            "ConversableAgent.initiate_chat",
            ag2_wrapper(initiate_chat_settings),
        ),
        # --- ConversableAgent.generate_reply ---
        SymbolPatcher(
            lambda: importlib.import_module("autogen"),
            "ConversableAgent.generate_reply",
            ag2_wrapper(generate_reply_settings),
        ),
        # --- OpenAIWrapper.create ---
        SymbolPatcher(
            lambda: importlib.import_module("autogen.oai.client"),
            "OpenAIWrapper.create",
            ag2_wrapper(openai_wrapper_create_settings),
        ),
        # --- initiate_group_chat (module-level function) ---
        SymbolPatcher(
            lambda: importlib.import_module("autogen.agentchat"),
            "initiate_group_chat",
            ag2_wrapper(initiate_group_chat_settings),
        ),
    ]

    _ag2_patcher = MultiPatcher(patchers)
    return _ag2_patcher
