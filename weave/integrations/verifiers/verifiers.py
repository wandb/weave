from __future__ import annotations

import importlib
from functools import wraps
from typing import Any, Callable, Optional

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_verifiers_patcher: Optional[MultiPatcher] = None


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
                    op_kwargs["name"] = f"verifiers.{self.__class__.__name__}.extract_fn"
                try:
                    self.extract_fn = weave.op(extract_fn, **op_kwargs)
                except Exception:
                    # If wrapping fails, leave the original in place
                    pass
            return result

        return _inner

    return wrapper


def _wrap_method_returning_callable(settings: OpSettings) -> Callable[[Callable], Callable]:
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
        update={"name": base.name or "verifiers.envs.multiturn_env.MultiTurnEnv.rollout"}
    )
    evaluate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.evaluate"}
    )
    a_generate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.a_generate"}
    )
    generate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.generate"}
    )
    score_rollouts_settings = base.model_copy(
        update={"name": base.name or "verifiers.Rubric.score_rollouts"}
    )
    score_rollout_settings = base.model_copy(
        update={"name": base.name or "verifiers.Rubric.score_rollout"}
    )

    _verifiers_patcher = MultiPatcher(
        [
            # Environment
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
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.multiturn_env"),
                "MultiTurnEnv.rollout",
                _verifiers_wrapper_async(settings=rollout_settings),
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
                _wrap_parser_init(settings=base.model_copy(update={"name": base.name or "verifiers.Parser.extract_fn"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.parse",
                _verifiers_wrapper(settings=base.model_copy(update={"name": base.name or "verifiers.Parser.parse"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.parse_answer",
                _verifiers_wrapper(settings=base.model_copy(update={"name": base.name or "verifiers.Parser.parse_answer"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.parser"),
                "Parser.get_format_reward_func",
                _wrap_method_returning_callable(settings=base.model_copy(update={"name": base.name or "verifiers.Parser.format_reward"})),
            ),

            # Parsers: ThinkParser
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.think_parser"),
                "ThinkParser.parse",
                _verifiers_wrapper(settings=base.model_copy(update={"name": base.name or "verifiers.ThinkParser.parse"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.parsers.think_parser"),
                "ThinkParser.get_format_reward_func",
                _wrap_method_returning_callable(settings=base.model_copy(update={"name": base.name or "verifiers.ThinkParser.format_reward"})),
            ),
            # TODO(ayulockin): Add XMLParser
        ]
    )

    return _verifiers_patcher
