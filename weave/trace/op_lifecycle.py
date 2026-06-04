"""Shared per-call lifecycle logic for the ``@op`` execution paths.

Historically, the four execution variants in ``op.py`` — sync function, async
function, sync generator, and async generator — each defined their own
byte-identical ``finish()`` closure to run ``client.finish_call`` exactly once,
apply the op's finish post-processor, and pop the call off the context stack.
That duplication meant any change to finish semantics had to be made in four
places and could not be unit-tested without driving a full op execution.

This module extracts that logic into :class:`CallFinisher`, a small object that
owns the finish-once semantics for a single call and can be tested in isolation.
The error-message templates used on the call-creation/finish paths live here too,
since they are part of the same lifecycle concern.
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Any

from weave.trace.context import call_context
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.util import log_once

if TYPE_CHECKING:
    from weave.trace.call import Call
    from weave.trace.op_protocol import Op
    from weave.trace.weave_client import WeaveClient

logger = logging.getLogger(__name__)

# Error-message templates for the op call lifecycle. Kept here (rather than in
# op.py) so CallFinisher can reference ON_OUTPUT_MSG without a circular import;
# re-exported from op.py for backwards compatibility.
CALL_CREATE_MSG = "Error creating call:\n{}"
ASYNC_CALL_CREATE_MSG = "Error creating async call:\n{}"
ON_OUTPUT_MSG = "Error capturing call output:\n{}"


class CallFinisher:
    """Owns the finish-once semantics for a single op call.

    A single call may have ``finish`` invoked from several places (normal return,
    an exception handler, ``GeneratorExit``, or an accumulator signalling end), so
    this object guarantees the underlying ``client.finish_call`` runs at most once.
    On the first call it applies the op's finish post-processor, forwards to
    ``client.finish_call``, and — regardless of outcome — pops the call from the
    context stack if it is still current.

    Instances are callable with the same ``(output, exception)`` signature as the
    closures they replace, so they can be passed anywhere a finish callback is
    expected (e.g. accumulator iterators, on-output handlers).
    """

    def __init__(
        self,
        op: Op,
        call: Call,
        client: WeaveClient,
        *,
        require_explicit_finish: bool = False,
    ) -> None:
        self._op = op
        self._call = call
        self._client = client
        self._require_explicit_finish = require_explicit_finish
        # Public so the generator paths can decide whether they still need to
        # finish on an error path (mirrors the old ``nonlocal has_finished``).
        self.has_finished = False

    def __call__(
        self, output: Any = None, exception: BaseException | None = None
    ) -> None:
        if self._require_explicit_finish:
            return

        if self.has_finished:
            return
        self.has_finished = True

        try:
            # Apply any post-processing to the accumulated state if needed.
            try:
                # getattr-with-default preserves the original defensive access;
                # the op decorator always sets this attribute, but tightening it
                # is deferred so this stays a pure structural refactor.
                if processor := getattr(self._op, "_on_finish_post_processor", None):
                    output = processor(output)
            except Exception:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))

            self._client.finish_call(
                self._call,
                output,
                exception,
                op=self._op,
            )
        finally:
            # Only pop the call context if we're the current call.
            current_call = call_context.get_current_call()
            if current_call and current_call.id == self._call.id:
                call_context.pop_call(self._call.id)
