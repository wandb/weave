"""Op lifecycle management for execution hooks.

This module provides a lifecycle manager for ops that handles execution hooks
like input processing, output transformation, and finish callbacks. These
hooks allow integrations to customize op execution behavior without cluttering
the Op protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from weave.trace.call import Call
    from weave.trace.op_protocol import Op, ProcessedInputs
else:
    # Forward references for runtime
    Op = Any
    ProcessedInputs = Any
    Call = Any

OnInputHandlerType = Callable[[Op, tuple, dict], Optional[ProcessedInputs]]
FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, dict], Any]
OnFinishHandlerType = Callable[[Call, Any, Optional[BaseException]], None]


@dataclass
class OpLifecycleManager:
    """Manages lifecycle hooks for op execution.

    Lifecycle hooks allow integrations to customize op execution behavior at
    different stages:
    - input: Transform inputs before function execution
    - output: Transform outputs after function execution
    - finish: Customize what gets logged when a call finishes
    - finish_post_processor: Post-process output before finishing

    These hooks differ from postprocess_inputs/postprocess_output in that they
    can modify execution flow, not just what gets logged.
    """

    input: OnInputHandlerType | None = None
    output: OnOutputHandlerType | None = None
    finish: OnFinishHandlerType | None = None
    finish_post_processor: Callable[[Any], Any] | None = None
