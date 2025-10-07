"""TraceServer-based evaluation logger implementations.

This module provides evaluation logging classes that preferentially use the new
TraceServerInterface evaluation_log_* methods when available, but fall back
to the existing EvaluationLogger implementation when they are not.

The new TraceServerInterface methods provide a more direct and efficient
way to log evaluations on the server side without requiring the client-side
evaluation framework.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Annotated, Any, TypeVar, Union, cast

from pydantic import BaseModel, BeforeValidator, Field, PrivateAttr

import weave
from weave.dataset.dataset import Dataset
from weave.evaluation.eval_imperative_v1 import (
    _cast_to_cls,
    _cast_to_imperative_dataset,
)
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.util import make_memorable_name
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.table import Table
from weave.trace_server import trace_server_interface as tsi

T = TypeVar("T")
ID = str
ScoreType = Union[float, bool, dict]

logger = logging.getLogger(__name__)


def _default_dataset_name() -> str:
    """Generate a default dataset name with timestamp and memorable identifier.

    Returns:
        A unique dataset name in format: YYYY-MM-DD-{memorable_name}-dataset

    Examples:
        >>> name = _default_dataset_name()
        >>> isinstance(name, str) and len(name) > 10
        True
    """
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    relative_name = make_memorable_name()
    return f"{date}-{relative_name}-dataset"


class ScoreLogger(BaseModel):
    """Score logger that uses TraceServerInterface evaluation_log_score method.

    This class provides an imperative interface for logging scores using the
    new TraceServerInterface API when available.
    """

    # Call references from TraceServer logging
    evaluation_call_id: str
    prediction_call_id: str

    # Scorer info
    predefined_scorers: list[str] | None = None

    _captured_scores: dict[str, ScoreType] = PrivateAttr(default_factory=dict)
    _has_finished: bool = PrivateAttr(False)

    def log_score(self, scorer: Scorer | dict | str, score: ScoreType) -> None:
        """Log a score using the TraceServerInterface evaluation_log_score method.

        Args:
            scorer: A Scorer object, dict of attributes, or string ID.
            score: The score value to log.

        Raises:
            ValueError: If scorer is not in predefined list or if already finished.
            RuntimeError: If server doesn't support evaluation logging.

        Examples:
            >>> logger = ScoreLogger(...)
            >>> logger.log_score("accuracy", 0.95)
            >>> logger.log_score({"name": "precision"}, 0.87)
        """
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        # Get client and server interface dynamically
        wc = require_weave_client()
        server_interface = wc.server

        # Convert scorer to Scorer object if needed
        if not isinstance(scorer, Scorer):
            scorer_id = json.dumps(scorer)
            scorer = _cast_to_cls(Scorer)(scorer)
        scorer = cast(Scorer, scorer)

        # Check predefined scorers
        if self.predefined_scorers:
            scorer_name = cast(str, scorer.name)
            if scorer_name not in self.predefined_scorers:
                logger.warning(
                    f"Scorer '{scorer_name}' is not in the predefined scorers list. "
                    f"Expected one of: {sorted(self.predefined_scorers)}"
                )

        # Create scorer object reference if needed
        scorer_ref = None
        try:
            # Create and publish scorer object to get reference
            scorer_obj = weave.publish(scorer)
            scorer_ref = scorer_obj.uri()
        except Exception:
            logger.debug(
                "Could not publish scorer object, proceeding without reference"
            )

        # Call the server's evaluation_log_score method
        req = tsi.EvaluationLogScoreReq(
            project_id=wc._project_id(),
            predict_call_id=self.prediction_call_id,
            scorer_ref=scorer_ref,
            score=score,
        )

        try:
            response = server_interface.evaluation_log_score(req)
            logger.debug(f"Logged score with call_id={response.call_id}")
        except Exception as e:
            logger.exception("Failed to log score via TraceServerInterface")
            raise

        # Store score locally for summary
        scorer_name = cast(str, scorer.name)
        self._captured_scores[scorer_name] = score

    def finish(self) -> None:
        """Mark this score logger as finished."""
        self._has_finished = True


class EvaluationLogger(BaseModel):
    """Evaluation logger that preferentially uses TraceServerInterface methods.

    This logger attempts to use the new TraceServerInterface evaluation_log_*
    methods when available, but falls back to the original EvaluationLogger
    implementation when they are not supported by the server.

    Example:
        ```python
        ev = TraceServerEvaluationLogger(
            model="my-model",
            dataset="my-dataset",
            fallback_to_imperative=True
        )
        pred = ev.log_prediction(inputs, output)
        pred.log_score("accuracy", score)
        ev.log_summary(summary)
        ```
    """

    name: Annotated[
        str | None,
        Field(
            default=None,
            description="An evaluator name. By default, a memorable name is generated.",
        ),
    ]
    model: Annotated[
        Model | dict | str,
        BeforeValidator(_cast_to_cls(Model)),
        Field(
            default_factory=Model,
            description="A metadata-only Model used for comparisons. Alternatively, "
            "you can pass a dict of attributes or just a string representing the ID.",
        ),
    ]
    dataset: Annotated[
        Dataset | list[dict] | str,
        BeforeValidator(_cast_to_imperative_dataset),
        Field(
            default_factory=lambda: Dataset(
                rows=Table([{"dataset_id": _default_dataset_name()}]),
            ),
            description="A metadata-only Dataset used for comparisons.",
        ),
    ]
    eval_attributes: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="A dictionary of attributes to add to the evaluation call.",
        ),
    ]
    scorers: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="A metadata-only list of predefined scorers for the evaluation.",
        ),
    ]

    _trace_server_call_id: str | None = PrivateAttr(None)
    _model_ref: str | None = PrivateAttr(None)

    def model_post_init(self, __context: Any) -> None:
        """Initialize the evaluation logger with appropriate backend."""
        # Set up TraceServer-based evaluation logging
        wc = require_weave_client()
        server_interface = wc.server

        assert isinstance(self.dataset, Dataset)

        # Publish model and dataset objects to get references
        if self.dataset.name is None:
            self.dataset.name = _default_dataset_name()

        try:
            model_obj = weave.publish(self.model)
            self._model_ref = model_obj.uri()
        except Exception as e:
            logger.exception("Failed to publish model object")
            raise

        try:
            dataset_obj = weave.publish(self.dataset)
            dataset_ref = dataset_obj.uri()
        except Exception as e:
            logger.exception("Failed to publish dataset object")
            raise

        try:
            # Create evaluation using TraceServerInterface
            eval_req = tsi.EvaluationCreateReq(
                project_id=wc._project_id(),
                name=self.name or f"eval-{make_memorable_name()}",
                dataset_ref=dataset_ref,
                scorer_refs=[],  # Will be populated as scorers are logged
                eval_attributes=self.eval_attributes if self.eval_attributes else None,
            )

            eval_resp = server_interface.evaluation_create(eval_req)
            if eval_resp is None:
                raise RuntimeError(
                    "evaluation_create returned None - server may not support this API"
                )
        except Exception as e:
            logger.exception("Failed to create evaluation")
            raise

        try:
            # Start evaluation logging
            start_req = tsi.EvaluationLogStartReq(
                project_id=wc._project_id(),
                evaluation_ref=eval_resp.evaluation_ref,
                model_ref=self._model_ref,
            )

            start_resp = server_interface.evaluation_log_start(start_req)
            self._trace_server_call_id = start_resp.evaluate_call_id

            logger.debug(
                f"Started TraceServer evaluation with evaluate_call_id={self._trace_server_call_id}"
            )
        except Exception as e:
            logger.exception("Failed to start evaluation logging")
            raise

    def log_prediction(self, inputs: dict, output: Any) -> ScoreLogger:
        """Log a prediction and return a score logger.

        Args:
            inputs: Input data for the prediction.
            output: Output data from the model.

        Returns:
            A ScoreLogger for logging scores.

        Examples:
            >>> ev = EvaluationLogger()
            >>> score_logger = ev.log_prediction({"text": "Hello"}, "world")
            >>> score_logger.log_score("accuracy", 0.95)
        """
        if not self._trace_server_call_id:
            raise RuntimeError("Evaluation not properly initialized")

        wc = require_weave_client()
        server_interface = wc.server

        pred_req = tsi.EvaluationLogPredictionReq(
            project_id=wc._project_id(),
            evaluate_call_id=self._trace_server_call_id,
            model_ref=self._model_ref,
            inputs=inputs,
            output=output,
        )

        try:
            pred_resp = server_interface.evaluation_log_prediction(pred_req)
        except Exception as e:
            logger.exception("Failed to log prediction via TraceServerInterface")
            raise

        return ScoreLogger(
            evaluation_call_id=self._trace_server_call_id,
            prediction_call_id=pred_resp.predict_call_id,
            predefined_scorers=self.scorers,
        )

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary and finish the evaluation.

        Args:
            summary: Summary data to log.
            auto_summarize: Whether to automatically summarize prediction scores.

        Examples:
            >>> ev.log_summary({"total_predictions": 10})
            >>> ev.log_summary()  # Auto-summarize from scores
        """
        if not self._trace_server_call_id:
            raise RuntimeError("Evaluation not properly initialized")

        if auto_summarize:
            logger.warning(
                "Auto-summarize is not available in V2, but the arg is kept here "
                "for backwards compatibility.  Please log a summary dict manually."
            )

        wc = require_weave_client()
        server_interface = wc.server

        if summary is None:
            summary = {}

        finish_req = tsi.EvaluationLogFinishReq(
            project_id=wc._project_id(),
            evaluate_call_id=self._trace_server_call_id,
            summary=summary,
        )

        try:
            finish_resp = server_interface.evaluation_log_finish(finish_req)
            logger.debug(
                f"Finished TraceServer evaluation: success={finish_resp.success}"
            )
        except Exception as e:
            logger.exception("Failed to finish TraceServer evaluation")
            raise

    def fail(self, exception: BaseException) -> None:
        """Fail the evaluation with an exception.

        Args:
            exception: The exception that caused the failure.
        """
        logger.warning(
            "Cannot fail TraceServer evaluation with exception, just finishing"
        )
        self.log_summary({"status": "failed", "exception": str(exception)})

    @property
    def ui_url(self) -> str | None:
        """Get the UI URL for this evaluation."""
        # TODO: Implement UI URL generation for TraceServer evaluation
        return None

    @property
    def attributes(self) -> dict[str, Any]:
        """Get evaluation attributes."""
        base_attrs = self.eval_attributes
        base_attrs["_weave_eval_meta"] = {"trace_server": True}
        return base_attrs


class ImperativeEvaluationLogger(EvaluationLogger):
    """Legacy class name for EvaluationLogger.

    This class is maintained for backward compatibility.
    Please use EvaluationLogger instead.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        logger.warning(
            "ImperativeEvaluationLogger was renamed to EvaluationLogger in 0.51.44"
            "Please use EvaluationLogger instead.  ImperativeEvaluationLogger will"
            "be removed in a future version."
        )
        super().__init__(*args, **kwargs)
