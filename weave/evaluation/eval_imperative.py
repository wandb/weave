from __future__ import annotations

import atexit
import logging
from typing import TYPE_CHECKING, Any, overload

from weave.dataset.dataset import Dataset
from weave.evaluation.eval_imperative_v1 import (
    EvaluationLoggerV1,
    ScoreLoggerV1,
    ScoreType,
)
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2, ScoreLoggerV2
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.trace.settings import should_use_evaluation_logger_v2
from weave.type_wrappers.Content.content import Content
from weave.utils.sentinel import NOT_SET, _NotSetType

if TYPE_CHECKING:
    from weave.evaluation.eval_imperative_v1 import _LogScoreContext

logger = logging.getLogger(__name__)

# Registry to track active EvaluationLogger instances
_active_evaluation_loggers: list[EvaluationLogger] = []


# Register cleanup handler for program exit
def _cleanup_all_evaluations() -> None:
    for eval_logger in _active_evaluation_loggers:
        _cleanup_evaluation(eval_logger)


def _cleanup_evaluation(eval_logger: EvaluationLogger) -> None:
    try:
        if not eval_logger._is_finalized:
            eval_logger.finish()
    except Exception:
        logger.error("Error during cleanup of EvaluationLogger", exc_info=True)


atexit.register(_cleanup_all_evaluations)


