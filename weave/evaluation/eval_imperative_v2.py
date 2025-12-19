from __future__ import annotations

import datetime
import logging
from typing import Any

from weave.dataset.dataset import Dataset
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.flow.util import make_memorable_name
from weave.trace.api import publish
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.ref_util import get_ref
from weave.trace.refs import ObjectRef
from weave.trace.table import Table
from weave.trace_server import trace_server_interface as tsi
from weave.type_wrappers.Content.content import Content

logger = logging.getLogger(__name__)

ScoreType = float | bool | dict


def _default_dataset_name() -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


def _get_or_publish_ref(obj: Any, name: str | None = None) -> str:
    """Get existing ref or publish object and return ref URI."""
    ref = get_ref(obj)
    if ref is not None and isinstance(ref, ObjectRef):
        return ref.uri()

    # Publish and get ref
    published_ref = publish(obj, name=name)
    return published_ref.uri()


class ScoreLoggerV2:
    """Interface for logging scores and managing prediction outputs using the V2 Object APIs.

    This class is returned by `EvaluationLoggerV2.log_prediction()` and can be used
    either directly or as a context manager.

    Direct usage - when output is known upfront:

    ```python
    ev = EvaluationLoggerV2()
    pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
    pred.log_score("correctness", 0.9)
    pred.finish()
    ```

    Context manager usage - for automatic cleanup:

    ```python
    ev = EvaluationLoggerV2()

    with ev.log_prediction(inputs={'q': 'Hello'}, output='Hi') as pred:
        pred.log_score("correctness", 0.9)
    # Automatically calls finish() on exit
    ```
    """

    def __init__(
        self,
        evaluation_logger: EvaluationLoggerV2,
        prediction_id: str,
        inputs: dict[str, Any],
        output: Any,
        predefined_scorers: list[str] | None = None,
    ) -> None:
        self._evaluation_logger = evaluation_logger
        self._prediction_id = prediction_id
        self._inputs = inputs
        self._predict_output = output
        self.predefined_scorers = predefined_scorers

        self._captured_scores: dict[str, ScoreType] = {}
        self._has_finished: bool = False

    def finish(self, output: Any | None = None) -> None:
        """Finish the prediction.

        Args:
            output: Optional output to override the prediction output. Currently
                V2 API doesn't support updating output after creation.
        """
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return

        if output is not None and output != self._predict_output:
            logger.warning(
                "V2 API does not support updating prediction output after creation. "
                "Output argument is ignored."
            )

        # Finish the prediction via server
        wc = require_weave_client()
        wc.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=wc._project_id(),
                prediction_id=self._prediction_id,
            )
        )

        self._has_finished = True

    def _get_scorer_ref(self, scorer: Scorer | dict | str) -> str:
        """Get or create a scorer ref."""
        if isinstance(scorer, str):
            # Check if it's already a ref
            if scorer.startswith("weave://"):
                return scorer
            # Create a simple scorer object with just the name
            scorer_obj = Scorer(name=scorer)
            return _get_or_publish_ref(scorer_obj, name=scorer)
        elif isinstance(scorer, dict):
            name = scorer.get("name", "unnamed_scorer")
            scorer_obj = Scorer(name=name)
            return _get_or_publish_ref(scorer_obj, name=name)
        elif isinstance(scorer, Scorer):
            name = scorer.name or "unnamed_scorer"
            return _get_or_publish_ref(scorer, name=name)
        else:
            raise TypeError(f"Unsupported scorer type: {type(scorer)}")

    def log_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        """Log a score for this prediction.

        Args:
            scorer: The scorer (Scorer object, dict with 'name', string name, or ref URI)
            score: The score value
        """
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        # Get scorer name for tracking
        if isinstance(scorer, str):
            if scorer.startswith("weave://"):
                # Extract name from ref
                scorer_name = scorer.split("/")[-1].split(":")[0]
            else:
                scorer_name = scorer
        elif isinstance(scorer, dict):
            scorer_name = scorer.get("name", "unnamed")
        elif isinstance(scorer, Scorer):
            scorer_name = scorer.name or "unnamed"
        else:
            scorer_name = "unnamed"

        # Check if scorer is in predefined list
        if self.predefined_scorers and scorer_name not in self.predefined_scorers:
            logger.warning(
                f"Scorer '{scorer_name}' is not in the predefined scorers list. "
                f"Expected one of: {sorted(self.predefined_scorers)}"
            )

        # Get scorer ref
        scorer_ref = self._get_scorer_ref(scorer)

        # Convert score to float for the API
        if isinstance(score, bool):
            score_value = 1.0 if score else 0.0
        elif isinstance(score, dict):
            # For dict scores, we'll store the first numeric value or 0
            score_value = 0.0
            for v in score.values():
                if isinstance(v, (int, float)):
                    score_value = float(v)
                    break
        else:
            score_value = float(score)

        # Create the score via server
        wc = require_weave_client()
        wc.server.score_create(
            tsi.ScoreCreateReq(
                project_id=wc._project_id(),
                prediction_id=self._prediction_id,
                scorer=scorer_ref,
                value=score_value,
                evaluation_run_id=self._evaluation_logger._evaluation_run_id,
            )
        )

        self._captured_scores[scorer_name] = score

    @property
    def output(self) -> Any:
        """Get the current output value."""
        return self._predict_output

    @output.setter
    def output(self, value: Any) -> None:
        """Set the output value. Note: V2 API doesn't support updating after creation."""
        logger.warning(
            "V2 API does not support updating prediction output after creation. "
            "This setter only updates the local value."
        )
        self._predict_output = value

    def __enter__(self) -> ScoreLoggerV2:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and automatically finish."""
        if not self._has_finished:
            self.finish()


class EvaluationLoggerV2:
    """This class provides an imperative interface for logging evaluations using the V2 Object APIs.

    An evaluation is started automatically when the logger is created,
    and finished when the `log_summary` method is called.

    Each time you log a prediction, you will get back a `ScoreLoggerV2` object.
    You can use this object to log scores for that specific prediction.

    Basic usage - log predictions with inputs and outputs directly:

    ```python
    ev = EvaluationLoggerV2()

    # Log predictions with known inputs/outputs
    pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
    pred.log_score("correctness", 0.9)
    pred.finish()

    # Finish the evaluation
    ev.log_summary({"avg_score": 0.9})
    ```

    Advanced usage - use context manager:

    ```python
    ev = EvaluationLoggerV2()

    with ev.log_prediction(inputs={'q': 'Hello'}, output='Hi') as pred:
        pred.log_score("correctness", 0.9)

    # Finish the evaluation
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
    ) -> None:
        self.name = name
        self.scorers = scorers
        self.eval_attributes = eval_attributes if eval_attributes is not None else {}

        # Private state
        self._is_finalized: bool = False
        self._accumulated_predictions: list[ScoreLoggerV2] = []
        self._evaluation_run_id: str | None = None
        self._evaluation_ref: str | None = None
        self._model_ref: str | None = None
        self._dataset_ref: str | None = None

        wc = require_weave_client()

        # Convert and publish dataset
        if dataset is None:
            dataset_obj = Dataset(
                name=_default_dataset_name(),
                rows=Table([{"dataset_id": _default_dataset_name()}]),
            )
        elif isinstance(dataset, str):
            if dataset.startswith("weave://"):
                self._dataset_ref = dataset
                dataset_obj = None
            else:
                dataset_obj = Dataset(
                    name=dataset, rows=Table([{"dataset_id": dataset}])
                )
        elif isinstance(dataset, list):
            dataset_obj = Dataset(rows=Table(dataset))
        elif isinstance(dataset, Dataset):
            dataset_obj = dataset
        else:
            raise TypeError(f"Unsupported dataset type: {type(dataset)}")

        if dataset_obj is not None:
            dataset_name = getattr(dataset_obj, "name", None) or _default_dataset_name()
            self._dataset_ref = _get_or_publish_ref(dataset_obj, name=dataset_name)

        # Convert and publish model
        if model is None:
            model_obj = Model(name="Model")
        elif isinstance(model, str):
            if model.startswith("weave://"):
                self._model_ref = model
                model_obj = None
            else:
                model_obj = Model(name=model)
        elif isinstance(model, dict):
            model_name = model.get("name", "Model")
            model_obj = Model(name=model_name)
        elif isinstance(model, Model):
            model_obj = model
        else:
            raise TypeError(f"Unsupported model type: {type(model)}")

        if model_obj is not None:
            model_name = getattr(model_obj, "name", None) or "Model"
            self._model_ref = _get_or_publish_ref(model_obj, name=model_name)

        # Get scorer refs if provided
        scorer_refs: list[str] | None = None
        if scorers:
            scorer_refs = []
            for scorer_name in scorers:
                if scorer_name.startswith("weave://"):
                    scorer_refs.append(scorer_name)
                else:
                    scorer_obj = Scorer(name=scorer_name)
                    scorer_refs.append(
                        _get_or_publish_ref(scorer_obj, name=scorer_name)
                    )

        # Create the evaluation object
        # Ensure dataset_ref is set (it should always be set by this point)
        assert self._dataset_ref is not None, (
            "Dataset ref should be set during initialization"
        )
        eval_name = self.name or f"Evaluation-{make_memorable_name()}"
        eval_res = wc.server.evaluation_create(
            tsi.EvaluationCreateReq(
                project_id=wc._project_id(),
                name=eval_name,
                dataset=self._dataset_ref,
                scorers=scorer_refs,
                description=self.eval_attributes.get("description"),
                eval_attributes=self.eval_attributes,
            )
        )
        self._evaluation_ref = eval_res.evaluation_ref

        # Create the evaluation run
        # Ensure model_ref is set (it should always be set by this point)
        assert self._model_ref is not None, (
            "Model ref should be set during initialization"
        )
        run_res = wc.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=wc._project_id(),
                evaluation=self._evaluation_ref,
                model=self._model_ref,
            )
        )
        self._evaluation_run_id = run_res.evaluation_run_id

        # Register with the shared cleanup registry
        from weave.evaluation.eval_imperative import register_evaluation_logger

        register_evaluation_logger(self)

    @property
    def ui_url(self) -> str | None:
        """Get the URL to view this evaluation in the UI."""
        # TODO: Construct proper URL for v2 evaluations
        return None

    @property
    def attributes(self) -> dict[str, Any]:
        return self.eval_attributes

    def _cleanup_predictions(self) -> None:
        if self._is_finalized:
            return

        for pred in self._accumulated_predictions:
            if pred._has_finished:
                continue
            try:
                pred.finish()
            except Exception:
                # Best effort cleanup
                pass

    def _finalize_evaluation(
        self,
        summary: dict[str, Any] | None = None,
        exception: BaseException | None = None,
    ) -> None:
        """Handles the final steps of the evaluation."""
        if self._is_finalized:
            return

        self._cleanup_predictions()

        # Finish the evaluation run
        if self._evaluation_run_id:
            wc = require_weave_client()
            try:
                wc.server.evaluation_run_finish(
                    tsi.EvaluationRunFinishReq(
                        project_id=wc._project_id(),
                        evaluation_run_id=self._evaluation_run_id,
                        summary=summary,
                    )
                )
            except Exception:
                logger.error(
                    "Failed to finish evaluation run during finalization.",
                    exc_info=True,
                )

        self._is_finalized = True

        # Unregister from the shared cleanup registry
        from weave.evaluation.eval_imperative import unregister_evaluation_logger

        unregister_evaluation_logger(self)

    def log_prediction(
        self, inputs: dict[str, Any], output: Any = None
    ) -> ScoreLoggerV2:
        """Log a prediction to the Evaluation.

        Returns a ScoreLoggerV2 that can be used directly or as a context manager.

        Args:
            inputs: The input data for the prediction
            output: The output value. Required for V2 API.

        Returns:
            ScoreLoggerV2 for logging scores and optionally finishing the prediction.
        """
        if self._is_finalized:
            raise ValueError(
                "Cannot log prediction after evaluation has been finalized."
            )

        if output is None:
            logger.warning(
                "V2 API requires output at prediction creation time. "
                "Setting output to None."
            )

        wc = require_weave_client()

        # Create the prediction via server
        # Ensure model_ref and evaluation_run_id are set (they should always be set by this point)
        assert self._model_ref is not None, (
            "Model ref should be set during initialization"
        )
        assert self._evaluation_run_id is not None, (
            "Evaluation run ID should be set during initialization"
        )
        pred_res = wc.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=wc._project_id(),
                model=self._model_ref,
                inputs=inputs,
                output=output,
                evaluation_run_id=self._evaluation_run_id,
            )
        )

        pred = ScoreLoggerV2(
            evaluation_logger=self,
            prediction_id=pred_res.prediction_id,
            inputs=inputs,
            output=output,
            predefined_scorers=self.scorers,
        )
        self._accumulated_predictions.append(pred)

        return pred

    def log_example(
        self, inputs: dict[str, Any], output: Any, scores: dict[str, ScoreType]
    ) -> None:
        """Log a complete example with inputs, output, and scores.

        This is a convenience method that combines log_prediction and log_score
        for when you have all the data upfront.

        Args:
            inputs: The input data for the prediction
            output: The output value
            scores: Dictionary mapping scorer names to score values
        """
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
        """Log a summary dict to the Evaluation.

        This will calculate the summary and finalize the evaluation,
        meaning no more predictions or scores can be logged.
        """
        if self._is_finalized:
            logger.warning("(NO-OP): Evaluation already finalized, cannot log summary.")
            return

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

        self._finalize_evaluation(summary=final_summary)

    def set_view(
        self,
        name: str,
        content: Content | str,
        *,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Attach a view to the evaluation.

        Note: V2 API currently does not support views. This is a no-op.
        """
        logger.warning(
            "V2 API does not currently support set_view. This operation is a no-op."
        )

    def finish(self, exception: BaseException | None = None) -> None:
        """Clean up the evaluation resources explicitly without logging a summary."""
        if self._is_finalized:
            return

        self._finalize_evaluation(summary=None)

    def fail(self, exception: BaseException) -> None:
        """Convenience method to fail the evaluation with an exception."""
        self.finish(exception=exception)

    def __del__(self) -> None:
        """Ensure cleanup happens during garbage collection."""
        # The atexit handler in eval_imperative.py will handle cleanup
        # This is a fallback in case the object is garbage collected before exit
        if not self._is_finalized:
            try:
                self.finish()
            except Exception:
                pass  # Suppress errors during GC
