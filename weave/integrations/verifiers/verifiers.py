from __future__ import annotations

import copy
import importlib
from collections.abc import Callable
from functools import wraps
from typing import Any

from openai.types.chat.chat_completion import ChatCompletion
from openai.types.completion import Completion
from pydantic import BaseModel

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

ModelResponse = Completion | ChatCompletion

_verifiers_patcher: MultiPatcher | None = None


def _verifiers_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Normalize `self` for clearer display in the UI."""
    if "self" in inputs:
        cls = inputs["self"].__class__
        inputs["self"] = {
            "__class__": {
                "module": cls.__module__,
                "qualname": getattr(cls, "__qualname__", cls.__name__),
                "name": cls.__name__,
            }
        }
    return inputs


def _remove_logprobs_from_responses(responses: list[Any]) -> list[Any]:
    """Return a copy of responses with logprobs removed, without mutating originals."""
    sanitized: list[Any] = []
    for response in responses:
        if isinstance(response, ModelResponse):
            # Prefer pydantic v2 deep copy if available; fall back to deepcopy
            try:
                response_copy = response.model_copy(deep=True)  # type: ignore[attr-defined]
            except Exception:
                response_copy = copy.deepcopy(response)
            # Strip logprobs from the copied response
            for choice in getattr(response_copy, "choices", []) or []:
                if hasattr(choice, "logprobs"):
                    choice.logprobs = None
            sanitized.append(response_copy)
        else:
            sanitized.append(response)
    return sanitized


def _verifiers_postprocess_outputs_no_logprobs(outputs: Any) -> Any:
    """Return a logging-safe copy of outputs with logprobs removed.

    IMPORTANT: Do not mutate the original outputs, as they are consumed by the
    training pipeline which expects `logprobs` to be present.
    """
    if outputs is None:
        return outputs

    # Deep copy the entire outputs structure for logging only
    try:
        outputs_copy = (
            outputs.model_copy(deep=True)  # type: ignore[attr-defined]
            if isinstance(outputs, BaseModel)
            else copy.deepcopy(outputs)
        )
    except Exception:
        outputs_copy = copy.deepcopy(outputs)

    if (
        isinstance(outputs_copy, BaseModel)
        and hasattr(outputs_copy, "state")
        and isinstance(outputs_copy.state, list)
    ):
        for state_item in outputs_copy.state:
            # ref: https://github.com/willccbb/verifiers/blob/37d7243703a38944be6e44fd4afe9b22c696b449/verifiers/types.py#L41
            if isinstance(state_item, dict) and "responses" in state_item:
                state_item["responses"] = _remove_logprobs_from_responses(
                    state_item.get("responses", [])
                )

    return outputs_copy


def _verifiers_postprocess_inputs_no_logprobs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Return a logging-safe copy of inputs with logprobs removed and normalized `self`.

    Do not mutate original inputs to avoid affecting the live function call.
    """
    # First apply the standard input processing (which returns a new dict for logging)
    processed_inputs = _verifiers_postprocess_inputs(inputs)

    if "states" in processed_inputs and isinstance(processed_inputs["states"], list):
        new_states: list[Any] = []
        for state_item in processed_inputs["states"]:
            if isinstance(state_item, dict) and "responses" in state_item:
                new_item = dict(state_item)
                new_item["responses"] = _remove_logprobs_from_responses(
                    state_item.get("responses", [])
                )
                new_states.append(new_item)
            else:
                new_states.append(state_item)
        processed_inputs["states"] = new_states

    return processed_inputs


def _verifiers_wrapper(settings: OpSettings) -> Callable:
    """Return a sync wrapper that converts a function into a Weave op."""

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = _verifiers_postprocess_inputs
        return weave.op(fn, **op_kwargs)

    return wrapper


