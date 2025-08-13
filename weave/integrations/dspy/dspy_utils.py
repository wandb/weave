import importlib
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Union

from pydantic import BaseModel

import weave
from weave.integrations.patcher import SymbolPatcher
from weave.trace.autopatch import OpSettings
from weave.trace.op import Op
from weave.utils.sanitize import REDACTED_VALUE, should_redact


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
        processed: dict[Any, Any] = {}
        for k, v in data.items():
            new_key = k.__name__ if isinstance(k, type) else k
            processed[new_key] = dump_dspy_objects(v)
        return processed
    elif isinstance(data, list):
        return [dump_dspy_objects(item) for item in data]
    elif isinstance(data, (tuple, set)):
        return [dump_dspy_objects(item) for item in data]
    elif isinstance(data, type):
        return data.__name__

    return data


def dspy_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    from dspy import Adapter, Evaluate, Predict

    if "self" in inputs:
        dictified_inputs_self = dictify(inputs["self"])
        if dictified_inputs_self["__class__"]["module"] == "__main__":
            dictified_inputs_self["__class__"]["module"] = ""

        # Optionally hide history to reduce trace size
        if os.getenv("WEAVE_DSPY_HIDE_HISTORY", "false").lower() in (
            "true",
            "1",
            "yes",
        ):
            dictified_inputs_self.pop("history", None)

        # Serialize the signature of the object if it is a Predict or Adapter
        if isinstance(inputs["self"], (Predict, Adapter)) and hasattr(
            inputs["self"], "signature"
        ):
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
    from litellm import ModelResponse

    if isinstance(outputs, Module):
        outputs = outputs.dump_state()

    if isinstance(outputs, Example):
        outputs = outputs.toDict()

    if isinstance(outputs, np.ndarray):
        outputs = outputs.tolist()

    if isinstance(outputs, ModelResponse):
        outputs = dictify(outputs)

    if isinstance(outputs, type):
        outputs = outputs.__name__

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


MAX_STR_LEN = 1000


def stringify(obj: Any, limit: int = MAX_STR_LEN) -> str:
    """This is a fallback for objects that we don't have a better way to serialize."""
    rep = None
    try:
        rep = repr(obj)
    except Exception:
        try:
            rep = str(obj)
        except Exception:
            rep = f"<{type(obj).__name__}: {id(obj)}>"
    if isinstance(rep, str) and len(rep) > limit:
        rep = rep[: limit - 3] + "..."
    return rep


def is_primitive(obj: Any) -> bool:
    """Check if an object is a known primitive type."""
    return isinstance(obj, (int, float, str, bool, type(None)))


def dictify(
    obj: Any, maxdepth: int = 0, depth: int = 1, seen: set[int] | None = None
) -> Any:
    """Recursively compute a dictionary representation of an object."""
    if seen is None:
        seen = set()

    if not is_primitive(obj):
        obj_id = id(obj)
        if obj_id in seen:
            # Avoid infinite recursion with circular references
            return stringify(obj)
        else:
            seen.add(obj_id)

    if maxdepth > 0 and depth > maxdepth:
        # TODO: If obj at this point is a simple type,
        #       maybe we should just return it rather than stringify
        return stringify(obj)

    if is_primitive(obj):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [dictify(v, maxdepth, depth + 1, seen) for v in obj]
    elif isinstance(obj, dict):
        dict_result = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                dict_result[k] = REDACTED_VALUE
            else:
                dict_result[k] = dictify(v, maxdepth, depth + 1, seen)
        return dict_result

    if hasattr(obj, "to_dict"):
        try:
            as_dict = obj.to_dict()
            if isinstance(as_dict, dict):
                to_dict_result = {}
                for k, v in as_dict.items():
                    if isinstance(k, str) and should_redact(k):
                        to_dict_result[k] = REDACTED_VALUE
                    elif maxdepth == 0 or depth < maxdepth:
                        to_dict_result[k] = dictify(v, maxdepth, depth + 1)
                    else:
                        to_dict_result[k] = stringify(v)
                return to_dict_result
        except Exception:
            raise ValueError("to_dict failed") from None

    result: dict[Any, Any] = {}
    result["__class__"] = {
        "module": obj.__class__.__module__,
        "qualname": obj.__class__.__qualname__,
        "name": obj.__class__.__name__,
    }
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        # Custom list-like object
        try:
            for i, item in enumerate(obj):
                result[i] = dictify(item, maxdepth, depth + 1, seen)
        except Exception:
            return stringify(obj)
    else:
        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            # DSPy 3.x's modules doesn't want to forward to be accessed directly.
            # Added this to dictify to suppress the warning without updating
            # weave utils' `dictify` with a similar change.
            if attr == "forward":
                continue
            if should_redact(attr):
                result[attr] = REDACTED_VALUE
                continue
            try:
                val = getattr(obj, attr)
                if callable(val):
                    continue
                if maxdepth == 0 or depth < maxdepth:
                    result[attr] = dictify(val, maxdepth, depth + 1, seen)
                else:
                    result[attr] = stringify(val)
            except Exception:
                return stringify(obj)
    return result
