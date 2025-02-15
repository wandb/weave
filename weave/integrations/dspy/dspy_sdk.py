from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.serialize import dictify

if TYPE_CHECKING:
    from dspy.primitives.prediction import Example

_dspy_patcher: MultiPatcher | None = None


def dspy_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
        if inputs["self"]["__class__"]["module"] == "__main__":
            inputs["self"]["__class__"]["module"] = ""
    return inputs


def dspy_postprocess_outputs(outputs: Any | Example) -> dict[str, Any]:
    from dspy.primitives.prediction import Example

    if isinstance(outputs, Example):
        return outputs.toDict()

    return outputs


def dspy_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = dspy_postprocess_inputs
        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = dspy_postprocess_outputs
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_dspy_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _dspy_patcher
    if _dspy_patcher is not None:
        return _dspy_patcher

    base = settings.op_settings

    _dspy_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "LM.__call__",
                dspy_wrapper(base.model_copy(update={"name": base.name or "dspy.LM"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Module.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Module"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Predict.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Predict"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Predict.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.Predict.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ChainOfThought.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ChainOfThought"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ChainOfThought.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.ChainOfThought.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ChainOfThoughtWithHint.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.ChainOfThoughtWithHint"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ChainOfThoughtWithHint.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.ChainOfThoughtWithHint.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "MultiChainComparison.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.MultiChainComparison"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "MultiChainComparison.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.MultiChainComparison.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Parallel.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Parallel"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Parallel.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.Parallel.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Program.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Program"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ProgramOfThought.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.ProgramOfThought"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ProgramOfThought.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.ProgramOfThought.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ProgramOfThought.execute_code",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.ProgramOfThought.execute_code"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ProgramOfThought.parse_code",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.ProgramOfThought.parse_code"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ReAct.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ReAct"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ReAct.forward",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ReAct.forward"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ColBERTv2.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ColBERTv2"})
                ),
            ),
        ]
    )

    return _dspy_patcher
