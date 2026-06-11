"""Auto-link GenAI OTel spans to eval predictions.

When a GenAI OTel span ends during an active ``Evaluation.predict_and_score``
call, the :class:`EvalLinkSpanProcessor` automatically populates a
:class:`GenAISpanRef` on the predict_and_score call summary — no user code
required.

It also injects eval metadata (call ID, evaluation name, project) onto the
span so the agent traces UI can deep-link and filter by eval run.

Register this processor alongside the ``BatchSpanProcessor`` during
``_setup_session_tracing`` in ``weave_init.py``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from weave_server_sdk import models as tsi

from weave.evaluation.eval import (
    _attach_genai_span_ref_to_call_summary,
    _current_eval_predict_and_score_call,
    _find_current_evaluate_call,
    _find_current_predict_and_score_call,
)
from weave.trace_server import constants

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from weave.trace.call import Call

logger = logging.getLogger(__name__)

# GenAI semantic convention attribute that identifies a span as a GenAI operation.
# It is available as GEN_AI_OPERATION_NAME in opentelemetry.semconv._incubating, but
# given it's a private module and subject to change, I don't want to depend on it for
# now.
# TODO: Use the official semconv when this standard moves out of _incubating
_GENAI_OPERATION_NAME_ATTR = "gen_ai.operation.name"


def _get_evaluation_name() -> str | None:
    """Find the parent evaluate call and return the eval display name."""
    call = _find_current_evaluate_call()
    if call is None:
        return None
    name = call.display_name
    return name if isinstance(name, str) else None


class EvalLinkSpanProcessor(SpanProcessor):
    """OTel SpanProcessor that auto-links GenAI spans to eval predictions.

    When ``on_start`` the processor injects eval context attributes (call ID,
    evaluation name, project) onto the span for reverse lookup and filtering
    in the agent traces UI.

    When ``on_end`` fires, it attaches a ``GenAISpanRef`` (trace_id + span_id)
    to the predict_and_score call summary so eval results can navigate to the
    underlying GenAI span.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Inject eval context attributes onto spans for reverse lookup.

        TODO(seanmor5): This might be a bit noisy since we tag every span created
        during a predict_and_score context, not just GenAI spans. This is because
        gen_ai.operation.name is typically set after span creation and is therefore
        not available at start time.  The query side can intersect with gen_ai.operation.name
        to narrow to GenAI spans.
        """
        call = self._find_predict_and_score_call()
        if call is None:
            return

        span.set_attribute(constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR, call.id)
        span.set_attribute(constants.EVAL_PROJECT_ID_SPAN_ATTR, call.project_id)

        eval_name = _get_evaluation_name()
        if eval_name:
            span.set_attribute(constants.EVAL_EVALUATION_NAME_SPAN_ATTR, eval_name)

    def on_end(self, span: ReadableSpan) -> None:
        """Auto-populate GenAISpanRef when a GenAI span ends during an eval."""
        attrs = span.attributes or {}
        if _GENAI_OPERATION_NAME_ATTR not in attrs:
            return

        call = self._find_predict_and_score_call()
        if call is None:
            return

        ctx = span.context
        if ctx is None or not ctx.is_valid:
            return

        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")

        ref = tsi.GenAISpanRef(trace_id=trace_id, span_id=span_id)
        _attach_genai_span_ref_to_call_summary(call, ref)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    @staticmethod
    def _find_predict_and_score_call() -> Call | None:
        """Find the active predict_and_score call via ContextVar or stack walk.

        Two lookup strategies are needed because the declarative and imperative
        eval paths manage the call stack differently:

        - Declarative (Evaluation.evaluate): predict_and_score is a real @op,
          so it appears on the weave call stack and the stack walk finds it.
        - Imperative (EvaluationLogger.log_prediction): the call stack is
          explicitly set to [predict_call] only, so predict_and_score is NOT
          on the stack.  Instead, ScoreLogger.__enter__ sets the ContextVar
          via _active_eval_prediction_context.
        """
        return (
            _current_eval_predict_and_score_call.get()
            or _find_current_predict_and_score_call()
        )
