"""V2 implementation of EvaluationLogger.

Standalone implementation (not a subclass of V1) that routes through the
V2 trace server APIs:

- ``evaluation_create`` — persists the Evaluation object.
- ``evaluation_run_create`` — opens an ``Evaluation.evaluate`` call.
- ``prediction_create`` — opens ``Evaluation.predict_and_score`` and
  ``Model.predict`` calls and records the prediction output.
- ``prediction_finish`` — closes ``Evaluation.predict_and_score`` with
  the aggregated ``{"output", "scores", "model_latency"}`` payload.
- ``score_create`` — records a score and its ``{scorer_name}`` scorer
  call (matching V1's op name convention).
- ``evaluation_run_finish`` — emits ``Evaluation.summarize`` and closes
  the evaluation run with the caller-supplied summary.

The server-side V2 impl now matches V1's call graph (op names,
``_weave_eval_meta`` attribute markers, summary output shape), so most
V1 EvaluationLogger tests pass unchanged under V2.

Known gaps (tests using these behaviors are marked ``v1_only``):

- Child LLM calls made inside a ``log_prediction`` / ``log_score``
  context manager are not re-parented to the V2-created predict call
  (V2 creates calls via the server without surfacing client-side ``Call``
  objects for ``call_context`` to push).
- ``set_view`` persistence — V2 has no server-side views API yet.
- ``_pseudo_evaluation`` / ``get_infer_method`` — V1-internal helpers
  that don't translate directly to V2.
"""

from __future__ import annotations

import asyncio
import atexit
import datetime
import json
import logging
import types
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any, TypeVar, cast, overload

from typing_extensions import Self

from weave.dataset.dataset import Dataset
from weave.evaluation.eval_imperative_v1 import (
    IMPERATIVE_EVAL_MARKER,
    _cast_to_cls,
    _cast_to_imperative_dataset,
    _default_dataset_name,
)
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.table import Table
from weave.trace.util import Thread
from weave.trace_server import trace_server_interface as tsi
from weave.utils.sentinel import NOT_SET, _NotSetType

logger = logging.getLogger(__name__)

T = TypeVar("T")
ScoreType = float | bool | dict


_active_evaluation_loggers: list[EvaluationLogger] = []


def _cleanup_all_evaluations() -> None:
    for eval_logger in list(_active_evaluation_loggers):
        try:
            if not eval_logger._is_finalized:
                eval_logger.finish()
        except Exception:
            logger.exception("Error during cleanup of V2 EvaluationLogger")


atexit.register(_cleanup_all_evaluations)


_current_score: ContextVar[ScoreType | None] = ContextVar(
    "v2_current_score", default=None
)


@contextmanager
def _set_current_score(score: ScoreType) -> Iterator[None]:
    token = _current_score.set(score)
    try:
        yield
    finally:
        _current_score.reset(token)


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
    wc = require_weave_client()
    existing = _ref_str(obj)
    if existing is not None:
        return existing
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
        inputs: dict[str, Any],
        output: Any,
    ) -> None:
        self._parent = parent
        self._prediction_id = prediction_id
        self._inputs = inputs
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
        # ``{"output", "scores", "model_latency"}`` payload (V1 parity).
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
    """V2 EvaluationLogger — uses the V2 trace server APIs."""

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

        _active_evaluation_loggers.append(self)

    @property
    def ui_url(self) -> str | None:
        # V2 evaluation_run_create returns only an ID; building a UI URL would
        # require entity/project/id formatting not provided by the API today.
        return None

    @property
    def attributes(self) -> dict[str, Any]:
        return self.eval_attributes | IMPERATIVE_EVAL_MARKER

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
            inputs=inputs,
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
        if exception is not None:
            # Close the Evaluation.evaluate call with the exception directly;
            # the V2 ``evaluation_run_finish`` API has no exception path, and
            # emitting a summarize call on failure would be misleading.
            try:
                wc.server.call_end(
                    tsi.CallEndReq(
                        end=tsi.EndedCallSchemaForInsert(
                            project_id=wc.project_id,
                            id=self._evaluation_run_id,
                            ended_at=datetime.datetime.now(datetime.timezone.utc),
                            output=None,
                            summary={},
                            exception=json.dumps(
                                {
                                    "type": type(exception).__name__,
                                    "message": str(exception),
                                }
                            ),
                        )
                    )
                )
            except Exception:
                logger.exception("V2 call_end (failure path) failed")
        else:
            try:
                wc.server.evaluation_run_finish(
                    tsi.EvaluationRunFinishReq(
                        project_id=wc.project_id,
                        evaluation_run_id=self._evaluation_run_id,
                        summary=summary,
                    )
                )
            except Exception:
                logger.exception("V2 evaluation_run_finish failed")
        self._is_finalized = True
        if self in _active_evaluation_loggers:
            _active_evaluation_loggers.remove(self)

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
        # V2 stores views inside the evaluation run's summary under
        # ``weave.views``. This is a placeholder wire-in that mirrors V1's
        # ``set_call_view`` shape; actual persistence via V2 is TBD when the
        # server grows a native views API.
        if isinstance(content, str) and len(content) == 0:
            raise ValueError("Content cannot be an empty string")
        if not isinstance(name, str) or len(name) == 0:
            raise ValueError("`name` must be a non-empty string")
        logger.debug("V2 set_view(%s) is not yet persisted to the server", name)

    def __del__(self) -> None:
        try:
            if not self._is_finalized:
                self.finish()
        except Exception:
            pass


# Reuse V1's threading helper so that sync log_score() called from an async
# context doesn't block the event loop.
def _run_sync_in_thread(coro_factory: Callable[[], Any]) -> Any:
    result: list[Any] = [None]
    err: list[BaseException | None] = [None]

    def runner() -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result[0] = loop.run_until_complete(coro_factory())
            finally:
                loop.close()
        except BaseException as e:
            err[0] = e

    t = Thread(target=runner)
    t.start()
    t.join()
    if err[0] is not None:
        raise err[0]
    return result[0]
