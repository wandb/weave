"""Imperative Evaluation Logger V2.

This module provides a V2 version of the EvaluationLogger that uses the
new V2 trace server APIs instead of the legacy call-based approach.

Example:
    ```python
    import weave

    weave.init("my-project")

    # Create an evaluation logger
    ev = weave.EvaluationLoggerV2(
        name="my-evaluation",
        dataset="my-dataset-ref",  # Can be a weave ref or Dataset object
        model="my-model",
    )

    # Log predictions
    for example in examples:
        pred = ev.log_prediction(
            inputs=example["input"],
            output=model(example["input"])
        )
        pred.log_score("accuracy", calculate_accuracy(...))
        pred.finish()

    # Finish with summary
    ev.log_summary({"avg_accuracy": 0.95})
    ```
"""

from __future__ import annotations

import atexit
import datetime
import logging
from typing import Annotated, Any, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from weave.dataset.dataset import Dataset
from weave.evaluation.eval import default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.flow.util import make_memorable_name
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import ObjectRef
from weave.trace_server import trace_server_interface as tsi

T = TypeVar("T")
ID = str
ScoreType = Union[float, bool, dict]

logger = logging.getLogger(__name__)

# Registry to track active EvaluationLoggerV2 instances
_active_evaluation_loggers_v2: list[EvaluationLoggerV2] = []


# Register cleanup handler for program exit
def _cleanup_all_evaluations_v2() -> None:
    for eval_logger in _active_evaluation_loggers_v2:
        _cleanup_evaluation_v2(eval_logger)


def _cleanup_evaluation_v2(eval_logger: EvaluationLoggerV2) -> None:
    try:
        if not eval_logger._is_finalized:
            # Check if weave client is still available before trying to finish
            try:
                require_weave_client()
                eval_logger.finish()
            except Exception:
                # Client is no longer available, skip cleanup
                pass
    except Exception:
        logger.error("Error during cleanup of EvaluationLoggerV2", exc_info=True)


atexit.register(_cleanup_all_evaluations_v2)


def _to_weave_ref(obj: Any, project_id: str) -> str:
    """Convert an object to a weave:// reference URI.

    Args:
        obj: The object to convert. Can be a weave ref string, ObjectRef, or a Weave object.
        project_id: The project ID in format "entity/project"

    Returns:
        A weave:// URI string
    """
    if isinstance(obj, str):
        # Already a string, assume it's either a weave ref or a simple string
        if obj.startswith("weave:///"):
            return obj
        # Simple string - treat as object_id (for models/datasets)
        entity, project = project_id.split("/")
        return f"weave:///{entity}/{project}/object/{obj}"

    if isinstance(obj, ObjectRef):
        return str(obj)

    # It's a Weave object - get its ref
    if hasattr(obj, "ref"):
        ref = obj.ref
        if ref is not None:
            return str(ref)

    # Fall back to object name
    if hasattr(obj, "name"):
        entity, project = project_id.split("/")
        return f"weave:///{entity}/{project}/object/{obj.name}"

    raise ValueError(f"Cannot convert {type(obj)} to weave ref")


def _default_dataset_name() -> str:
    """Generate a default dataset name."""
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


