from __future__ import annotations

import atexit
import logging
from typing import Any, cast

from weave.dataset.dataset import Dataset
from weave.evaluation.eval_imperative_v1 import EvaluationLoggerV1, ScoreLoggerV1
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2, ScoreLoggerV2
from weave.flow.model import Model
from weave.trace.settings import should_use_evaluation_logger_v2

ScoreLogger = ScoreLoggerV1 | ScoreLoggerV2


logger = logging.getLogger(__name__)

# Registry to track active EvaluationLogger instances for cleanup
# Both V1 and V2 implementations register themselves here
_active_evaluation_loggers: list[Any] = []


def _cleanup_all_evaluations() -> None:
    """Cleanup handler for program exit."""
    for eval_logger in list(_active_evaluation_loggers):
        _cleanup_evaluation(eval_logger)


def _cleanup_evaluation(eval_logger: Any) -> None:
    """Clean up a single evaluation logger."""
    try:
        if not eval_logger._is_finalized:
            eval_logger.finish()
    except Exception:
        logger.error("Error during cleanup of EvaluationLogger", exc_info=True)


def register_evaluation_logger(eval_logger: Any) -> None:
    """Register an evaluation logger for atexit cleanup."""
    _active_evaluation_loggers.append(eval_logger)


def unregister_evaluation_logger(eval_logger: Any) -> None:
    """Unregister an evaluation logger from atexit cleanup."""
    if eval_logger in _active_evaluation_loggers:
        _active_evaluation_loggers.remove(eval_logger)


atexit.register(_cleanup_all_evaluations)


class EvaluationLogger:
    """This class provides an imperative interface for logging evaluations.

    Based on the `use_evaluation_logger_v2` setting, this class will dispatch to either
    the legacy call-based approach (V1) or the new Object APIs (V2).

    An evaluation is started automatically when the first prediction is logged
    using the `log_prediction` method, and finished when the `log_summary` method
    is called.

    Each time you log a prediction, you will get back a `ScoreLogger` object.
    You can use this object to log scores and metadata for that specific
    prediction.

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

    def __new__(
        cls,
        name: str | None = None,
        model: Model | dict | str | None = None,
        dataset: Dataset | list[dict] | str | None = None,
        eval_attributes: dict[str, Any] | None = None,
        scorers: list[str] | None = None,
    ) -> EvaluationLogger:
        """Create and return either a V1 or V2 EvaluationLogger based on settings."""
        instance: EvaluationLoggerV1 | EvaluationLoggerV2
        if should_use_evaluation_logger_v2():
            instance = EvaluationLoggerV2(
                name=name,
                model=model,
                dataset=dataset,
                eval_attributes=eval_attributes,
                scorers=scorers,
            )
        else:
            instance = EvaluationLoggerV1(
                name=name,
                model=model,
                dataset=dataset,
                eval_attributes=eval_attributes,
                scorers=scorers,
            )
        return cast(EvaluationLogger, instance)

    def log_prediction(self, inputs: dict[str, Any], output: Any = None) -> ScoreLogger:
        """Log a prediction to the Evaluation.

        This method is implemented by EvaluationLoggerV1 and EvaluationLoggerV2.
        This stub exists for type checking purposes only.
        """
        raise NotImplementedError("This method should be implemented by V1 or V2")

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary dict to the Evaluation.

        This method is implemented by EvaluationLoggerV1 and EvaluationLoggerV2.
        This stub exists for type checking purposes only.
        """
        raise NotImplementedError("This method should be implemented by V1 or V2")


class ImperativeEvaluationLogger(EvaluationLogger):
    """Legacy class name for EvaluationLogger.

    This class is maintained for backward compatibility.
    Please use EvaluationLogger instead.
    """

    def __new__(
        cls,
        name: str | None = None,
        model: Model | dict | str | None = None,
        dataset: Dataset | list[dict] | str | None = None,
        eval_attributes: dict[str, Any] | None = None,
        scorers: list[str] | None = None,
    ) -> ImperativeEvaluationLogger:
        logger.warning(
            "ImperativeEvaluationLogger was renamed to EvaluationLogger in 0.51.44. "
            "Please use EvaluationLogger instead. ImperativeEvaluationLogger will "
            "be removed in a future version."
        )
        instance = super().__new__(
            cls,
            name=name,
            model=model,
            dataset=dataset,
            eval_attributes=eval_attributes,
            scorers=scorers,
        )
        return cast(ImperativeEvaluationLogger, instance)
