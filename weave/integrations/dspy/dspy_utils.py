from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.trace.autopatch import OpSettings
from weave.trace.serialize import dictify

if TYPE_CHECKING:
    from dspy.primitives.prediction import Example


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

        inputs["self"] = dictified_inputs_self
    return inputs


def dspy_postprocess_outputs(
    outputs: Any | "Example",
) -> list[Any] | dict[str, Any] | Any:
    import numpy as np
    from dspy import Example, Module

    if isinstance(outputs, Module):
        return outputs.dump_state()

    if isinstance(outputs, Example):
        return outputs.toDict()

    if isinstance(outputs, np.ndarray):
        return outputs.tolist()

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
