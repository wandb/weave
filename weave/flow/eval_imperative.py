from __future__ import annotations

import atexit
import datetime
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MethodType
from typing import Annotated, Any, TypeVar, Union, cast

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    validate_call,
)

import weave
from weave.flow.dataset import Dataset
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer, auto_summarize
from weave.flow.util import make_memorable_name
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op
from weave.trace.weave_client import Call

T = TypeVar("T")
ID = str
ScoreType = Union[float, bool, dict]

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

# Context variable to store the current output safely between threads.  This also
# ensures that only 1 version of the predict method is saved because the code
# contents are always the same.
current_output: ContextVar[Any] = ContextVar("current_output", default=None)
current_score: ContextVar[ScoreType | None] = ContextVar("current_score", default=None)
current_summary: ContextVar[dict | None] = ContextVar("current_summary", default=None)
current_predict_call: ContextVar[Call | None] = ContextVar(
    "current_predict_call", default=None
)

IMPERATIVE_EVAL_MARKER = {"_weave_eval_meta": {"imperative": True}}
IMPERATIVE_SCORE_MARKER = {"_weave_eval_meta": {"imperative": True, "score": True}}


@contextmanager
def _set_current_output(output: Any) -> Iterator[None]:
    """Set the current output in a thread-safe way using context variables."""
    token = current_output.set(output)
    try:
        yield
    finally:
        current_output.reset(token)


@contextmanager
def _set_current_score(score: ScoreType) -> Iterator[None]:
    token = current_score.set(score)
    try:
        yield
    finally:
        current_score.reset(token)


@contextmanager
def _set_current_summary(summary: dict) -> Iterator[None]:
    token = current_summary.set(summary)
    try:
        yield
    finally:
        current_summary.reset(token)


def _cast_to_cls(type_: type[T]) -> Callable[[str | T], T]:
    def _convert_to_cls_inner(value: str | T) -> T:
        if isinstance(value, str):
            cls_name = value

            # Dynamically create the class if the user only provides a name
            cls_name = _validate_class_name(cls_name)

            pydantic_config_dict = {
                "__annotations__": {"name": str},
                "name": cls_name,
            }

            cls = type(cls_name, (type_,), pydantic_config_dict)
            return cast(T, cls())

        elif isinstance(value, dict):
            attributes = value

            if "name" not in attributes:
                raise ValueError("Your dict must contain a `name` key.")

            pydantic_config_dict = {
                "__annotations__": dict.fromkeys(attributes, Any),
                **attributes,
            }
            cls = type(attributes["name"], (type_,), pydantic_config_dict)
            return cast(T, cls())

        elif isinstance(value, type_):
            instance = value
            if isinstance(instance, weave.Object) and not instance.name:
                instance.name = instance.__class__.__name__
            return instance

        raise TypeError("Unsupported type for casting")

    return _convert_to_cls_inner


def _cast_to_imperative_dataset(value: Dataset | list[dict] | str) -> Dataset:
    if isinstance(value, str):
        return Dataset(name=value, rows=weave.Table([{"dataset_id": value}]))
    elif isinstance(value, list):
        return Dataset(rows=weave.Table(value))
    elif isinstance(value, Dataset):
        return value
    else:
        raise TypeError("Unsupported type for casting")


def _default_dataset_name() -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


def _validate_class_name(name: str) -> str:
    """Validate the scorer name to be a valid class name."""
    # Check if name is not empty
    if not name:
        raise ValueError("Scorer name cannot be empty")

    # Check if name follows Python class naming conventions
    # Class names should start with a letter or underscore and contain only
    # alphanumeric characters and underscores
    import re

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(
            f"Invalid scorer name: '{name}'. Scorer names must start with a letter or underscore "
            "and contain only alphanumeric characters and underscores."
        )

    # Check if name is not a Python keyword
    import keyword

    if keyword.iskeyword(name):
        raise ValueError(f"Scorer name '{name}' cannot be a Python keyword")

    return name


