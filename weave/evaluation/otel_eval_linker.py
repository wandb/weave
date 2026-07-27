"""Stamp eval metadata onto OTel spans created during eval predictions.

When an OTel span starts during an active ``Evaluation.predict_and_score`` call,
the :class:`EvalLinkSpanProcessor` injects eval metadata (call IDs, evaluation
name, project, row identity, trial index, and kind) onto the span so the agent
traces UI can find eval traces by querying promoted span columns.

Register this processor alongside the ``BatchSpanProcessor`` during
``_setup_conversation_tracing`` in ``weave_init.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from weave.evaluation.eval import (
    EvalSpanContext,
    _current_eval_predict_and_score_call,
    _current_eval_span_context,
    _find_current_evaluate_call,
    _find_current_predict_and_score_call,
)
from weave.trace_server import constants

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from weave.trace.call import Call


def _get_evaluation_name(call: Call | None) -> str | None:
    """Find the parent evaluate call and return the eval display name."""
    if call is None:
        return None
    name = call.display_name
    return name if isinstance(name, str) else None


class EvalLinkSpanProcessor(SpanProcessor):
    """OTel SpanProcessor that stamps eval metadata onto prediction spans.

    When ``on_start`` the processor injects eval context attributes (call ID,
    evaluation name, project) onto the span for reverse lookup and filtering
    in the agent traces UI.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Inject eval context attributes onto spans for reverse lookup.

        TODO(seanmor5): This might be a bit noisy since we tag every span created
        during a predict_and_score context, not just GenAI spans. This is because
        gen_ai.operation.name is typically set after span creation and is therefore
        not available at start time.  The query side can intersect with gen_ai.operation.name
        to narrow to GenAI spans.
        """
        eval_context = self._find_eval_span_context()
        if eval_context is None:
            return

        predict_and_score_call = eval_context.predict_and_score_call
        if predict_and_score_call.id is not None:
            span.set_attribute(
                constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
                predict_and_score_call.id,
            )
        span.set_attribute(
            constants.EVAL_PROJECT_ID_SPAN_ATTR, predict_and_score_call.project_id
        )

        if (
            eval_context.evaluate_call is not None
            and eval_context.evaluate_call.id is not None
        ):
            span.set_attribute(
                constants.EVAL_RUN_ID_SPAN_ATTR,
                eval_context.evaluate_call.id,
            )
        if eval_context.eval_kind is not None:
            span.set_attribute(constants.EVAL_KIND_SPAN_ATTR, eval_context.eval_kind)
        if eval_context.row_digest is not None:
            span.set_attribute(
                constants.EVAL_ROW_DIGEST_SPAN_ATTR,
                eval_context.row_digest,
            )
        if eval_context.example_id is not None:
            span.set_attribute(
                constants.EVAL_EXAMPLE_ID_SPAN_ATTR,
                eval_context.example_id,
            )
        if eval_context.trial_index is not None:
            span.set_attribute(
                constants.EVAL_TRIAL_INDEX_SPAN_ATTR,
                eval_context.trial_index,
            )

        eval_name = eval_context.evaluation_name or _get_evaluation_name(
            eval_context.evaluate_call
        )
        if eval_name:
            span.set_attribute(constants.EVAL_EVALUATION_NAME_SPAN_ATTR, eval_name)

    def on_end(self, span: ReadableSpan) -> None:
        return None

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

    @staticmethod
    def _find_eval_span_context() -> EvalSpanContext | None:
        """Find structured eval span context, with legacy stack fallback."""
        if (eval_context := _current_eval_span_context.get()) is not None:
            return eval_context

        predict_and_score_call = EvalLinkSpanProcessor._find_predict_and_score_call()
        if predict_and_score_call is None:
            return None

        evaluate_call = _find_current_evaluate_call()
        return EvalSpanContext(
            predict_and_score_call=predict_and_score_call,
            evaluate_call=evaluate_call,
            eval_kind="standard" if evaluate_call is not None else None,
            evaluation_name=_get_evaluation_name(evaluate_call),
        )