class ScoreLogger:
    """Interface for logging scores and managing prediction outputs.

    This class wraps either ScoreLoggerV1 or ScoreLoggerV2 based on the setting,
    providing a consistent interface regardless of the underlying implementation.

    Direct usage - when output is known upfront:

    ```python
    ev = EvaluationLogger()
    pred = ev.log_prediction(inputs={'q': 'Hello'}, output='Hi there!')
    pred.log_score("correctness", 0.9)
    pred.finish()
    ```

    Context manager usage - for dynamic outputs and automatic call stack management:

    ```python
    ev = EvaluationLogger()

    # Works whether output is provided or not
    with ev.log_prediction(inputs={'q': 'Hello'}) as pred:
        # Operations here automatically become children of the predict call
        response = your_llm_call(...)
        pred.output = response.content

        # Log scores directly
        pred.log_score("correctness", 0.9)

        # Or use log_score as a context manager for complex scoring (V1 only)
        with pred.log_score("reasoning_quality") as score:
            analysis = analyze_response(...)
            score.value = analysis.score
    # Automatically calls finish() on exit and restores call stack
    ```
    """

    def __init__(self, impl: ScoreLoggerV1 | ScoreLoggerV2) -> None:
        self._impl = impl

    def finish(self, output: Any | None = None) -> None:
        """Finish the prediction and log all scores.

        Args:
            output: Optional output to override the prediction output. If not provided,
                uses the output passed to log_prediction.
        """
        self._impl.finish(output)

    @property
    def _has_finished(self) -> bool:
        return self._impl._has_finished

    @property
    def _captured_scores(self) -> dict[str, ScoreType]:
        return self._impl._captured_scores

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
        """Log a score synchronously or return a context manager for deferred scoring.

        Can be used in two ways:

        1. Direct scoring (immediate):
        ```python
        pred.log_score("correctness", 0.9)
        pred.log_score("failed_check", None)  # None is a valid score value
        ```

        2. Context manager (deferred with automatic call stack, V1 only):
        ```python
        with pred.log_score("correctness") as score_ctx:
            result = calculate_score(...)
            score_ctx.value = result
        ```
        """
        if isinstance(self._impl, ScoreLoggerV1):
            if score is NOT_SET:
                return self._impl.log_score(scorer)
            return self._impl.log_score(scorer, score)
        else:
            # V2 doesn't support context manager for log_score
            if score is NOT_SET:
                raise ValueError(
                    "V2 API does not support context manager for log_score. "
                    "Please provide the score value directly."
                )
            return self._impl.log_score(scorer, score)

    async def alog_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        """Async version of log_score. V1 only."""
        if isinstance(self._impl, ScoreLoggerV1):
            await self._impl.alog_score(scorer, score)
        else:
            # V2 is synchronous
            self._impl.log_score(scorer, score)

    @property
    def output(self) -> Any:
        """Get the current output value."""
        return self._impl.output

    @output.setter
    def output(self, value: Any) -> None:
        """Set the output value that will be used when finishing."""
        self._impl.output = value

    def __enter__(self) -> ScoreLogger:
        """Enter context manager and set call stack to predict_call."""
        self._impl.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, restore call stack, and automatically finish."""
        self._impl.__exit__(exc_type, exc_val, exc_tb)


class EvaluationLogger:
    """This class provides an imperative interface for logging evaluations.

    Based on the `use_evaluation_logger_v2` setting, this class will use either
    the legacy call-based approach (V1) or the new Object APIs (V2).

    An evaluation is started automatically when the first prediction is logged
    using the `log_prediction` method, and finished when the `log_summary` method
    is called.

    Each time you log a prediction, you will get back a `ScoreLogger` object.
    You can use this object to log scores and metadata for that specific
    prediction. For more information, see the `ScoreLogger` class.

    Basic usage - log predictions with inputs and outputs directly:

    ```python
    ev = EvaluationLogger()

    # Log predictions with known inputs/outputs
    pred = ev.log_prediction(inputs={'q': 'Hello'}, outputs={'a': 'Hi there!'})
    pred.log_score("correctness", 0.9)

    # Finish the evaluation
    ev.log_summary({"avg_score": 0.9})
    ```

    Advanced usage - use context manager for dynamic outputs and nested operations:

    ```python
    ev = EvaluationLogger()

    # Use context manager when you need to capture nested operations
    with ev.log_prediction(inputs={'q': 'Hello'}) as pred:
        # Any operations here (like LLM calls) automatically become
        # children of the predict call
        response = your_llm_call(...)
        pred.output = response.content
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
        self._use_v2 = should_use_evaluation_logger_v2()

        if self._use_v2:
            self._impl: EvaluationLoggerV1 | EvaluationLoggerV2 = EvaluationLoggerV2(
                name=name,
                model=model,
                dataset=dataset,
                eval_attributes=eval_attributes,
                scorers=scorers,
            )
        else:
            self._impl = EvaluationLoggerV1(
                name=name,
                model=model,
                dataset=dataset,
                eval_attributes=eval_attributes,
                scorers=scorers,
            )

        # Register this instance in the global registry for atexit cleanup
        _active_evaluation_loggers.append(self)

    @property
    def _is_finalized(self) -> bool:
        return self._impl._is_finalized

    @property
    def ui_url(self) -> str | None:
        return self._impl.ui_url

    @property
    def attributes(self) -> dict[str, Any]:
        return self._impl.attributes

    def log_prediction(
        self, inputs: dict[str, Any], output: Any = None
    ) -> ScoreLogger:
        """Log a prediction to the Evaluation.

        Returns a ScoreLogger that can be used directly or as a context manager.

        Args:
            inputs: The input data for the prediction
            output: The output value. Defaults to None. Can be set later using pred.output.

        Returns:
            ScoreLogger for logging scores and optionally finishing the prediction.

        Example (direct):
            pred = ev.log_prediction({'q': '...'}, output="answer")
            pred.log_score("correctness", 0.9)
            pred.finish()

        Example (context manager):
            with ev.log_prediction({'q': '...'}) as pred:
                response = model(...)
                pred.output = response
                pred.log_score("correctness", 0.9)
            # Automatically calls finish() on exit
        """
        impl_pred = self._impl.log_prediction(inputs=inputs, output=output)
        return ScoreLogger(impl_pred)

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

        Example:
        ```python
        ev = EvaluationLogger()
        ev.log_example(
            inputs={'q': 'What is 2+2?'},
            output='4',
            scores={'correctness': 1.0, 'fluency': 0.9}
        )
        ```
        """
        self._impl.log_example(inputs=inputs, output=output, scores=scores)

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary dict to the Evaluation.

        This will calculate the summary, call the summarize op, and then finalize
        the evaluation, meaning no more predictions or scores can be logged.
        """
        self._impl.log_summary(summary=summary, auto_summarize=auto_summarize)

        # Remove from global registry since we've finalized
        if self in _active_evaluation_loggers:
            _active_evaluation_loggers.remove(self)

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
        """Attach a view to the evaluation's main call summary under `weave.views`.

        Saves the provided content as an object in the project and writes its
        reference URI under `summary.weave.views.<name>` for the evaluation's
        `evaluate` call. String inputs are wrapped as text content using
        `Content.from_text` with the provided extension or mimetype.

        Args:
            name: The view name to display, used as the key under `summary.weave.views`.
            content: A `weave.Content` instance or string to serialize.
            extension: Optional file extension for string content inputs.
            mimetype: Optional MIME type for string content inputs.
            metadata: Optional metadata attached to newly created `Content`.
            encoding: Text encoding for string content inputs.

        Returns:
            None

        Examples:
            >>> import weave
            >>> ev = weave.EvaluationLogger()
            >>> ev.set_view("report", "# Report", extension="md")
        """
        self._impl.set_view(
            name=name,
            content=content,
            extension=extension,
            mimetype=mimetype,
            metadata=metadata,
            encoding=encoding,
        )

    def finish(self, exception: BaseException | None = None) -> None:
        """Clean up the evaluation resources explicitly without logging a summary.

        Ensures all prediction calls and the main evaluation call are finalized.
        This is automatically called if the logger is used as a context manager.
        """
        self._impl.finish(exception=exception)

        # Remove from global registry since we've manually finalized
        if self in _active_evaluation_loggers:
            _active_evaluation_loggers.remove(self)

    def fail(self, exception: BaseException) -> None:
        """Convenience method to fail the evaluation with an exception."""
        self.finish(exception=exception)

    def __del__(self) -> None:
        """Ensure cleanup happens during garbage collection."""
        _cleanup_evaluation(self)


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
