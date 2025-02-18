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


def create_patcher(
    import_module_path: str, attribute_name: str, base: OpSettings
) -> SymbolPatcher:
    return SymbolPatcher(
        lambda: importlib.import_module(import_module_path),
        attribute_name,
        dspy_wrapper(
            base.model_copy(
                update={
                    "name": base.name
                    or f"{import_module_path}.{attribute_name}".removesuffix(
                        ".__call__"
                    )
                }
            )
        ),
    )


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

    return MultiPatcher(
        [
            create_patcher("dspy", "LM.__call__", base),
            create_patcher("dspy", "Embedder.__call__", base),
            create_patcher("dspy", "Module.__call__", base),
            create_patcher("dspy", "Predict.__call__", base),
            create_patcher("dspy", "Predict.forward", base),
            create_patcher("dspy", "ChainOfThought.__call__", base),
            create_patcher("dspy", "ChainOfThought.forward", base),
            create_patcher("dspy", "ChainOfThoughtWithHint.__call__", base),
            create_patcher("dspy", "ChainOfThoughtWithHint.forward", base),
            create_patcher("dspy", "MultiChainComparison.__call__", base),
            create_patcher("dspy", "MultiChainComparison.forward", base),
            create_patcher("dspy", "Parallel.__call__", base),
            create_patcher("dspy", "Parallel.forward", base),
            create_patcher("dspy", "Program.__call__", base),
            create_patcher("dspy", "ProgramOfThought.__call__", base),
            create_patcher("dspy", "ProgramOfThought.forward", base),
            create_patcher("dspy", "ProgramOfThought.execute_code", base),
            create_patcher("dspy", "ProgramOfThought.parse_code", base),
            create_patcher("dspy", "ReAct.__call__", base),
            create_patcher("dspy", "ReAct.forward", base),
            create_patcher("dspy", "ColBERTv2.__call__", base),
            create_patcher("dspy", "BootstrapFinetune.compile", base),
            create_patcher("dspy", "MIPROv2.compile", base),
            create_patcher("dspy", "LabeledFewShot.compile", base),
            create_patcher("dspy", "KNNFewShot.compile", base),
            create_patcher("dspy", "KNN.__call__", base),
            create_patcher("dspy", "Ensemble.compile", base),
            create_patcher("dspy", "COPRO.compile", base),
            create_patcher("dspy", "BootstrapFewShotWithRandomSearch.compile", base),
            create_patcher("dspy", "BootstrapFewShot.compile", base),
            create_patcher("dspy", "BetterTogether.compile", base),
            create_patcher("dspy.evaluate", "answer_passage_match", base),
            create_patcher("dspy.evaluate", "answer_exact_match", base),
            create_patcher("dspy.evaluate", "SemanticF1.__call__", base),
            create_patcher("dspy.evaluate", "SemanticF1.forward", base),
            create_patcher("dspy.evaluate", "CompleteAndGrounded.__call__", base),
            create_patcher("dspy.evaluate", "CompleteAndGrounded.forward", base),
            create_patcher("dspy", "Evaluate.__call__", base),
            create_patcher("dspy.retrievers", "Embeddings.__call__", base),
            create_patcher("dspy.retrievers", "Embeddings.forward", base),
            create_patcher("dspy", "PythonInterpreter.__call__", base),
            create_patcher("dspy", "PythonInterpreter.execute", base),
            create_patcher("dspy", "Adapter.__call__", base),
            create_patcher("dspy", "ChatAdapter.__call__", base),
            create_patcher("dspy", "JSONAdapter.__call__", base),
        ]
    )
