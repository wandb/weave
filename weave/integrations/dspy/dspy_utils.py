from typing import TYPE_CHECKING, Any, Callable, Union

import weave
from weave.trace.autopatch import OpSettings
from weave.trace.serialize import dictify

if TYPE_CHECKING:
    from dspy.primitives.prediction import Example


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
    from dspy import Adapter, Predict

    if "self" in inputs:
        dictified_inputs_self = dictify(inputs["self"])
        if dictified_inputs_self["__class__"]["module"] == "__main__":
            dictified_inputs_self["__class__"]["module"] = ""

        if isinstance(inputs["self"], Predict) or isinstance(inputs["self"], Adapter):
            if hasattr(inputs["self"], "signature"):
                if hasattr(inputs["self"].signature, "model_json_schema"):
                    dictified_inputs_self["signature"] = inputs[
                        "self"
                    ].signature.model_json_schema()
                else:
                    dictified_inputs_self["signature"] = inputs["self"].signature

        dictified_inputs_self = serialize_dspy_objects(dictified_inputs_self)
        inputs["self"] = dictified_inputs_self
    return serialize_dspy_objects(inputs)


def dspy_postprocess_outputs(
    outputs: Union[Any, "Example"],
) -> Union[list[Any], dict[str, Any], Any]:
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
