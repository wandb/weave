import rich
from typing import Any, Dict, Optional
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.patcher import Patcher
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

        def on_lm_start(self, call_id: str, instance: Any, inputs: Dict[str, Any]):
            print("on_lm_start")
            gc = weave_client_context.require_weave_client()
            self._call_map[call_id] = gc.create_call(
                "dspy.LM", inputs=inputs, display_name="dspy.LM"
            )

        def on_lm_end(
            self,
            call_id: str,
            outputs: Optional[Any],
            exception: Optional[Exception] = None,
        ):
            print("on_lm_end")
            gc = weave_client_context.require_weave_client()
            if call_id in self._call_map:
                gc.finish_call(self._call_map[call_id], outputs, exception)
