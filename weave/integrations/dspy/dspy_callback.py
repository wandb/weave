from typing import Any, Optional

import weave
from weave.integrations.dspy.dspy_utils import (
    dspy_postprocess_inputs,
    dump_dspy_objects,
    get_op_name_for_callback,
)
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.serialization.serialize import dictify
from weave.trace.weave_client import Call

import_failed = False

try:
    from dspy.utils.callback import BaseCallback
except ImportError:
    import_failed = True

if not import_failed:

    class WeaveCallback(BaseCallback):
        def __init__(self) -> None:
            self._call_map: dict[str, Call] = {}

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
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )

        def on_tool_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            gc = weave_client_context.require_weave_client()

            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

            # TODO: Should we do this? Have to ask Ayush tomorrow.
            if hasattr(instance, "func"):
                instance.func = weave.op(instance.func)

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
                    self._call_map[call_id], dump_dspy_objects(outputs), exception
                )