class ScoreLogger(BaseModel):
    """This class provides an imperative interface for logging scores."""

    # model_id: ID
    predict_and_score_call: Call
    evaluate_call: Call
    predict_call: Call

    _captured_scores: dict[str, ScoreType] = PrivateAttr(default_factory=dict)
    _has_finished: bool = PrivateAttr(False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def finish(self) -> None:
        if self._has_finished:
            logger.warn("(NO-OP): Already called finish, returning.")
            return

        scores = self._captured_scores

        wc = require_weave_client()
        wc.finish_call(
            self.predict_and_score_call,
            output={
                "output": self.predict_call.output,
                "scores": scores,
                "model_latency": None,
            },
        )

        self._has_finished = True

    def log_score(self, scorer: Scorer | dict | str, score: ScoreType) -> None:
        """Log a score synchronously."""
        import asyncio

        # When in an active asyncio test environment (like pytest.mark.asyncio),
        # we need special handling to avoid "already running" errors
        try:
            loop = asyncio.get_running_loop()
            if asyncio.current_task() is not None:
                # We're in an async context, just run the coroutine synchronously
                import nest_asyncio

                nest_asyncio.apply()
                return loop.run_until_complete(self.alog_score(scorer, score))
            else:
                # We're not in an async context, but a loop exists
                return loop.run_until_complete(self.alog_score(scorer, score))
        except RuntimeError:
            # No event loop exists, create one with asyncio.run
            return asyncio.run(self.alog_score(scorer, score))

    @validate_call
    async def alog_score(
        self,
        scorer: Annotated[
            Scorer | dict | str,
            BeforeValidator(_cast_to_cls(Scorer)),
            Field(
                description="A metadata-only scorer used for comparisons."
                "Alternatively, you can pass a dict of attributes or just a string"
                "representing the ID of your scorer."
            ),
        ],
        score: ScoreType,
    ) -> None:
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        # this is safe; pydantic casting is done in validator above
        scorer = cast(Scorer, scorer)

        @weave.op(name=scorer.name, enable_code_capture=False)
        def score_method(self: Scorer, *, output: Any, inputs: Any) -> ScoreType:
            # TODO: can't use score here because it will cause version mismatch
            # return score
            return cast(ScoreType, current_score.get())

        scorer.__dict__["score"] = MethodType(score_method, scorer)

        # attach the score feedback to the predict call
        with call_context.set_call_stack(
            [self.evaluate_call, self.predict_and_score_call]
        ):
            with _set_current_score(score):
                with weave.attributes(IMPERATIVE_SCORE_MARKER):
                    await self.predict_call.apply_scorer(scorer)

        # this is always true because of how the scorer is created in the validator
        scorer_name = cast(str, scorer.name)
        self._captured_scores[scorer_name] = score


class EvaluationLogger(BaseModel):
    """This class provides an imperative interface for logging evaluations.

    An evaluation is started automatically when the first prediction is logged
    using the `log_prediction` method, and finished when the `log_summary` method
    is called.

    Each time you log a prediction, you will get back a `ScoreLogger` object.
    You can use this object to log scores and metadata for that specific
    prediction. For more information, see the `ScoreLogger` class.

    Example:
        ```python
        ev = EvaluationLogger()
        pred = ev.log_prediction(inputs, output)
        pred.log_score(scorer_name, score)
        ev.log_summary(summary)
        ```
    """

    name: Annotated[
        str | None,
        Field(
            default=None,
            description="(Optional): A name for the evaluation call."
            "If not provided, a default name will be generated.",
        ),
    ]
    model: Annotated[
        Model | dict | str,
        BeforeValidator(_cast_to_cls(Model)),
        Field(
            default_factory=Model,
            description="(Optional): A metadata-only Model used for comparisons."
            "Alternatively, you can pass a dict of attributes or just a string"
            "representing the ID of your model.",
        ),
    ]
    dataset: Annotated[
        Dataset | list[dict] | str,
        BeforeValidator(_cast_to_imperative_dataset),
        Field(
            default_factory=lambda: Dataset(
                rows=weave.Table([{"dataset_id": _default_dataset_name()}]),
            ),
            description="(Optional): A metadata-only Dataset used for comparisons."
            "If you already know your rows ahead of time, you can pass either"
            "a Dataset or list[dict]."
            "If you don't, you can just pass any string as a unique identifier",
        ),
    ]

    _eval_started: bool = PrivateAttr(False)
    _logged_summary: bool = PrivateAttr(False)
    _is_finalized: bool = PrivateAttr(False)
    _evaluate_call: Call | None = PrivateAttr(None)
    _pseudo_evaluation: Evaluation = PrivateAttr()

    @property
    def ui_url(self) -> str | None:
        # In normal usage, _evaluate_call will never be None because it's set
        # at init time.
        if self._evaluate_call is None:
            return None
        return self._evaluate_call.ui_url

    # This private attr is used to keep track of predictions so we can finish
    # them if the user forgot to.
    _accumulated_predictions: list[ScoreLogger] = PrivateAttr(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Initialize the pseudo evaluation with the dataset from the model."""
        # Register this instance in the global registry for atexit cleanup
        _active_evaluation_loggers.append(self)

        # At this point dataset has already been processed by the validator
        # and converted to a Dataset object
        self._pseudo_evaluation = Evaluation(
            dataset=cast(Dataset, self.dataset),
            scorers=[],
        )

        # The following section is a "hacky" way to create Model and Evaluation
        # objects that "look right" to our object saving system.

        # --- Setup the model object ---
        @weave.op(name="Model.predict", enable_code_capture=False)
        def predict(self: Model, inputs: dict) -> Any:
            # Get the output from the context variable
            return current_output.get()

        self.model.__dict__["predict"] = MethodType(predict, self.model)

        # --- Setup the evaluation object ---
        @weave.op(name="Evaluation.evaluate", enable_code_capture=False)
        def evaluate(self: Evaluation, model: Model) -> None: ...

        @weave.op(name="Evaluation.predict_and_score", enable_code_capture=False)
        def predict_and_score(self: Evaluation, model: Model, example: dict) -> dict:
            predict_method = cast(Op, model.get_infer_method())
            with weave.attributes(IMPERATIVE_EVAL_MARKER):
                output, predict_call = predict_method.call(model, example)
                current_predict_call.set(predict_call)

            # This data is just a placeholder to give a sense of the data shape.
            # The actual output is explicitly replaced in ScoreLogger.finish.
            return {
                "output": output,
                "scores": {},
                "model_latency": None,
            }

        @weave.op(name="Evaluation.summarize", enable_code_capture=False)
        def summarize(self: Evaluation) -> dict:
            return cast(dict, current_summary.get())

        self._pseudo_evaluation.__dict__.update(
            {
                "evaluate": MethodType(evaluate, self._pseudo_evaluation),
                "predict_and_score": MethodType(
                    predict_and_score, self._pseudo_evaluation
                ),
                "summarize": MethodType(summarize, self._pseudo_evaluation),
            }
        )

        # Create the evaluation call
        wc = require_weave_client()
        self._evaluate_call = wc.create_call(
            display_name=self.name or default_evaluation_display_name,
            op=self._pseudo_evaluation.evaluate,
            inputs={
                "self": self._pseudo_evaluation,
                "model": self.model,
            },
            attributes=IMPERATIVE_EVAL_MARKER,
        )
        assert self._evaluate_call is not None
        call_context.push_call(self._evaluate_call)

    def _cleanup_predictions(self) -> None:
        if self._is_finalized:
            return

        for pred in self._accumulated_predictions:
            if pred._has_finished:
                continue
            try:
                pred.finish()
            except Exception:
                # This is best effort.  If we fail, just swallow the error.
                pass

    def _finalize_evaluation(self, output: Any = None) -> None:
        """Handles the final steps of the evaluation: cleaning up predictions and finishing the main call."""
        if self._is_finalized:
            return

        self._cleanup_predictions()

        assert (
            self._evaluate_call is not None
        ), "Evaluation call should exist for finalization"

        # Finish the evaluation call
        wc = require_weave_client()
        # Ensure the call is finished even if there was an error during summarize or elsewhere
        try:
            wc.finish_call(self._evaluate_call, output=output)
        except Exception:
            # Log error but continue cleanup
            logger.error(
                "Failed to finish evaluation call during finalization.", exc_info=True
            )

        # Pop the call regardless of finish success
        try:
            call_context.pop_call(self._evaluate_call.id)
        except Exception:
            # If popping fails (e.g., context already unwound), log and ignore
            logger.warning("Failed to pop evaluation call from context.", exc_info=True)

        self._is_finalized = True

    def log_prediction(self, inputs: dict, output: Any) -> ScoreLogger:
        """Log a prediction to the Evaluation, and return a reference.

        The reference can be used to log scores which are attached to the specific
        prediction instance."""
        # Make the prediction call
        with _set_current_output(output):
            with weave.attributes(IMPERATIVE_EVAL_MARKER):
                _, predict_and_score_call = (
                    self._pseudo_evaluation.predict_and_score.call(
                        self._pseudo_evaluation,
                        self.model,
                        inputs,
                        __require_explicit_finish=True,
                    )
                )

        # Get the predict_call from the context variable
        predict_call = current_predict_call.get()
        if predict_call is None:
            raise ValueError("predict_call should not be None")

        assert self._evaluate_call is not None
        pred = ScoreLogger(
            predict_and_score_call=predict_and_score_call,
            evaluate_call=self._evaluate_call,
            predict_call=predict_call,
        )
        self._accumulated_predictions.append(pred)
        return pred

    def log_summary(self, summary: dict | None = None) -> None:
        """Log a summary dict to the Evaluation.

        This will calculate the summary, call the summarize op, and then finalize
        the evaluation, meaning no more predictions or scores can be logged.
        """
        if self._is_finalized:
            logger.warn("(NO-OP): Evaluation already finalized, cannot log summary.")
            return

        # Calculate summary
        data_to_summarize = [
            pred._captured_scores for pred in self._accumulated_predictions
        ]
        summary_data = auto_summarize(data_to_summarize)
        final_summary = {}
        if summary_data:
            final_summary = summary_data
        if summary is not None:
            final_summary = {**final_summary, **summary}

        # Call the summarize op
        assert (
            self._evaluate_call is not None
        ), "Evaluation call should exist for summary"
        try:
            with _set_current_summary(final_summary):
                with weave.attributes(IMPERATIVE_EVAL_MARKER):
                    self._pseudo_evaluation.summarize()
        except Exception:
            logger.error("Error during execution of summarize op.", exc_info=True)
            # Even if summarize fails, try to finalize with the calculated summary

        self._finalize_evaluation(output=final_summary)

    def finish(self) -> None:
        """Clean up the evaluation resources explicitly without logging a summary.

        Ensures all prediction calls and the main evaluation call are finalized.
        This is automatically called if the logger is used as a context manager.
        """
        if self._is_finalized:
            return

        # Finalize with None output, indicating closure without summary
        self._finalize_evaluation(output=None)

        # Remove from global registry since we've manually finalized
        if self in _active_evaluation_loggers:
            _active_evaluation_loggers.remove(self)

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
