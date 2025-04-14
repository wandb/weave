import importlib
from typing import TYPE_CHECKING, Any, Callable, Union

from pydantic import BaseModel

import weave
from weave.integrations.patcher import SymbolPatcher
from weave.trace.autopatch import OpSettings
from weave.trace.op import Op
from weave.trace.serialization.serialize import dictify

if TYPE_CHECKING:
    from dspy.primitives.prediction import Example


def get_symbol_patcher(
    base_symbol: str, attribute_name: str, settings: OpSettings
) -> SymbolPatcher:
    display_name = base_symbol + "." + attribute_name
    display_name = (
        display_name.replace(".__call__", "")
        if attribute_name.endswith(".__call__")
        else display_name
    )
    return SymbolPatcher(
        lambda: importlib.import_module(base_symbol),
        attribute_name,
        dspy_wrapper(
            settings.model_copy(update={"name": settings.name or display_name})
        ),
    )


def dump_dspy_objects(data: Any) -> Any:
    import numpy as np
    from dspy import Example, Module

    if isinstance(data, Example):
        return data.toDict()

    elif isinstance(data, Module):
        return data.dump_state()

    elif isinstance(data, np.ndarray):
        return data.tolist()

    elif isinstance(data, dict):
        return {key: dump_dspy_objects(value) for key, value in data.items()}

    elif isinstance(data, list):
        return [dump_dspy_objects(item) for item in data]

    return data


def dspy_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    from dspy import Adapter, Evaluate, Predict

    if "self" in inputs:
        dictified_inputs_self = dictify(inputs["self"])
        if dictified_inputs_self["__class__"]["module"] == "__main__":
            dictified_inputs_self["__class__"]["module"] = ""

        # Serialize the signature of the object if it is a Predict or Adapter
        if isinstance(inputs["self"], Predict) or isinstance(inputs["self"], Adapter):
            if hasattr(inputs["self"], "signature"):
                if isinstance(inputs["self"].signature, BaseModel):
                    dictified_inputs_self["signature"] = inputs[
                        "self"
                    ].signature.model_json_schema()
                else:
                    dictified_inputs_self["signature"] = inputs["self"].signature

        dictified_inputs_self = dump_dspy_objects(dictified_inputs_self)

        # Recursively serialize the dspy objects in the devset
        if isinstance(inputs["self"], Evaluate):
            dictified_inputs_self["devset"] = [
                dump_dspy_objects(example) for example in inputs["self"].devset
            ]

            # Convert the metric to a weave op if it is not already one
            if hasattr(inputs["self"], "metric"):
                inputs["self"].metric = (
                    weave.op(inputs["self"].metric)
                    if not isinstance(inputs["self"].metric, Op)
                    else inputs["self"].metric
                )

        inputs["self"] = dictified_inputs_self

    return dump_dspy_objects(inputs)


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

    return dump_dspy_objects(outputs)


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


def get_op_name_for_callback(instance: Any, inputs: dict[str, Any]) -> str:
    instance_class_name = instance.__class__.__name__
    return (
        f"dspy.{instance_class_name}"
        if "dspy." in inputs["self"]["__class__"]["module"]
        else instance_class_name
    )
