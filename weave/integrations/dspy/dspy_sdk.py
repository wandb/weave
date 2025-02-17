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


def serialize_dspy_objects(data: Any) -> Any:
    import numpy as np
    from dspy import Example, Module

    if isinstance(data, Example):
        return data.toDict()

    elif isinstance(data, Module):
        return data.dump_state()

    elif isinstance(data, np.ndarray):
        return data.tolist()

    elif isinstance(data, dict):
        return {key: serialize_dspy_objects(value) for key, value in data.items()}

    elif isinstance(data, list):
        return [serialize_dspy_objects(item) for item in data]

    return data


def dspy_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    from dspy import Predict

    if "self" in inputs:
        dictified_inputs_self = dictify(inputs["self"])
        if dictified_inputs_self["__class__"]["module"] == "__main__":
            dictified_inputs_self["__class__"]["module"] = ""

        if isinstance(inputs["self"], Predict):
            if hasattr(inputs["self"], "signature"):
                try:
                    dictified_inputs_self["signature"] = inputs[
                        "self"
                    ].signature.model_json_schema()
                except Exception as e:
                    dictified_inputs_self["signature"] = inputs["self"].signature

        dictified_inputs_self = serialize_dspy_objects(dictified_inputs_self)
        inputs["self"] = dictified_inputs_self
    return serialize_dspy_objects(inputs)


def dspy_postprocess_outputs(
    outputs: Any | Example,
) -> list[Any] | dict[str, Any] | Any:
    import numpy as np
    from dspy import Example, Module

    if isinstance(outputs, Module):
        outputs = outputs.dump_state()

    if isinstance(outputs, Example):
        outputs = outputs.toDict()

    if isinstance(outputs, np.ndarray):
        outputs = outputs.tolist()

    return serialize_dspy_objects(outputs)


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
                "Embedder.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Embedder"})
                ),
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
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFinetune.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BootstrapFinetune.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "MIPROv2.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.MIPROv2.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "LabeledFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.LabeledFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "KNNFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.KNNFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "KNN.__call__",
                dspy_wrapper(base.model_copy(update={"name": base.name or "dspy.KNN"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Ensemble.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.Ensemble.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "COPRO.compile",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.COPRO.compile"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFewShotWithRandomSearch.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name
                            or "dspy.BootstrapFewShotWithRandomSearch.compile"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BootstrapFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BetterTogether.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BetterTogether.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "answer_passage_match",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.evaluate.answer_passage_match"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "answer_exact_match",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.answer_exact_match"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "SemanticF1.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.SemanticF1"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "SemanticF1.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.SemanticF1.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "CompleteAndGrounded.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.evaluate.CompleteAndGrounded"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "CompleteAndGrounded.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name
                            or "dspy.evaluate.CompleteAndGrounded.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Evaluate.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Evaluate"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.retrievers"),
                "Embeddings.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.retrievers.Embeddings"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.retrievers"),
                "Embeddings.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.retrievers.Embeddings.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "PythonInterpreter.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.PythonInterpreter"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "PythonInterpreter.execute",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.PythonInterpreter.execute"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Adapter.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Adapter"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ChatAdapter.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ChatAdapter"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "JSONAdapter.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.JSONAdapter"})
                ),
            ),
        ]
    )

    return _dspy_patcher