class ScoreLoggerV2(BaseModel):
    """Interface for logging scores in V2 evaluation runs.

    This class is returned by `EvaluationLoggerV2.log_prediction()` and can be used
    to log scores for a specific prediction.

    Example:
        ```python
        ev = EvaluationLoggerV2()
        pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
        pred.log_score("correctness", 0.9)
        pred.finish()
        ```
    """

    evaluation_logger: EvaluationLoggerV2
    predict_call_id: str
    inputs: dict[str, Any]
    output: Any

    _captured_scores: dict[str, ScoreType] = PrivateAttr(default_factory=dict)
    _has_finished: bool = PrivateAttr(False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def finish(self) -> None:
        """Finish the prediction logging.

        This is a no-op in V2 since predictions are logged immediately.
        """
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return

        self._has_finished = True

    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        """Log a score for this prediction.

        Args:
            scorer: The scorer to use. Can be a Scorer object, dict, or string.
            score: The score value (float, bool, or dict).
        """
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        # Convert scorer to ref
        scorer_ref = self.evaluation_logger._prepare_scorer_ref(scorer)

        # Get the weave client and project
        wc = require_weave_client()
        project_id = wc._project_id()

        # Log the score via V2 API
        req = tsi.EvaluationRunLogScoreV2Req(
            project_id=project_id,
            evaluation_run_id=self.evaluation_logger._eval_run_id,
            predict_call_id=self.predict_call_id,
            scorer=scorer_ref,
            score=score,
        )

        res = wc.server.evaluation_run_log_score_v2(req)

        # Track the score locally
        scorer_name = self._get_scorer_name(scorer)
        self._captured_scores[scorer_name] = score

        logger.debug(
            f"Logged score {scorer_name}={score} with call_id={res.score_call_id}"
        )

    def _get_scorer_name(self, scorer: Scorer | dict | str) -> str:
        """Extract the scorer name from various input types."""
        if isinstance(scorer, str):
            return scorer
        elif isinstance(scorer, dict):
            return scorer.get("name", str(scorer))
        elif isinstance(scorer, Scorer):
            return scorer.name or str(scorer)
        return str(scorer)


class EvaluationLoggerV2(BaseModel):
    """V2 imperative interface for logging evaluations.

    This class provides an imperative interface for logging evaluations using
    the V2 trace server APIs. It offers cleaner separation between evaluation
    setup and execution.

    Basic usage:
        ```python
        ev = EvaluationLoggerV2(
            name="my-eval",
            dataset="dataset-ref",
            model="model-ref",
        )

        # Log predictions
        pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
        pred.log_score("correctness", 0.9)
        pred.finish()

        # Finish the evaluation
        ev.log_summary({"avg_score": 0.9})
        ```
    """

    name: Annotated[
        str | None,
        Field(
            default=None,
            description="(Optional): A name for the evaluation. "
            "If not provided, a default name will be generated.",
        ),
    ]
    model: Annotated[
        Model | dict | str,
        Field(
            description="The model to evaluate. Can be a Model object, dict, or string ref."
        ),
    ]
    dataset: Annotated[
        Dataset | str,
        Field(description="The dataset to use. Can be a Dataset object or string ref."),
    ]
    scorers: Annotated[
        list[Scorer | dict | str] | None,
        Field(
            default=None,
            description="(Optional): List of scorers for the evaluation.",
        ),
    ] = None
    description: Annotated[
        str | None,
        Field(
            default=None,
            description="(Optional): A description of the evaluation.",
        ),
    ] = None
    eval_attributes: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="(Optional): Additional attributes for the evaluation.",
        ),
    ]

    # Private attributes
    _is_finalized: bool = PrivateAttr(False)
    _eval_run_id: str | None = PrivateAttr(None)
    _evaluation_ref: str | None = PrivateAttr(None)
    _dataset_ref: str | None = PrivateAttr(None)
    _model_ref: str | None = PrivateAttr(None)
    _accumulated_predictions: list[ScoreLoggerV2] = PrivateAttr(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def ui_url(self) -> str | None:
        """Get the UI URL for this evaluation run."""
        if self._eval_run_id is None:
            return None

        wc = require_weave_client()
        project_id = wc._project_id()
        entity, project = project_id.split("/")

        # Get the base URL - handle both remote and local servers
        if hasattr(wc.server, "_app_base_url"):
            base_url = wc.server._app_base_url()
        else:
            # In test environments, construct a default URL
            base_url = "https://wandb.ai"

        # The UI URL for an evaluation run call
        return f"{base_url}/{entity}/{project}/weave/calls?filter=%7B%22traceRootsOnly%22%3Atrue%2C%22callId%22%3A%22{self._eval_run_id}%22%7D"

    def model_post_init(self, __context: Any) -> None:
        """Initialize the evaluation run."""
        # Register this instance in the global registry for atexit cleanup
        _active_evaluation_loggers_v2.append(self)

        wc = require_weave_client()
        project_id = wc._project_id()
        entity, project = project_id.split("/")

        # Ensure dataset exists and get its ref
        if isinstance(self.dataset, Dataset):
            # Save the dataset if it doesn't have a ref yet
            if self.dataset.ref is None:
                dataset_name = self.dataset.name or _default_dataset_name()
                wc.save(self.dataset, name=dataset_name)

            self._dataset_ref = str(self.dataset.ref)
        else:
            # It's a string ref
            self._dataset_ref = _to_weave_ref(self.dataset, project_id)

        # Ensure model exists and get its ref
        if isinstance(self.model, Model):
            # Save the model if it doesn't have a ref yet
            if self.model.ref is None:
                model_name = self.model.name or "model"
                wc.save(self.model, name=model_name)

            self._model_ref = str(self.model.ref)
        elif isinstance(self.model, dict):
            # Create a model from dict
            model_obj = Model(**self.model)
            model_name = model_obj.name or "model"
            wc.save(model_obj, name=model_name)
            self._model_ref = str(model_obj.ref)
        else:
            # It's a string ref
            self._model_ref = _to_weave_ref(self.model, project_id)

        # Convert scorers to refs
        scorer_refs = []
        if self.scorers:
            for scorer in self.scorers:
                scorer_ref = self._prepare_scorer_ref(scorer)
                scorer_refs.append(scorer_ref)

        # Create the evaluation object via V2 API
        eval_req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name=self.name or default_evaluation_display_name,
            description=self.description,
            dataset=self._dataset_ref,
            scorers=scorer_refs,
            trials=1,
            eval_attributes=self.eval_attributes,
        )

        eval_res = wc.server.evaluation_create_v2(eval_req)
        self._evaluation_ref = (
            f"weave:///{entity}/{project}/object/{eval_res.object_id}:{eval_res.digest}"
        )

        logger.debug(f"Created evaluation: {self._evaluation_ref}")

        # Create the evaluation run
        eval_run_req = tsi.EvaluationRunCreateV2Req(
            project_id=project_id,
            evaluation=self._evaluation_ref,
            model=self._model_ref,
        )

        eval_run_res = wc.server.evaluation_run_create_v2(eval_run_req)
        self._eval_run_id = eval_run_res.evaluation_run_id

        logger.debug(f"Created evaluation run: {self._eval_run_id}")

    def _prepare_scorer_ref(self, scorer: Scorer | dict | str) -> str:
        """Prepare a scorer and return its weave ref."""
        wc = require_weave_client()
        project_id = wc._project_id()

        if isinstance(scorer, str):
            # Already a string - convert to ref if needed
            return _to_weave_ref(scorer, project_id)

        if isinstance(scorer, dict):
            # Create a Scorer from dict
            scorer_obj = Scorer(**scorer)
            scorer_name = scorer_obj.name or "scorer"
            wc.save(scorer_obj, name=scorer_name)
            return str(scorer_obj.ref)

        if isinstance(scorer, Scorer):
            # Save the scorer if it doesn't have a ref yet
            if scorer.ref is None:
                scorer_name = scorer.name or "scorer"
                wc.save(scorer, name=scorer_name)
            return str(scorer.ref)

        raise ValueError(f"Invalid scorer type: {type(scorer)}")

    def log_prediction(
        self,
        inputs: dict[str, Any],
        output: Any,
    ) -> ScoreLoggerV2:
        """Log a prediction to the evaluation run.

        Args:
            inputs: The input data for the prediction
            output: The output value

        Returns:
            ScoreLoggerV2 for logging scores

        Example:
            ```python
            pred = ev.log_prediction({'q': '...'}, output="answer")
            pred.log_score("correctness", 0.9)
            pred.finish()
            ```
        """
        if self._is_finalized:
            raise RuntimeError("Cannot log prediction after evaluation is finalized")

        if self._eval_run_id is None:
            raise RuntimeError("Evaluation run not initialized")

        wc = require_weave_client()
        project_id = wc._project_id()

        # Log the prediction via V2 API
        req = tsi.EvaluationRunLogPredictionV2Req(
            project_id=project_id,
            evaluation_run_id=self._eval_run_id,
            model=self._model_ref,
            inputs=inputs,
            output=output,
        )

        res = wc.server.evaluation_run_log_prediction_v2(req)

        # Create the ScoreLoggerV2
        pred = ScoreLoggerV2(
            evaluation_logger=self,
            predict_call_id=res.predict_call_id,
            inputs=inputs,
            output=output,
        )

        self._accumulated_predictions.append(pred)

        logger.debug(f"Logged prediction with call_id={res.predict_call_id}")

        return pred

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary and finalize the evaluation run.

        Args:
            summary: Summary data to log. If None, will be auto-calculated.
            auto_summarize: Whether to automatically calculate summary statistics.
        """
        if self._is_finalized:
            logger.warning("(NO-OP): Evaluation already finalized, cannot log summary.")
            return

        if self._eval_run_id is None:
            raise RuntimeError("Evaluation run not initialized")

        if summary is None:
            summary = {}

        # Calculate summary
        if auto_summarize:
            data_to_summarize = [
                pred._captured_scores for pred in self._accumulated_predictions
            ]
            summary_data = auto_summarize_fn(data_to_summarize)
        else:
            summary_data = summary

        final_summary = {}
        if summary_data:
            final_summary = summary_data
        if summary is not None:
            final_summary = {**final_summary, "output": summary}

        wc = require_weave_client()
        project_id = wc._project_id()

        # Finish the evaluation run via V2 API
        req = tsi.EvaluationRunFinishV2Req(
            project_id=project_id,
            evaluation_run_id=self._eval_run_id,
            summary=final_summary,
        )

        wc.server.evaluation_run_finish_v2(req)

        self._is_finalized = True

        logger.debug(f"Finished evaluation run: {self._eval_run_id}")

    def finish(self, exception: BaseException | None = None) -> None:
        """Clean up the evaluation resources explicitly without logging a summary.

        Args:
            exception: Optional exception to log with the evaluation run.
        """
        if self._is_finalized:
            return

        # If there's an exception, we might want to log it somehow
        # For now, just finalize with empty summary
        if exception is not None:
            logger.error(f"Evaluation failed with exception: {exception}")

        # Finalize with empty summary
        self.log_summary(summary={}, auto_summarize=False)

        # Remove from global registry since we've manually finalized
        if self in _active_evaluation_loggers_v2:
            _active_evaluation_loggers_v2.remove(self)

    def fail(self, exception: BaseException) -> None:
        """Convenience method to fail the evaluation with an exception."""
        self.finish(exception=exception)

    def __del__(self) -> None:
        """Ensure cleanup happens during garbage collection."""
        _cleanup_evaluation_v2(self)
