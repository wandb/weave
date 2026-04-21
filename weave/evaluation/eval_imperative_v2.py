"""V2 implementation of EvaluationLogger.

Standalone implementation that routes through the V2 trace server APIs:

- ``evaluation_create`` — persists the Evaluation object.
- ``evaluation_run_create`` — opens an ``Evaluation.evaluate`` call.
- ``prediction_create`` — opens ``Evaluation.predict_and_score`` and
  ``Model.predict`` calls and records the prediction output.
- ``prediction_finish`` — closes ``Evaluation.predict_and_score`` with
  the aggregated ``{"output", "scores", "model_latency"}`` payload.
- ``score_create`` — records a score and its ``{scorer_name}`` scorer call.
- ``evaluation_run_finish`` — emits ``Evaluation.summarize`` and closes
  the evaluation run with the caller-supplied summary (or a caller-supplied
  exception when the run failed).
"""

from __future__ import annotations

import asyncio
import json
import logging
import types
from threading import Lock
from typing import Any, cast, overload

from typing_extensions import Self

from weave.dataset.dataset import Dataset
from weave.evaluation.eval_imperative_v1 import (
    _cast_to_cls,
    _cast_to_imperative_dataset,
    _default_dataset_name,
)
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.table import Table
from weave.trace_server import trace_server_interface as tsi
from weave.utils.sentinel import NOT_SET, _NotSetType

logger = logging.getLogger(__name__)

ScoreType = float | bool | dict


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


def _publish(obj: Any, fallback_name: str) -> str | None:
    """Publish ``obj`` and return its ref URI, or None on failure."""
    existing = _ref_str(obj)
    if existing is not None:
        return existing
    wc = require_weave_client()
    name = getattr(obj, "name", None) or fallback_name
    try:
        ref = wc._save_object(obj, name)
    except Exception:
        logger.exception("V2: failed to publish %s", name)
        return None
    return (
        ref.uri()
        if callable(getattr(ref, "uri", None))
        else str(getattr(ref, "uri", ""))
    )


class _ScorerCache:
    """Caches Scorer instances and their published refs by serialized key."""

    def __init__(self) -> None:
        self._scorers: dict[str, Scorer] = {}
        self._refs: dict[str, str] = {}
        self._lock = Lock()

    def prepare(self, scorer: Scorer | dict | str) -> tuple[Scorer, str | None]:
        with self._lock:
            if isinstance(scorer, Scorer):
                key = f"instance:{id(scorer)}:{scorer.name}"
                instance = scorer
            else:
                key = f"value:{json.dumps(scorer, sort_keys=True, default=str)}"
                instance = self._scorers.get(key) or _cast_to_cls(Scorer)(scorer)
                self._scorers[key] = instance
            cached_ref = self._refs.get(key)
        if cached_ref is not None:
            return instance, cached_ref
        ref = _publish(instance, instance.__class__.__name__)
        if ref is not None:
            with self._lock:
                self._refs[key] = ref
        return instance, ref


class _LogScoreContext:
    """Context manager returned by ``log_score`` when no value is given yet."""

    def __init__(
        self,
        score_logger: ScoreLogger,
        scorer: Scorer | dict | str,
    ) -> None:
        self._score_logger = score_logger
        self._scorer = scorer
        self._value: ScoreType | None = None

    @property
    def value(self) -> ScoreType | None:
        return self._value

    @value.setter
    def value(self, val: ScoreType) -> None:
        self._value = val

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._value is not None and exc_type is None:
            self._score_logger.log_score(self._scorer, self._value)
        elif exc_type is None:
            scorer_name = (
                self._scorer.name
                if isinstance(self._scorer, Scorer)
                else str(self._scorer)
            )
            raise ValueError(
                f"Score value was not set for scorer '{scorer_name}'. "
                "Please set score_ctx.value within the context manager."
            )


