"""V2 implementation of EvaluationLogger.

Dispatched to when ``weave.trace.settings.should_use_v2_eval_logger()`` is
true (``WEAVE_USE_V2_EVAL_LOGGER=1`` / ``use_v2_eval_logger=True``).

The V2 trace server exposes a dedicated object-model for evaluations:
``evaluation_create``, ``evaluation_run_create``, ``prediction_create``,
``score_create``, ``evaluation_run_finish``.

Wire-in strategy
----------------

The V1 imperative path already emits the full evaluation call graph
(``Evaluation.evaluate``, ``Evaluation.predict_and_score``,
``Model.predict``, scorer calls, ``Evaluation.summarize``). The V2
*call* APIs (``evaluation_run_create``, ``prediction_create``,
``score_create``, ``evaluation_run_finish``) internally emit the same
call graph via ``call_start``/``call_end``, so invoking them in
addition to V1 would double-emit.

Rather than duplicate the V1 call graph, the V2 implementation inherits
from the V1 ``EvaluationLogger`` and exposes V2-specific hooks
(``_v2_on_init``, ``_v2_on_prediction``, ``_v2_on_score``,
``_v2_on_summary``). A concrete integration that replaces the V1 call
emission with V2 API calls can be layered behind these hooks once the
server-side V2 paths are the sole source of truth.

Today the hooks intentionally no-op so that existing V1 tests continue
to pass against the V2 logger — confirming the dispatcher, settings,
and parametrization scaffolding are wired up correctly end-to-end.
"""

from __future__ import annotations

import logging
from typing import Any

from weave.evaluation.eval_imperative_v1 import (
    EvaluationLogger as _V1EvaluationLogger,
)
from weave.evaluation.eval_imperative_v1 import (
    ScoreLogger as _V1ScoreLogger,
)
from weave.evaluation.eval_imperative_v1 import (
    ScoreType,
)
from weave.flow.scorer import Scorer
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


def _ref_str(obj: Any) -> str | None:
    """Return a weave:// ref URI for a saved weave object, or None."""
    ref = getattr(obj, "ref", None)
    if ref is None:
        return None
    uri = getattr(ref, "uri", None)
    if callable(uri):
        try:
            value = uri()
        except Exception:
            return None
    else:
        value = uri
    if isinstance(value, str):
        return value
    return None


class ScoreLogger(_V1ScoreLogger):
    """V2 ScoreLogger.

    Delegates to V1 and calls the V2 ``_v2_on_score`` hook after each score
    is finished.
    """

    def __init__(
        self,
        *args: Any,
        v2_parent: EvaluationLogger | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._v2_parent = v2_parent

    def _finish_score_call(
        self,
        score_call: Any,
        scorer: Scorer,
        score_value: ScoreType | None = None,
        exception: BaseException | None = None,
    ) -> None:
        super()._finish_score_call(score_call, scorer, score_value, exception)
        if (
            self._v2_parent is not None
            and exception is None
            and score_value is not None
        ):
            try:
                self._v2_parent._v2_on_score(self, scorer, score_value)
            except Exception:
                logger.debug("V2 _v2_on_score hook failed", exc_info=True)

    async def alog_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        await super().alog_score(scorer, score)
        if self._v2_parent is not None:
            try:
                prepared = self._prepare_scorer(scorer)
                self._v2_parent._v2_on_score(self, prepared, score)
            except Exception:
                logger.debug("V2 _v2_on_score hook failed", exc_info=True)


class EvaluationLogger(_V1EvaluationLogger):
    """V2 EvaluationLogger.

    Inherits V1's tracing behavior and exposes hooks (``_v2_on_init``,
    ``_v2_on_prediction``, ``_v2_on_score``, ``_v2_on_summary``) as extension
    points for a V2-API-driven integration. See module docstring.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._v2_evaluation_ref: str | None = None
        super().__init__(*args, **kwargs)
        try:
            self._v2_on_init()
        except Exception:
            logger.debug("V2 _v2_on_init hook failed", exc_info=True)

    def _v2_on_init(self) -> None:
        """Hook called at the end of __init__.

        Persists the evaluation via the V2 ``evaluation_create`` object API
        when a dataset ref is available.
        """
        wc = require_weave_client()
        dataset_ref = _ref_str(self.dataset)
        if dataset_ref is None:
            return
        eval_name = (
            self.name or getattr(self._pseudo_evaluation, "name", None) or "Evaluation"
        )
        try:
            res = wc.server.evaluation_create(
                tsi.EvaluationCreateReq(
                    project_id=wc.project_id,
                    name=eval_name,
                    dataset=dataset_ref,
                    scorers=[],
                    eval_attributes=self.eval_attributes or None,
                )
            )
            self._v2_evaluation_ref = res.evaluation_ref
        except Exception:
            logger.debug("V2 evaluation_create failed", exc_info=True)

    def _v2_on_prediction(self, pred: ScoreLogger, output: Any) -> None:
        """Hook called each time a prediction is finished."""

    def _v2_on_score(self, pred: ScoreLogger, scorer: Scorer, score: ScoreType) -> None:
        """Hook called each time a score is recorded."""

    def _v2_on_summary(self, summary: dict | None) -> None:
        """Hook called at the end of log_summary."""

    def log_prediction(self, inputs: dict[str, Any], output: Any = None) -> ScoreLogger:
        v1_pred = super().log_prediction(inputs=inputs, output=output)
        pred = ScoreLogger(
            predict_and_score_call=v1_pred.predict_and_score_call,
            evaluate_call=v1_pred.evaluate_call,
            predict_call=v1_pred.predict_call,
            predefined_scorers=v1_pred.predefined_scorers,
            v2_parent=self,
        )
        pred._predict_output = v1_pred._predict_output
        try:
            idx = self._accumulated_predictions.index(v1_pred)
            self._accumulated_predictions[idx] = pred
        except ValueError:
            self._accumulated_predictions.append(pred)
        return pred

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        super().log_summary(summary=summary, auto_summarize=auto_summarize)
        try:
            self._v2_on_summary(summary)
        except Exception:
            logger.debug("V2 _v2_on_summary hook failed", exc_info=True)
