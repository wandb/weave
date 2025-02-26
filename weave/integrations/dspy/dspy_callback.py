from typing import Any, Optional

from weave.integrations.dspy.dspy_utils import (
    dspy_postprocess_inputs,
    get_op_name_for_callback,
    serialize_dspy_objects,
)
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.serialize import dictify
from weave.trace.weave_client import Call

import_failed = False

try:
    from dspy.utils.callback import BaseCallback
except Exception:
    import_failed = True


if not import_failed:

    class WeaveCallback(BaseCallback):
        def __init__(self) -> None:
            self._call_map: dict[str, Call] = {}

        def on_lm_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}
            self._call_map[call_id] = gc.create_call(
                "dspy.LM",
                inputs=dspy_postprocess_inputs(inputs),
                display_name="dspy.LM",
            )

        def on_lm_end(
            self,
            call_id: str,
            outputs: Optional[Any],
            exception: Optional[Exception] = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], serialize_dspy_objects(outputs), exception
                )

        def on_module_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}
                if hasattr(instance, "signature"):
                    if hasattr(instance.signature, "model_json_schema"):
                        inputs["self"]["signature"] = (
                            instance.signature.model_json_schema()
                        )
                    else:
                        inputs["self"]["signature"] = instance.signature

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )

        def on_module_end(
            self,
            call_id: str,
            outputs: Optional[Any],
            exception: Optional[Exception] = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], serialize_dspy_objects(outputs), exception
                )

        def on_tool_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )

        def on_tool_end(
            self,
            call_id: str,
            outputs: Optional[dict[str, Any]],
            exception: Optional[Exception] = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id], serialize_dspy_objects(outputs), exception
                )