class ScoreLogger:
    """V2 ScoreLogger.

    Wraps a V2 ``prediction_id`` and records scores via ``score_create``.
    """

    def __init__(
        self,
        *,
        parent: EvaluationLogger,
        prediction_id: str,
        output: Any,
    ) -> None:
        self._parent = parent
        self._prediction_id = prediction_id
        self._predict_output = output
        self._captured_scores: dict[str, ScoreType] = {}
        self._has_finished: bool = False

    @property
    def output(self) -> Any:
        return self._predict_output

    @output.setter
    def output(self, value: Any) -> None:
        self._predict_output = value

    def _prepare_scorer(self, scorer: Scorer | dict | str) -> tuple[Scorer, str | None]:
        instance, ref = self._parent._scorer_cache.prepare(scorer)
        if self._parent.scorers:
            scorer_name = cast(str, instance.name)
            if scorer_name not in self._parent.scorers:
                logger.warning(
                    "Scorer '%s' is not in the predefined scorers list. "
                    "Expected one of: %s",
                    scorer_name,
                    sorted(self._parent.scorers),
                )
        return instance, ref

    @overload
    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None: ...

    @overload
    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: _NotSetType = NOT_SET,
    ) -> _LogScoreContext: ...

    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType | _NotSetType = NOT_SET,
    ) -> _LogScoreContext | None:
        if score is NOT_SET:
            return _LogScoreContext(self, scorer)

        score_value = cast(ScoreType, score)
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        instance, scorer_ref = self._prepare_scorer(scorer)
        scorer_name = cast(str, instance.name)

        if scorer_ref is not None:
            value: float | None
            if score_value is None:
                value = None
            elif isinstance(score_value, (int, float, bool)):
                value = float(score_value)
            else:
                value = None
            wc = require_weave_client()
            try:
                wc.server.score_create(
                    tsi.ScoreCreateReq(
                        project_id=wc.project_id,
                        prediction_id=self._prediction_id,
                        scorer=scorer_ref,
                        value=value,
                        evaluation_run_id=self._parent._evaluation_run_id,
                    )
                )
            except Exception:
                logger.debug("V2 score_create failed", exc_info=True)

        self._captured_scores[scorer_name] = score_value
        return None

    async def alog_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        # score_create is synchronous server-side; run in a worker to avoid
        # blocking the event loop.
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.log_score(scorer, score)
        )

    def finish(self, output: Any | None = None) -> None:
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return
        if output is not None:
            self._predict_output = output
        self._has_finished = True

        # Close the server-side predict_and_score call with the aggregated
        # ``{"output", "scores", "model_latency"}`` payload.
        wc = require_weave_client()
        try:
            wc.server.prediction_finish(
                tsi.PredictionFinishReq(
                    project_id=wc.project_id,
                    prediction_id=self._prediction_id,
                )
            )
        except Exception:
            logger.debug("V2 prediction_finish failed", exc_info=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if not self._has_finished:
            self.finish()


class EvaluationLogger:
    """V2 EvaluationLogger — uses the V2 trace server APIs.

    Note: if the caller forgets to invoke ``finish()`` / ``log_summary()`` /
    ``fail()``, the ``Evaluation.evaluate`` call started by
    ``evaluation_run_create`` will remain in-flight on the server. This
    matches the general ``call_start`` / ``call_end`` contract and is
    considered caller responsibility.
    """

    def __init__(
        self,
        name: str | None = None,
        model: Model | dict | str | None = None,
        dataset: Dataset | list[dict] | str | None = None,
        eval_attributes: dict[str, Any] | None = None,
        scorers: list[str] | None = None,
    ) -> None:
        self.name = name
        self.scorers = scorers
        self.eval_attributes = eval_attributes if eval_attributes is not None else {}

        if model is None:
            model = Model()
        self.model: Model = _cast_to_cls(Model)(model)

        if dataset is None:
            dataset = Dataset(rows=Table([{"dataset_id": _default_dataset_name()}]))
        self.dataset: Dataset = _cast_to_imperative_dataset(dataset)

        self._scorer_cache = _ScorerCache()
        self._accumulated_predictions: list[ScoreLogger] = []
        self._is_finalized: bool = False

        wc = require_weave_client()

        dataset_ref = _publish(self.dataset, "Dataset")
        self._model_ref = _publish(self.model, self.model.__class__.__name__)

        if dataset_ref is None:
            raise RuntimeError("V2 EvaluationLogger: failed to publish dataset")
        if self._model_ref is None:
            raise RuntimeError("V2 EvaluationLogger: failed to publish model")

        eval_name = (
            self.name
            or f"{getattr(self.dataset, 'name', None) or 'dataset'}-evaluation"
        )
        eval_res = wc.server.evaluation_create(
            tsi.EvaluationCreateReq(
                project_id=wc.project_id,
                name=eval_name,
                dataset=dataset_ref,
                scorers=[],
                eval_attributes=self.eval_attributes or None,
            )
        )
        self._evaluation_ref: str = eval_res.evaluation_ref

        run_res = wc.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=wc.project_id,
                evaluation=self._evaluation_ref,
                model=self._model_ref,
                eval_attributes=self.eval_attributes or None,
            )
        )
        self._evaluation_run_id: str = run_res.evaluation_run_id

    @property
    def ui_url(self) -> str | None:
        # V2 evaluation_run_create returns only an ID; building a UI URL would
        # require entity/project/id formatting not provided by the API today.
        return None

    def log_prediction(self, inputs: dict[str, Any], output: Any = None) -> ScoreLogger:
        wc = require_weave_client()
        res = wc.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=wc.project_id,
                model=self._model_ref,
                inputs=inputs,
                output=output,
                evaluation_run_id=self._evaluation_run_id,
            )
        )
        pred = ScoreLogger(
            parent=self,
            prediction_id=res.prediction_id,
            output=output,
        )
        self._accumulated_predictions.append(pred)
        return pred

    def log_example(
        self,
        inputs: dict[str, Any],
        output: Any,
        scores: dict[str, ScoreType],
    ) -> None:
        if self._is_finalized:
            raise ValueError(
                "Cannot log example after evaluation has been finalized. "
                "Call log_example before calling finish() or log_summary()."
            )
        pred = self.log_prediction(inputs=inputs, output=output)
        for scorer_name, score_value in scores.items():
            pred.log_score(scorer_name, score_value)
        pred.finish()

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        if self._is_finalized:
            logger.warning("(NO-OP): Evaluation already finalized, cannot log summary.")
            return

        if summary is None:
            summary = {}

        if auto_summarize:
            data_to_summarize = [
                pred._captured_scores for pred in self._accumulated_predictions
            ]
            summary_data = auto_summarize_fn(data_to_summarize)
        else:
            summary_data = summary

        final_summary: dict[str, Any] = {}
        if summary_data:
            final_summary = dict(summary_data)
        final_summary["output"] = summary

        self._finalize(summary=final_summary)

    def _finalize(
        self,
        summary: dict[str, Any] | None = None,
        exception: BaseException | None = None,
    ) -> None:
        if self._is_finalized:
            return
        wc = require_weave_client()
        exception_payload: str | None = None
        if exception is not None:
            exception_payload = json.dumps(
                {
                    "type": type(exception).__name__,
                    "message": str(exception),
                }
            )
        try:
            wc.server.evaluation_run_finish(
                tsi.EvaluationRunFinishReq(
                    project_id=wc.project_id,
                    evaluation_run_id=self._evaluation_run_id,
                    summary=summary,
                    exception=exception_payload,
                )
            )
        except Exception:
            logger.exception("V2 evaluation_run_finish failed")
        self._is_finalized = True

    def finish(self, exception: BaseException | None = None) -> None:
        if self._is_finalized:
            return
        self._finalize(summary=None, exception=exception)

    def fail(self, exception: BaseException) -> None:
        self.finish(exception=exception)

    def set_view(
        self,
        name: str,
        content: Any,
        *,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        raise NotImplementedError(
            "V2 EvaluationLogger does not yet support set_view; the V2 trace "
            "server has no native views API. Track or contribute at "
            "weave.evaluation."
        )