def _verifiers_wrapper_async(settings: OpSettings) -> Callable:
    """Return an async-aware wrapper factory that awaits the original function."""

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = _verifiers_postprocess_inputs

        @wraps(fn)
        async def _inner(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        return weave.op(_inner, **op_kwargs)

    return wrapper


def _wrap_parser_init(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(original_init: Callable) -> Callable:
        @wraps(original_init)
        def _inner(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_init(self, *args, **kwargs)
            extract_fn = getattr(self, "extract_fn", None)
            if callable(extract_fn):
                op_kwargs = settings.model_dump()
                if not op_kwargs.get("name"):
                    op_kwargs["name"] = (
                        f"verifiers.{self.__class__.__name__}.extract_fn"
                    )
                try:
                    self.extract_fn = weave.op(extract_fn, **op_kwargs)
                except Exception:
                    # If wrapping fails, leave the original in place
                    pass
            return result

        return _inner

    return wrapper


def _wrap_method_returning_callable(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(original_method: Callable) -> Callable:
        @wraps(original_method)
        def _inner(self: Any, *args: Any, **kwargs: Any) -> Callable:
            returned = original_method(self, *args, **kwargs)
            if callable(returned):
                op_kwargs = settings.model_dump()
                if not op_kwargs.get("name"):
                    op_kwargs["name"] = (
                        f"verifiers.{self.__class__.__name__}.format_reward"
                    )
                try:
                    return weave.op(returned, **op_kwargs)
                except Exception:
                    return returned
            return returned

        return _inner

    return wrapper


def get_verifiers_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _verifiers_patcher
    if _verifiers_patcher is not None:
        return _verifiers_patcher

    base: OpSettings = settings.op_settings
    get_model_response_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.get_model_response"}
    )
    rollout_settings = base.model_copy(
        update={
            "name": base.name or "verifiers.envs.multiturn_env.MultiTurnEnv.rollout"
        }
    )
    evaluate_settings = base.model_copy(
        update={
            "name": base.name or "verifiers.Environment.evaluate",
            "postprocess_output": _verifiers_postprocess_outputs_no_logprobs,
        }
    )
    a_generate_settings = base.model_copy(
        update={
            "name": base.name or "verifiers.Environment.a_generate",
            "postprocess_output": _verifiers_postprocess_outputs_no_logprobs,
        }
    )
    generate_settings = base.model_copy(
        update={
            "name": base.name or "verifiers.Environment.generate",
            "postprocess_output": _verifiers_postprocess_outputs_no_logprobs,
        }
    )
    score_rollouts_settings = base.model_copy(
        update={
            "name": base.name or "verifiers.Rubric.score_rollouts",
            "postprocess_inputs": _verifiers_postprocess_inputs_no_logprobs,
            "postprocess_output": _verifiers_postprocess_outputs_no_logprobs,
        }
    )
    score_rollout_settings = base.model_copy(
        update={"name": base.name or "verifiers.Rubric.score_rollout"}
    )

    _verifiers_patcher = MultiPatcher(
        [
            # Environment (core)
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.evaluate",
                _verifiers_wrapper(evaluate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.get_model_response",
                _verifiers_wrapper_async(settings=get_model_response_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.a_generate",
                _verifiers_wrapper_async(settings=a_generate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.generate",
                _verifiers_wrapper(settings=generate_settings),
            ),
            # Multi-turn core rollout
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.multiturn_env"),
                "MultiTurnEnv.rollout",
                _verifiers_wrapper_async(settings=rollout_settings),
            ),
            # EnvGroup routing
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.env_group"),
                "EnvGroup.rollout",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.EnvGroup.rollout"}
                    )
                ),
            ),
            # SingleTurnEnv
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.singleturn_env"),
                "SingleTurnEnv.env_response",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={
                            "name": base.name or "verifiers.SingleTurnEnv.env_response"
                        }
                    )
                ),
            ),
            # ToolEnv (tool-use)
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.tool_env"),
                "ToolEnv.is_completed",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.ToolEnv.is_completed"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.tool_env"),
                "ToolEnv.env_response",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.ToolEnv.env_response"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.tool_env"),
                "ToolEnv.call_tool",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.ToolEnv.call_tool"}
                    )
                ),
            ),
            # StatefulToolEnv
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.stateful_tool_env"),
                "StatefulToolEnv.update_tool_args",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={
                            "name": base.name
                            or "verifiers.StatefulToolEnv.update_tool_args"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.stateful_tool_env"),
                "StatefulToolEnv.call_tool",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={
                            "name": base.name or "verifiers.StatefulToolEnv.call_tool"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.stateful_tool_env"),
                "StatefulToolEnv.env_response",
                _verifiers_wrapper_async(
                    settings=base.model_copy(
                        update={
                            "name": base.name
                            or "verifiers.StatefulToolEnv.env_response"
                        }
                    )
                ),
            ),
            # Rubric
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.rubrics.rubric"),
                "Rubric.score_rollouts",
                _verifiers_wrapper_async(settings=score_rollouts_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.rubrics.rubric"),
                "Rubric.score_rollout",
                _verifiers_wrapper_async(settings=score_rollout_settings),
            ),
            # Parsers: base
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.__init__",
                _wrap_parser_init(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.Parser.extract_fn"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.parse",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.Parser.parse"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.get_format_reward_func",
                _wrap_method_returning_callable(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.Parser.format_reward"}
                    )
                ),
            ),
            # Parsers: ThinkParser
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.think_parser"),
                "ThinkParser.parse",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.ThinkParser.parse"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.think_parser"),
                "ThinkParser.get_format_reward_func",
                _wrap_method_returning_callable(
                    settings=base.model_copy(
                        update={
                            "name": base.name or "verifiers.ThinkParser.format_reward"
                        }
                    )
                ),
            ),
            # Parsers: XMLParser
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.parse",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.XMLParser.parse"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.parse_answer",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.XMLParser.parse_answer"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.get_format_reward_func",
                _wrap_method_returning_callable(
                    settings=base.model_copy(
                        update={
                            "name": base.name or "verifiers.XMLParser.format_reward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.get_fields",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.XMLParser.get_fields"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.format",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={"name": base.name or "verifiers.XMLParser.format"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.xml_parser"),
                "XMLParser.get_format_str",
                _verifiers_wrapper(
                    settings=base.model_copy(
                        update={
                            "name": base.name or "verifiers.XMLParser.get_format_str"
                        }
                    )
                ),
            ),
        ]
    )

    return _verifiers_patcher
