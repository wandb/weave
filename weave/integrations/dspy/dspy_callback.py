from __future__ import annotations

from typing import Any

import weave
from weave.integrations.dspy.dspy_utils import (
    dictify,
    dspy_postprocess_inputs,
    dspy_postprocess_outputs,
    get_op_name_for_callback,
)
from weave.trace.call import Call
from weave.trace.context import weave_client_context as weave_client_context

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
            outputs: Any | None,
            exception: Exception | None = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            # Just finish the call normally - prediction logging is handled by monkey-patching
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id],
                    dspy_postprocess_outputs(outputs),
                    exception,
                )

        def on_lm_start(
            self,
            call_id: str,
            instance: Any,
            inputs: dict[str, Any],
        ) -> None:
            """A handler triggered when __call__ method of dspy.LM instance is called.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                instance: The LM instance.
                inputs: The inputs to the LM's __call__ method. Each arguments is stored as
                    a key-value pair in a dictionary.
            """
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

            op_name = get_op_name_for_callback(instance, inputs)
            self._call_map[call_id] = gc.create_call(
                op_name,
                inputs=dspy_postprocess_inputs(inputs),
                display_name=op_name,
            )

        def on_lm_end(
            self,
            call_id: str,
            outputs: dict[str, Any] | None,
            exception: Exception | None = None,
        ) -> None:
            """A handler triggered after __call__ method of dspy.LM instance is executed.

            Args:
                call_id: A unique identifier for the call. Can be used to connect start/end handlers.
                outputs: The outputs of the LM's __call__ method. If the method is interrupted by
                    an exception, this will be None.
                exception: If an exception is raised during the execution, it will be stored here.
            """
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id],
                    dspy_postprocess_outputs(outputs),
                    exception,
                )

        def on_tool_start(
            self, call_id: str, instance: Any, inputs: dict[str, Any]
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if instance is not None:
                inputs = {"self": dictify(instance), **inputs}

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
            outputs: dict[str, Any] | None,
            exception: Exception | None = None,
        ) -> None:
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(
                    self._call_map[call_id],
                    dspy_postprocess_outputs(outputs),
                    exception,
                )
