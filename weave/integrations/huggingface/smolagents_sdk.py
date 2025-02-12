import importlib
from typing import Callable, Optional, Union

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher

_smolagents_patcher: Optional[MultiPatcher] = None


def smolagents_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_smolagents_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _smolagents_patcher
    if _smolagents_patcher is not None:
        return _smolagents_patcher

    base = settings.op_settings
    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.run",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.MultiStepAgent.run"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.execute_tool_call",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.execute_tool_call"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.extract_action",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name or "smolagents.MultiStepAgent.extract_action"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.provide_final_answer",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.provide_final_answer"
                    }
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent",
            smolagents_wrapper(
                base.model_copy(
                    update={"name": base.name or "smolagents.MultiStepAgent.__call__"}
                )
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("smolagents"),
            "MultiStepAgent.write_memory_to_messages",
            smolagents_wrapper(
                base.model_copy(
                    update={
                        "name": base.name
                        or "smolagents.MultiStepAgent.write_memory_to_messages"
                    }
                )
            ),
        ),
    ]

    _smolagents_patcher = MultiPatcher(patchers)
    return _smolagents_patcher
