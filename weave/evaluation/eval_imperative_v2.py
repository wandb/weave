"""Server-side imperative evaluation logger.

EvaluationLoggerV2 mirrors the public API of EvaluationLogger (V1) but is
implemented on top of the trace server's V2 evaluation endpoints
(`evaluation_create`, `evaluation_run_create/finish`, `prediction_create/
finish`, `score_create`, `scorer_create`, `model_create`, `dataset_create`)
instead of faking a weave.Evaluation call graph.

V1 predates those endpoints and drives a "pseudo" Evaluation: it injects
placeholder `predict`, `predict_and_score`, and `summarize` ops onto runtime
objects, smuggles outputs/scores/summaries between method boundaries through
ContextVars, and manually pokes the call stack. V2 speaks the server APIs
directly — no ContextVars, no method injection, no call-stack manipulation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import types
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, cast, overload

from typing_extensions import Self

# Number of concurrent in-flight V2 server calls per logger. One worker
# matches V1's `AsyncBatchProcessor` model: user code never blocks on the
# network, but writes serialize through a single background thread. This
# is also what in-process SQLite requires (it errors on concurrent writes
# with "database is locked"). Users on a remote HTTP backend who want more
# parallelism can bump this via the `max_workers` constructor arg.
_DEFAULT_MAX_WORKERS = 1

from weave.dataset.dataset import Dataset
from weave.evaluation._imperative_shared import (
    ScoreType,
    _active_evaluation_loggers,
    _cast_to_cls,
    _cast_to_imperative_dataset,
    _default_dataset_name,
    _sanitize_class_name,
    global_scorer_cache,
    scorer_to_cache_key,
)
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.trace.context.weave_client_context import (
    WeaveInitError,
    require_weave_client,
)
from weave.trace.op import is_tracing_setting_disabled
from weave.trace.refs import ObjectRef
from weave.trace_server import trace_server_interface as tsi
from weave.utils.project_id import from_project_id
from weave.utils.sentinel import NOT_SET, _NotSetType

logger = logging.getLogger(__name__)


def _synthesize_model_source(model: Model) -> str:
    """Placeholder source for models supplied as just a name or dict.

    V1 accepts models as bare strings or dicts, synthesizing a pydantic
    subclass at runtime. The V2 `model_create` endpoint requires source code,
    so when the user passes a non-real Model we emit a minimal valid class
    definition. The server stores it but never executes it.
    """
    name = _sanitize_class_name(model.name or model.__class__.__name__)
    return f"import weave\n\n\nclass {name}(weave.Model):\n    pass\n"


def _synthesize_scorer_source(scorer: Scorer) -> str:
    """Placeholder source for scorers supplied as just a name or dict."""
    return (
        "def score(*, output, inputs):\n"
        "    # Placeholder source emitted by EvaluationLoggerV2.\n"
        "    return None\n"
    )


def _object_ref_uri(entity: str, project: str, object_id: str, digest: str) -> str:
    """Build a canonical `weave:///...` object ref URI via `ObjectRef`."""
    return ObjectRef(entity=entity, project=project, name=object_id, _digest=digest).uri


@dataclass(frozen=True)
class _DatasetSpec:
    """Normalized dataset input: name + raw rows for the V2 dataset_create API."""

    name: str
    rows: list[dict]


def _resolve_dataset_spec(
    value: Dataset | list[dict] | str | None,
) -> _DatasetSpec:
    """Normalize a V1-style dataset input for V2."""
    if value is None:
        name = _default_dataset_name()
        return _DatasetSpec(name=name, rows=[{"dataset_id": name}])
    if isinstance(value, str):
        return _DatasetSpec(name=value, rows=[{"dataset_id": value}])
    if isinstance(value, list):
        return _DatasetSpec(name=_default_dataset_name(), rows=value)
    ds = _cast_to_imperative_dataset(value)
    rows = list(ds.rows)
    name = ds.name or _default_dataset_name()
    return _DatasetSpec(name=name, rows=rows)


class _LogScoreContextV2:
    """Context manager for deferred scoring in V2 (matches V1 semantics).

    Usage:
        with pred.log_score("quality") as score:
            result = compute(...)
            score.value = result
    """

    def __init__(
        self,
        score_logger: ScoreLoggerV2,
        scorer: Scorer,
    ) -> None:
        self._score_logger = score_logger
        self._scorer = scorer
        # Use NOT_SET so `score.value = None` is distinguishable from
        # "value was never set". V1 conflates the two; V2 keeps None valid.
        self._value: ScoreType | _NotSetType | None = NOT_SET

    @property
    def value(self) -> ScoreType | None:
        if isinstance(self._value, _NotSetType):
            return None
        return self._value

    @value.setter
    def value(self, val: ScoreType | None) -> None:
        self._value = val

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if exc_type is not None:
            return
        if isinstance(self._value, _NotSetType):
            # Not a type error — it's a state error about the caller not
            # having assigned `score_ctx.value` before the block ended. V1
            # raises ValueError here and the V1 contract test expects it.
            raise ValueError(  # noqa: TRY004
                f"Score value was not set for scorer '{self._scorer.name}'. "
                "Please set score_ctx.value within the context manager."
            )
        self._score_logger._submit_score(
            self._scorer, cast("ScoreType | None", self._value)
        )


class ScoreLoggerV2:
    """V2 counterpart of V1's ScoreLogger.

    Returned by `EvaluationLoggerV2.log_prediction`. Supports the same two
    usage patterns as V1: direct and context-manager.
    """

    def __init__(
        self,
        eval_logger: EvaluationLoggerV2,
        inputs: dict[str, Any],
        output: Any,
    ) -> None:
        self._eval_logger = eval_logger
        self._inputs = inputs
        self._output_buffer: Any = output
        self._prediction_id: str | None = None
        self._has_finished: bool = False
        self._captured_scores: dict[str, ScoreType | None] = {}
        # Future that resolves to `prediction_id` once `prediction_create`
        # returns. Set lazily the first time a score or finish is submitted.
        # Score and finish tasks chain off this so they never call the server
        # until the prediction exists, while still unblocking the caller.
        self._prediction_future: Future[str] | None = None
        # Futures for every score/finish task owned by this prediction; we
        # wait on these in `finish` to order `prediction_finish` after all
        # its scores, and at eval-level drain time.
        self._pending_futures: list[Future[Any]] = []

    @property
    def output(self) -> Any:
        return self._output_buffer

    @output.setter
    def output(self, value: Any) -> None:
        self._output_buffer = value

    # V1 exposes predefined_scorers for warning purposes; V2 mirrors it
    # through the eval_logger.
    @property
    def predefined_scorers(self) -> list[str] | None:
        return self._eval_logger.scorers

    def _ensure_prediction_future(self) -> Future[str]:
        """Submit ``prediction_create`` in the background (if not started).

        Returns a Future that will resolve to the new prediction_id. Safe to
        call from user code; does not block.
        """
        if self._prediction_future is not None:
            return self._prediction_future

        # One-time server init (dataset / scorers / model / evaluation /
        # evaluation_run) is kept synchronous: it runs a handful of serial
        # round-trips once per logger and it populates state that every
        # background task depends on (model_ref, evaluation_run_id, ...).
        self._eval_logger._ensure_initialized()
        assert self._eval_logger._server is not None
        assert self._eval_logger._model_ref is not None

        project_id = self._eval_logger._project_id
        model_ref = self._eval_logger._model_ref
        inputs = self._inputs
        output = self._output_buffer
        evaluation_run_id = self._eval_logger._evaluation_run_id
        server = self._eval_logger._server

        def _create() -> str:
            res = server.prediction_create(
                tsi.PredictionCreateReq(
                    project_id=project_id,
                    model=model_ref,
                    inputs=inputs,
                    output=output,
                    evaluation_run_id=evaluation_run_id,
                    wb_user_id=None,
                )
            )
            self._prediction_id = res.prediction_id
            return res.prediction_id

        self._prediction_future = self._eval_logger._submit(_create)
        return self._prediction_future

    @overload
    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType | None,
    ) -> None: ...

    @overload
    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: _NotSetType = NOT_SET,
    ) -> _LogScoreContextV2: ...

    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType | _NotSetType | None = NOT_SET,
    ) -> _LogScoreContextV2 | None:
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        prepared = self._eval_logger._prepare_scorer(scorer)

        if isinstance(score, _NotSetType):
            return _LogScoreContextV2(self, prepared)

        self._submit_score(prepared, score)
        return None

    async def alog_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType | None,
    ) -> None:
        # The V2 server interface is synchronous. V1's alog_score existed
        # because V1 piggybacked on `apply_scorer` which had an async path.
        # Here we just dispatch to a thread so callers in async frameworks
        # don't block their loop during network I/O.
        await asyncio.to_thread(self.log_score, scorer, score)

    def _submit_score(self, scorer: Scorer, score: ScoreType | None) -> None:
        scorer_name = cast(str, scorer.name)

        # Capture for auto-summarize regardless of server availability.
        self._captured_scores[scorer_name] = score

        if self._eval_logger._disabled:
            return

        prediction_future = self._ensure_prediction_future()
        server = self._eval_logger._server
        assert server is not None
        project_id = self._eval_logger._project_id
        evaluation_run_id = self._eval_logger._evaluation_run_id

        def _create_score() -> None:
            prediction_id = prediction_future.result()
            scorer_ref = self._eval_logger._get_or_create_scorer_ref(scorer)
            server.score_create(
                tsi.ScoreCreateReq(
                    project_id=project_id,
                    prediction_id=prediction_id,
                    scorer=scorer_ref,
                    value=score,
                    evaluation_run_id=evaluation_run_id,
                    wb_user_id=None,
                )
            )

        fut = self._eval_logger._submit(_create_score)
        self._pending_futures.append(fut)

    def finish(self, output: Any | None = None) -> None:
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return

        if output is not None:
            self._output_buffer = output

        if self._eval_logger._disabled:
            self._has_finished = True
            return

        prediction_future = self._ensure_prediction_future()
        # Snapshot scores + pending score futures now so that later user
        # mutations to `self._output_buffer` or `self._pending_futures` do
        # not affect what we send.
        scores_pending = list(self._pending_futures)
        output_to_send = self._output_buffer
        server = self._eval_logger._server
        assert server is not None
        project_id = self._eval_logger._project_id

        def _finish_prediction() -> None:
            prediction_id = prediction_future.result()
            # Make sure every score for this prediction has landed before we
            # close out the parent `predict_and_score` call (whose output
            # payload includes `scores_dict`, computed from score-child
            # queries at finish time).
            if scores_pending:
                wait(scores_pending)
            # `prediction_create` only emits `call_start` in the restructure;
            # `prediction_finish` owns the `call_end` with the final output.
            server.prediction_finish(
                tsi.PredictionFinishReq(
                    project_id=project_id,
                    prediction_id=prediction_id,
                    output=output_to_send,
                    wb_user_id=None,
                )
            )

        fut = self._eval_logger._submit(_finish_prediction)
        self._pending_futures.append(fut)
        self._has_finished = True

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


class EvaluationLoggerV2:
    """Imperative evaluation logger backed by V2 server APIs.

    This class matches the public API of `EvaluationLogger` (V1) but builds
    on top of the first-class V2 endpoints instead of a pseudo-Evaluation.
    Drop-in replacement for callers that don't depend on V1's exact call
    tree shape.

    ```python
    ev = weave.EvaluationLoggerV2()
    pred = ev.log_prediction(inputs={"q": "..."}, output="...")
    pred.log_score("correctness", 0.9)
    pred.finish()
    ev.log_summary({"avg_score": 0.9})
    ```
    """

    def __init__(
        self,
        name: str | None = None,
        model: Model | dict | str | None = None,
        dataset: Dataset | list[dict] | str | None = None,
        eval_attributes: dict[str, Any] | None = None,
        scorers: list[str] | None = None,
        *,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> None:
        self.name = name
        self.scorers = scorers
        self.eval_attributes = eval_attributes if eval_attributes is not None else {}
        self._max_workers = max_workers

        if model is None:
            model = Model()
        self.model: Model = _cast_to_cls(Model)(model)

        # Normalize the dataset to (name, rows). V1 wraps into Dataset+Table
        # internally; V2 sends rows to the server directly.
        self._dataset_spec = _resolve_dataset_spec(dataset)

        # Lifecycle state.
        self._is_finalized: bool = False
        self._initialized: bool = False
        self._accumulated_predictions: list[ScoreLoggerV2] = []

        # Disabled-mode detection. V1 returns an object that still captures
        # scores locally when WEAVE_DISABLED=true or no client exists; V2
        # mirrors that by skipping all server calls in this mode.
        self._disabled: bool = False
        # Use `FullTraceServerInterface` so mypy sees the V2 endpoints
        # (dataset_create, evaluation_run_create, etc.) that live on
        # `ObjectInterface` — those methods aren't on `TraceServerInterface`
        # but are present at runtime on every concrete backend.
        self._server: tsi.FullTraceServerInterface | None = None
        self._project_id: str = ""
        self._entity: str = ""
        self._project: str = ""
        try:
            wc = require_weave_client()
        except WeaveInitError:
            self._disabled = True
        else:
            if is_tracing_setting_disabled():
                self._disabled = True
            else:
                # All concrete backends satisfy FullTraceServerInterface; the
                # cast lets us call V2 endpoints that live on ObjectInterface.
                self._server = cast("tsi.FullTraceServerInterface", wc.server)
                self._project_id = wc.project_id
                self._entity, self._project = from_project_id(wc.project_id)

        # Server-side references populated on lazy init.
        self._dataset_ref: str | None = None
        self._model_ref: str | None = None
        self._evaluation_ref: str | None = None
        self._evaluation_run_id: str | None = None
        self._scorer_refs_by_name: dict[str, str] = {}

        # Background submission machinery. User-facing ``log_prediction`` /
        # ``log_score`` / ``finish`` calls enqueue work here and return
        # instantly; real server round-trips happen on the executor threads.
        # The executor is lazy so constructing a logger without using it
        # (e.g. in a disabled-mode or validation path) doesn't spin threads.
        self._executor: ThreadPoolExecutor | None = None
        # Protects `_scorer_refs_by_name` during concurrent
        # `_get_or_create_scorer_ref` calls across worker threads.
        self._scorer_lock = threading.Lock()
        # Every submitted future, for draining at log_summary/finish time.
        self._pending_futures: list[Future[Any]] = []

        _active_evaluation_loggers.append(self)

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="eval-logger-v2",
            )
        return self._executor

    def _submit(self, fn: Any) -> Future[Any]:
        """Submit a no-arg callable to the background executor."""
        executor = self._get_executor()
        fut = executor.submit(fn)
        self._pending_futures.append(fut)
        return fut

    def _drain_pending(self) -> None:
        """Wait for every in-flight background task to finish.

        Background failures are logged (matching V1's batch-processor
        behavior) but not re-raised — we want ``finish`` / ``log_summary``
        to succeed even if a transient server error dropped a score.
        """
        if not self._pending_futures:
            return
        wait(self._pending_futures)
        for fut in self._pending_futures:
            exc = fut.exception()
            if exc is not None:
                logger.exception("Background V2 server call failed", exc_info=exc)
        self._pending_futures.clear()

    @property
    def ui_url(self) -> str | None:
        """URL to the evaluation run in the Weave UI.

        V2 evaluation runs double as calls on the server (their IDs are valid
        call IDs), so the standard `/r/call/{id}` URL resolves.
        """
        if self._disabled or self._evaluation_run_id is None:
            return None
        if self._server is None:
            return None
        try:
            wc = require_weave_client()
        except Exception:
            return None
        base = getattr(wc, "_server_info", None)
        host = getattr(base, "ui_base_url", None) if base else None
        if not host:
            host = "https://wandb.ai"
        return f"{host}/{self._entity}/{self._project}/r/call/{self._evaluation_run_id}"

    @property
    def attributes(self) -> dict[str, Any]:
        """Eval-level attributes. Matches V1's shape for user-visible keys."""
        return dict(self.eval_attributes)

    # ------------------------------------------------------------------
    # Lazy server initialization
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if self._initialized or self._disabled:
            return
        assert self._server is not None

        # 1. Dataset
        dataset_res = self._server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=self._project_id,
                name=self._dataset_spec.name,
                description=None,
                rows=self._dataset_spec.rows,
                wb_user_id=None,
            )
        )
        self._dataset_ref = _object_ref_uri(
            self._entity, self._project, dataset_res.object_id, dataset_res.digest
        )

        # 2. Pre-declared scorers
        scorer_refs: list[str] = []
        if self.scorers:
            for scorer_name in self.scorers:
                scorer_obj = _cast_to_cls(Scorer)(scorer_name)
                ref = self._create_scorer_on_server(scorer_obj)
                self._scorer_refs_by_name[cast(str, scorer_obj.name)] = ref
                scorer_refs.append(ref)

        # 3. Model
        model_source = _synthesize_model_source(self.model)
        model_attrs = {
            k: v
            for k, v in self.model.model_dump().items()
            if k not in {"name", "description"}
        }
        model_res = self._server.model_create(
            tsi.ModelCreateReq(
                project_id=self._project_id,
                name=cast(str, self.model.name) or self.model.__class__.__name__,
                description=None,
                source_code=model_source,
                attributes=model_attrs or None,
                wb_user_id=None,
            )
        )
        self._model_ref = _object_ref_uri(
            self._entity, self._project, model_res.object_id, model_res.digest
        )

        # 4. Evaluation
        eval_res = self._server.evaluation_create(
            tsi.EvaluationCreateReq(
                project_id=self._project_id,
                name=self.name or self._dataset_spec.name,
                description=None,
                dataset=self._dataset_ref,
                scorers=scorer_refs or None,
                trials=1,
                evaluation_name=self.name,
                eval_attributes=self.eval_attributes or None,
                wb_user_id=None,
            )
        )
        self._evaluation_ref = eval_res.evaluation_ref

        # 5. Evaluation Run
        run_res = self._server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=self._project_id,
                evaluation=self._evaluation_ref,
                model=self._model_ref,
                wb_user_id=None,
            )
        )
        self._evaluation_run_id = run_res.evaluation_run_id

        self._initialized = True

    def _create_scorer_on_server(self, scorer: Scorer) -> str:
        assert self._server is not None
        res = self._server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=self._project_id,
                name=cast(str, scorer.name),
                description=None,
                op_source_code=_synthesize_scorer_source(scorer),
                wb_user_id=None,
            )
        )
        return _object_ref_uri(self._entity, self._project, res.object_id, res.digest)

    # ------------------------------------------------------------------
    # Scorer coercion + ref resolution
    # ------------------------------------------------------------------

    def _prepare_scorer(self, scorer: Scorer | dict | str) -> Scorer:
        """V1-compatible scorer coercion with predefined-list warning."""
        if isinstance(scorer, Scorer):
            prepared: Scorer = scorer
        else:
            prepared = global_scorer_cache.get_scorer(
                scorer_to_cache_key(scorer),
                lambda: _cast_to_cls(Scorer)(scorer),
            )

        if self.scorers:
            scorer_name = cast(str, prepared.name)
            if scorer_name not in self.scorers:
                logger.warning(
                    "Scorer '%s' is not in the predefined scorers list. "
                    "Expected one of: %s",
                    scorer_name,
                    sorted(self.scorers),
                )

        return prepared

    def _get_or_create_scorer_ref(self, scorer: Scorer) -> str:
        """Look up (or lazily create) a scorer ref by name.

        Called from background worker threads during score submission, so
        we guard the cache with a lock and double-check after paying the
        server round-trip to avoid two threads creating the same scorer.
        """
        name = cast(str, scorer.name)
        with self._scorer_lock:
            existing = self._scorer_refs_by_name.get(name)
        if existing is not None:
            return existing
        ref = self._create_scorer_on_server(scorer)
        with self._scorer_lock:
            # Another thread may have raced us; its ref is just as valid.
            return self._scorer_refs_by_name.setdefault(name, ref)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_prediction(
        self, inputs: dict[str, Any], output: Any = None
    ) -> ScoreLoggerV2:
        """Log a single prediction. Returns a ScoreLoggerV2."""
        if self._is_finalized:
            raise ValueError(
                "Cannot log prediction after evaluation has been finalized."
            )
        pred = ScoreLoggerV2(eval_logger=self, inputs=inputs, output=output)
        self._accumulated_predictions.append(pred)
        return pred

    def log_example(
        self,
        inputs: dict[str, Any],
        output: Any,
        scores: dict[str, ScoreType | None],
    ) -> None:
        """Convenience: log_prediction + log_score(s) + finish, all at once."""
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
        """Compute and attach the evaluation run's summary, then finalize."""
        if self._is_finalized:
            logger.warning("(NO-OP): Evaluation already finalized, cannot log summary.")
            return

        if summary is None:
            summary = {}

        if auto_summarize:
            data_to_summarize = [
                pred._captured_scores for pred in self._accumulated_predictions
            ]
            summary_data = auto_summarize_fn(data_to_summarize) or {}
        else:
            summary_data = {}

        final_summary: dict[str, Any] = {}
        if summary_data:
            final_summary.update(summary_data)
        final_summary["output"] = summary

        self._cleanup_predictions()
        # Wait for all in-flight prediction/score/finish tasks before we
        # close the run — summary aggregation on the server expects every
        # score and prediction_finish to have landed.
        self._drain_pending()

        if not self._disabled:
            self._ensure_initialized()
            assert self._server is not None
            try:
                self._server.evaluation_run_finish(
                    tsi.EvaluationRunFinishReq(
                        project_id=self._project_id,
                        evaluation_run_id=cast(str, self._evaluation_run_id),
                        summary=final_summary,
                        exception=None,
                        wb_user_id=None,
                    )
                )
            except Exception:
                logger.exception("Error finishing evaluation run during summary.")

        self._is_finalized = True
        self._unregister()

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
        # TODO(EvaluationLoggerV2): set_view() is not yet supported by the V2
        # server APIs. V1 stores views under `summary.weave.views.<name>` on
        # the evaluation's Call, but V2 does not expose a mutation endpoint
        # for evaluation-run summaries post-creation. Cleanly supporting
        # set_view requires either:
        #   (a) a new endpoint (e.g. EvaluationRunViewCreateReq) that mirrors
        #       `set_call_view` semantics for evaluation_run IDs, or
        #   (b) deferring view registration until log_summary/finish and
        #       folding the views into the summary dict on the way out.
        # We leave the stub raising for now so callers fail loudly rather
        # than silently dropping content.
        raise NotImplementedError(
            "EvaluationLoggerV2.set_view() is not yet supported. "
            "Use EvaluationLogger (V1) if you need set_view, or see the "
            "TODO in eval_imperative_v2.py for the design options."
        )

    def finish(self, exception: BaseException | None = None) -> None:
        """Finalize without computing a summary."""
        if self._is_finalized:
            return

        self._cleanup_predictions()
        # Wait for any in-flight background work to settle before we close
        # the run (or shut down the executor below).
        self._drain_pending()

        # Only emit evaluation_run_finish if tracing is active AND we have a
        # run to finish. `exception is not None` forces a lazy-init so the
        # failure is recorded even if the user never called log_prediction.
        if not self._disabled and (self._initialized or exception is not None):
            self._ensure_initialized()
            assert self._server is not None
            try:
                self._server.evaluation_run_finish(
                    tsi.EvaluationRunFinishReq(
                        project_id=self._project_id,
                        evaluation_run_id=cast(str, self._evaluation_run_id),
                        summary=None,
                        exception=str(exception) if exception else None,
                        wb_user_id=None,
                    )
                )
            except Exception:
                logger.exception("Error finishing evaluation run during finish().")

        self._is_finalized = True
        self._unregister()

    def fail(self, exception: BaseException) -> None:
        """Finalize the evaluation as failed."""
        self.finish(exception=exception)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cleanup_predictions(self) -> None:
        for pred in self._accumulated_predictions:
            if pred._has_finished:
                continue
            try:
                pred.finish()
            except Exception:
                logger.exception(
                    "Error finishing prediction during evaluation cleanup."
                )

    def _unregister(self) -> None:
        # Shut the executor down after the run is closed so any lingering
        # scheduled work runs to completion. Done here (not in `finish`)
        # because both `finish` and `log_summary` funnel into `_unregister`.
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
        try:
            _active_evaluation_loggers.remove(self)
        except ValueError:
            pass
