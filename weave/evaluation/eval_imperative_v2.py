"""Imperative Evaluation Logger V2.

This module provides a V2 version of the EvaluationLogger that uses the
trace server APIs instead of the legacy call-based approach.

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

import asyncio
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


def _default_dataset_name() -> str:
    """Generate a default dataset name."""
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


def _convert_score_to_float(score: ScoreType) -> float:
    """Convert a score to float format required by the API.

    Args:
        score: The score value (float, bool, int, or dict).

    Returns:
        float: The converted score value.

    Raises:
        TypeError: If the score type is not supported.
    """
    if isinstance(score, (bool, int)):
        return float(score)
    elif isinstance(score, float):
        return score
    elif isinstance(score, dict):
        raise TypeError(f"Dict scores are not supported by the API. Got dict: {score}")
    else:
        raise TypeError(f"Invalid score type: {type(score)}. Expected float or bool.")


class ScoreLoggerV2(BaseModel):
    """Interface for logging scores in evaluation runs.

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
    prediction_id: str
    inputs: dict[str, Any]
    output: Any

    _captured_scores: dict[str, ScoreType] = PrivateAttr(default_factory=dict)
    _has_finished: bool = PrivateAttr(False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _prepare_finish_prediction(self) -> tsi.PredictionFinishReq | None:
        """Internal helper to prepare finish prediction request."""
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return None

        wc = require_weave_client()
        project_id = wc._project_id()

        # Finish the prediction via API
        req = tsi.PredictionFinishReq(
            project_id=project_id,
            prediction_id=self.prediction_id,
        )

        return req

    def finish(self) -> None:
        """Finish the prediction logging.

        Calls prediction_finish to mark the prediction as complete.
        """
        req = self._prepare_finish_prediction()
        if req is None:
            return

        wc = require_weave_client()
        wc.server.prediction_finish(req)
        self._has_finished = True

        logger.debug(f"Finished prediction with prediction_id={self.prediction_id}")

    async def afinish(self) -> None:
        """Finish the prediction logging (async version).

        Calls prediction_finish to mark the prediction as complete.
        """
        req = self._prepare_finish_prediction()
        if req is None:
            return

        wc = require_weave_client()
        await asyncio.to_thread(wc.server.prediction_finish, req)
        # Use sync finish's post-processing logic
        self._has_finished = True
        logger.debug(f"Finished prediction with prediction_id={self.prediction_id}")

    def _prepare_score_logging(
        self,
        scorer: Scorer | str,
        score: ScoreType,
    ) -> tsi.ScoreCreateReq:
        """Internal helper to prepare score logging request."""
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        # Convert scorer to ref
        scorer_ref = self.evaluation_logger._prepare_scorer_ref(scorer)

        # Get the weave client and project
        wc = require_weave_client()
        project_id = wc._project_id()

        # Convert score to float if needed (API expects float)
        score_value = _convert_score_to_float(score)

        # Log the score via API
        req = tsi.ScoreCreateReq(
            project_id=project_id,
            prediction_id=self.prediction_id,
            scorer=scorer_ref,
            value=score_value,
            evaluation_run_id=self.evaluation_logger._eval_run_id,
        )

        return req

    def _process_score_result(
        self,
        scorer: Scorer | str,
        score: ScoreType,
        res: Any,
    ) -> None:
        """Process score result (shared by sync and async)."""
        scorer_name = self._get_scorer_name(scorer)
        self._captured_scores[scorer_name] = score
        logger.debug(f"Logged score {scorer_name}={score} with score_id={res.score_id}")

    def log_score(
        self,
        scorer: Scorer | str,
        score: ScoreType,
    ) -> None:
        """Log a score for this prediction.

        Args:
            scorer: The scorer to use. Can be a Scorer object or string.
            score: The score value (float, bool, or dict).
        """
        req = self._prepare_score_logging(scorer, score)
        wc = require_weave_client()
        res = wc.server.score_create(req)
        self._process_score_result(scorer, score, res)

    async def alog_score(
        self,
        scorer: Scorer | str,
        score: ScoreType,
    ) -> None:
        """Log a score for this prediction (async version).

        Args:
            scorer: The scorer to use. Can be a Scorer object or string.
            score: The score value (float, bool, or dict).
        """
        req = self._prepare_score_logging(scorer, score)
        wc = require_weave_client()
        res = await asyncio.to_thread(wc.server.score_create, req)
        self._process_score_result(scorer, score, res)

    def _get_scorer_name(self, scorer: Scorer | str) -> str:
        """Extract the scorer name from various input types."""
        if isinstance(scorer, str):
            return scorer
        elif isinstance(scorer, Scorer):
            return scorer.name or str(scorer)
        return str(scorer)


class EvaluationLoggerV2(BaseModel):
    """V2 imperative interface for logging evaluations.

    This class provides an imperative interface for logging evaluations using
    the trace server APIs. It offers cleaner separation between evaluation
    setup and execution.

    Basic usage:
        ```python
        ev = EvaluationLoggerV2(
            name="my-eval",
            dataset="dataset-ref",
            model="model-ref",
        )

        # Log predictions (sync)
        pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
        pred.log_score("correctness", 0.9)
        pred.finish()

        # Finish the evaluation
        ev.log_summary({"avg_score": 0.9})

        # Or use async versions:
        # pred = await ev.alog_prediction(inputs={'q': 'Hello'}, output='Hi there!')
        # await pred.alog_score("correctness", 0.9)
        # await pred.afinish()
        # await ev.alog_summary({"avg_score": 0.9})
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
        Model | str,
        Field(
            description="The model to evaluate. Can be a Model object or string ref."
        ),
    ]
    dataset: Annotated[
        Dataset | str,
        Field(description="The dataset to use. Can be a Dataset object or string ref."),
    ]
    scorers: Annotated[
        list[Scorer | str] | None,
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
    _scorer_ref_cache: dict[str, str] = PrivateAttr(default_factory=dict)
    _model_ref_cache: dict[str, str] = PrivateAttr(default_factory=dict)

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
            # Check if ref already exists, use it; otherwise save the dataset
            if self.dataset.ref is not None:
                self._dataset_ref = str(self.dataset.ref)
            else:
                dataset_name = self.dataset.name or _default_dataset_name()
                wc.save(self.dataset, name=dataset_name)
                self._dataset_ref = str(self.dataset.ref)
        else:
            # It's a string - call dataset_create API with the name as the str
            dataset_name = self.dataset
            # Create an empty dataset with just the name
            req = tsi.DatasetCreateReq(
                project_id=project_id,
                name=dataset_name,
                description=None,
                rows=[],  # Empty dataset
            )

            res = wc.server.dataset_create(req)
            # Construct the dataset ref manually since DatasetCreateRes doesn't have a dataset_ref field
            self._dataset_ref = (
                f"weave:///{entity}/{project}/object/{res.object_id}:{res.digest}"
            )

        # Ensure model exists and get its ref
        self._model_ref = self._prepare_model_ref(
            self.model, project_id, entity, project
        )

        # Convert scorers to refs
        scorer_refs = []
        if self.scorers:
            for scorer in self.scorers:
                scorer_ref = self._prepare_scorer_ref(scorer)
                scorer_refs.append(scorer_ref)

        # Create the evaluation object via API
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name=self.name or default_evaluation_display_name,
            description=self.description,
            dataset=self._dataset_ref,
            scorers=scorer_refs,
            trials=1,
            eval_attributes=self.eval_attributes,
        )

        eval_res = wc.server.evaluation_create(eval_req)
        self._evaluation_ref = (
            f"weave:///{entity}/{project}/object/{eval_res.object_id}:{eval_res.digest}"
        )

        logger.debug(f"Created evaluation: {self._evaluation_ref}")

        # Create the evaluation run
        eval_run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=self._evaluation_ref,
            model=self._model_ref,
        )

        eval_run_res = wc.server.evaluation_run_create(eval_run_req)
        self._eval_run_id = eval_run_res.evaluation_run_id

        logger.debug(f"Created evaluation run: {self._eval_run_id}")

    def _prepare_model_ref(
        self, model: Model | str, project_id: str, entity: str, project: str
    ) -> str:
        """Prepare a model and return its weave ref.

        Uses caching to avoid repeated API calls for the same model.
        """
        # Generate cache key for this model
        if isinstance(model, Model):
            # Use ref if available, otherwise use object id as cache key
            if model.ref is not None:
                return str(model.ref)
            # Use model name if available, otherwise object id
            cache_key = model.name if model.name else f"model_{id(model)}"
        elif isinstance(model, str):
            cache_key = model
        else:
            raise TypeError(f"Invalid model type: {type(model)}")

        # Check cache first
        if cache_key in self._model_ref_cache:
            logger.debug(f"Using cached model ref for: {cache_key}")
            return self._model_ref_cache[cache_key]

        # Not in cache, need to create/save
        wc = require_weave_client()

        if isinstance(model, Model):
            # Save the model if it doesn't have a ref yet
            model_name = model.name or "model"
            wc.save(model, name=model_name)
            model_ref = str(model.ref)
        elif isinstance(model, str):
            # It's a string - call model_create API with the name as the str
            model_name = model
            # Use a minimal placeholder source code for models created from string names
            # The actual model name is stored in the model object metadata
            source_code = """from weave.flow.model import Model

class PlaceholderModel(Model):
    '''Placeholder model created from string name.'''
    pass
"""

            req = tsi.ModelCreateReq(
                project_id=project_id,
                name=model_name,
                description=None,
                source_code=source_code,
                attributes=None,
            )

            res = wc.server.model_create(req)
            model_ref = res.model_ref
        else:
            raise TypeError(f"Invalid model type: {type(model)}")

        # Cache the result
        self._model_ref_cache[cache_key] = model_ref
        logger.debug(f"Cached model ref for: {cache_key} -> {model_ref}")

        return model_ref

    def _prepare_scorer_ref(self, scorer: Scorer | str) -> str:
        """Prepare a scorer and return its weave ref.

        Uses caching to avoid repeated API calls for the same scorer.
        """
        # Generate cache key for this scorer
        if isinstance(scorer, str):
            cache_key = scorer
        elif isinstance(scorer, Scorer):
            # Use ref if available, otherwise use object id as cache key
            if scorer.ref is not None:
                return str(scorer.ref)
            # Use scorer name if available, otherwise object id
            cache_key = scorer.name if scorer.name else f"scorer_{id(scorer)}"
        else:
            raise TypeError(f"Invalid scorer type: {type(scorer)}")

        # Check cache first
        if cache_key in self._scorer_ref_cache:
            logger.debug(f"Using cached scorer ref for: {cache_key}")
            return self._scorer_ref_cache[cache_key]

        # Not in cache, need to create/save
        wc = require_weave_client()
        project_id = wc._project_id()

        if isinstance(scorer, str):
            # It's a string - call scorer_create API with the name as the str
            scorer_name = scorer
            # Use a minimal placeholder source code for scorers created from string names
            # The actual scorer name is stored in the scorer object metadata
            op_source_code = """def score(output):
    '''Placeholder scorer score function created from string name.'''
    raise NotImplementedError("Scorer created from string name - implement score method")
"""

            req = tsi.ScorerCreateReq(
                project_id=project_id,
                name=scorer_name,
                description=None,
                op_source_code=op_source_code,
            )

            res = wc.server.scorer_create(req)
            scorer_ref = res.scorer
        elif isinstance(scorer, Scorer):
            # Save the scorer if it doesn't have a ref yet
            scorer_name = scorer.name or "scorer"
            wc.save(scorer, name=scorer_name)
            scorer_ref = str(scorer.ref)
        else:
            raise TypeError(f"Invalid scorer type: {type(scorer)}")

        # Cache the result
        self._scorer_ref_cache[cache_key] = scorer_ref
        logger.debug(f"Cached scorer ref for: {cache_key} -> {scorer_ref}")

        return scorer_ref

    def _calculate_summary(
        self, summary: dict | None, auto_summarize: bool
    ) -> dict[str, Any]:
        """Calculate the final summary for the evaluation run.

        Args:
            summary: Summary data to log. If None, will be auto-calculated.
            auto_summarize: Whether to automatically calculate summary statistics.

        Returns:
            dict: The final summary dictionary.
        """
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

        # Merge summary data with user-provided summary
        final_summary = {}
        if summary_data:
            final_summary = summary_data
        if summary is not None:
            final_summary = {**final_summary, "output": summary}

        return final_summary

    def _log_prediction_internal(
        self,
        inputs: dict[str, Any],
        output: Any,
    ) -> tsi.PredictionCreateReq:
        """Internal helper to prepare prediction logging.

        Returns:
            PredictionCreateReq: The request object for creating a prediction.
        """
        if self._is_finalized:
            raise RuntimeError("Cannot log prediction after evaluation is finalized")

        if self._eval_run_id is None:
            raise RuntimeError("Evaluation run not initialized")

        wc = require_weave_client()
        project_id = wc._project_id()

        # Log the prediction via API
        req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=self._model_ref,
            inputs=inputs,
            output=output,
            evaluation_run_id=self._eval_run_id,
        )

        return req

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
        req = self._log_prediction_internal(inputs, output)

        wc = require_weave_client()
        res = wc.server.prediction_create(req)

        return self._create_score_logger(res.prediction_id, inputs, output)

    async def alog_prediction(
        self,
        inputs: dict[str, Any],
        output: Any,
    ) -> ScoreLoggerV2:
        """Log a prediction to the evaluation run (async version).

        Args:
            inputs: The input data for the prediction
            output: The output value

        Returns:
            ScoreLoggerV2 for logging scores

        Example:
            ```python
            pred = await ev.alog_prediction({'q': '...'}, output="answer")
            await pred.alog_score("correctness", 0.9)
            await pred.afinish()
            ```
        """
        req = self._log_prediction_internal(inputs, output)

        wc = require_weave_client()
        res = await asyncio.to_thread(wc.server.prediction_create, req)

        return self._create_score_logger(res.prediction_id, inputs, output)

    def log_example(
        self,
        inputs: dict[str, Any],
        output: Any,
        scores: dict[str, ScoreType],
    ) -> None:
        """Log a complete example with inputs, output, and scores.

        This is a convenience method that combines log_prediction and log_score
        for when you have all the data upfront.

        Args:
            inputs: The input data for the prediction
            output: The output value
            scores: Dictionary mapping scorer names to score values

        Example:
            ```python
            ev = EvaluationLoggerV2()
            ev.log_example(
                inputs={'q': 'What is 2+2?'},
                output='4',
                scores={'correctness': 1.0, 'fluency': 0.9}
            )
            ```
        """
        if self._is_finalized:
            raise ValueError(
                "Cannot log example after evaluation has been finalized. "
                "Call log_example before calling finish() or log_summary()."
            )

        # Log the prediction with the output
        pred = self.log_prediction(inputs=inputs, output=output)

        # Log all the scores
        for scorer_name, score_value in scores.items():
            pred.log_score(scorer_name, score_value)

        # Finish the prediction
        pred.finish()

    async def alog_example(
        self,
        inputs: dict[str, Any],
        output: Any,
        scores: dict[str, ScoreType],
    ) -> None:
        """Log a complete example with inputs, output, and scores (async version).

        This is a convenience method that combines alog_prediction and alog_score
        for when you have all the data upfront.

        Args:
            inputs: The input data for the prediction
            output: The output value
            scores: Dictionary mapping scorer names to score values

        Example:
            ```python
            ev = EvaluationLoggerV2()
            await ev.alog_example(
                inputs={'q': 'What is 2+2?'},
                output='4',
                scores={'correctness': 1.0, 'fluency': 0.9}
            )
            ```
        """
        if self._is_finalized:
            raise ValueError(
                "Cannot log example after evaluation has been finalized. "
                "Call alog_example before calling finish() or log_summary()."
            )

        # Log the prediction with the output
        pred = await self.alog_prediction(inputs=inputs, output=output)

        # Log all the scores in parallel
        if scores:
            await asyncio.gather(
                *[
                    pred.alog_score(scorer_name, score_value)
                    for scorer_name, score_value in scores.items()
                ]
            )

        # Finish the prediction
        await pred.afinish()

    def _create_score_logger(
        self, prediction_id: str, inputs: dict[str, Any], output: Any
    ) -> ScoreLoggerV2:
        """Internal helper to create and register a ScoreLoggerV2."""
        # Create the ScoreLoggerV2
        pred = ScoreLoggerV2(
            evaluation_logger=self,
            prediction_id=prediction_id,
            inputs=inputs,
            output=output,
        )

        self._accumulated_predictions.append(pred)

        logger.debug(f"Logged prediction with prediction_id={prediction_id}")

        return pred

    def _prepare_log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> tuple[tsi.EvaluationRunFinishReq, list[ScoreLoggerV2]]:
        """Prepare summary logging request and get unfinished predictions.

        Args:
            summary: Summary data to log. If None, will be auto-calculated.
            auto_summarize: Whether to automatically calculate summary statistics.

        Returns:
            Tuple of (request, unfinished_predictions)
        """
        if self._is_finalized:
            logger.warning("(NO-OP): Evaluation already finalized, cannot log summary.")
            return None, []  # type: ignore

        if self._eval_run_id is None:
            raise RuntimeError("Evaluation run not initialized")

        final_summary = self._calculate_summary(summary, auto_summarize)

        wc = require_weave_client()
        project_id = wc._project_id()

        # Get unfinished predictions
        unfinished_predictions = [
            pred for pred in self._accumulated_predictions if not pred._has_finished
        ]

        # Finish the evaluation run via API
        req = tsi.EvaluationRunFinishReq(
            project_id=project_id,
            evaluation_run_id=self._eval_run_id,
            summary=final_summary,
        )

        return req, unfinished_predictions

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
        req, unfinished_predictions = self._prepare_log_summary(summary, auto_summarize)
        if req is None:
            return

        # Finish any unfinished predictions before finalizing the evaluation run
        for pred in unfinished_predictions:
            pred.finish()

        wc = require_weave_client()
        wc.server.evaluation_run_finish(req)

        self._is_finalized = True
        logger.debug(f"Finished evaluation run: {self._eval_run_id}")

    async def alog_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary and finalize the evaluation run (async version).

        Args:
            summary: Summary data to log. If None, will be auto-calculated.
            auto_summarize: Whether to automatically calculate summary statistics.
        """
        req, unfinished_predictions = self._prepare_log_summary(summary, auto_summarize)
        if req is None:
            return

        # Finish any unfinished predictions in parallel before finalizing
        if unfinished_predictions:
            await asyncio.gather(*[pred.afinish() for pred in unfinished_predictions])

        wc = require_weave_client()
        await asyncio.to_thread(wc.server.evaluation_run_finish, req)

        self._is_finalized = True
        logger.debug(f"Finished evaluation run: {self._eval_run_id}")

    def _finish_evaluation_internal(
        self, exception: BaseException | None = None
    ) -> None:
        """Internal helper for finish logic.

        Args:
            exception: Optional exception to log with the evaluation run.
        """
        # If there's an exception, we might want to log it somehow
        # For now, just finalize with empty summary
        if exception is not None:
            logger.error(f"Evaluation failed with exception: {exception}")

        # Remove from global registry since we've manually finalized
        if self in _active_evaluation_loggers_v2:
            _active_evaluation_loggers_v2.remove(self)

    def finish(self, exception: BaseException | None = None) -> None:
        """Clean up the evaluation resources explicitly without logging a summary.

        Args:
            exception: Optional exception to log with the evaluation run.
        """
        if self._is_finalized:
            return

        self._finish_evaluation_internal(exception)

        # Finalize with empty summary
        self.log_summary(summary={}, auto_summarize=False)

    async def afinish(self, exception: BaseException | None = None) -> None:
        """Clean up the evaluation resources explicitly without logging a summary (async version).

        Args:
            exception: Optional exception to log with the evaluation run.
        """
        if self._is_finalized:
            return

        self._finish_evaluation_internal(exception)

        # Finalize with empty summary
        await self.alog_summary(summary={}, auto_summarize=False)

    def fail(self, exception: BaseException) -> None:
        """Convenience method to fail the evaluation with an exception."""
        self.finish(exception=exception)

    async def afail(self, exception: BaseException) -> None:
        """Convenience method to fail the evaluation with an exception (async version)."""
        await self.afinish(exception=exception)

    def __del__(self) -> None:
        """Ensure cleanup happens during garbage collection."""
        _cleanup_evaluation_v2(self)
