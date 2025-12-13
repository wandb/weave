from __future__ import annotations

import asyncio
import atexit
import contextlib
import datetime
import json
import keyword
import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from types import MethodType
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from weave.dataset.dataset import Dataset
from weave.evaluation.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import MissingInferenceMethodError, Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
from weave.flow.util import make_memorable_name
from weave.object.obj import Object
from weave.trace.api import attributes
from weave.trace.call import Call
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op, as_op, op
from weave.trace.table import Table
from weave.trace.util import Thread
from weave.trace.view_utils import set_call_view
from weave.type_wrappers.Content.content import Content
from weave.utils.sentinel import NOT_SET, _NotSetType

if TYPE_CHECKING:
    from weave.trace.call import Call

T = TypeVar("T")
ID = str
ScoreType = float | bool | dict

logger = logging.getLogger(__name__)

# Class names should start with a letter or underscore and contain only alphanumeric characters and underscores
VALID_CLASS_NAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

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


def _sanitize_class_name(name: str) -> str:
    """Return a valid Python class name based on a string."""
    # Remove characters that are not alphanumeric or underscore
    class_name = re.sub(r"\W", "", name)
    if class_name == "":
        return "GeneratedClass"

    # Ensure it starts with a letter or underscore (prepend "C" if not)
    first_char = class_name[0]
    if not first_char.isalpha() and first_char != "_":
        class_name = "C" + class_name

    # Avoid Python keywords
    if keyword.iskeyword(class_name):
        class_name += "Class"

    return class_name


def _cast_to_cls(type_: type[T]) -> Callable[[str | dict | T], T]:
    def _convert_to_cls_inner(value: str | dict | T) -> T:
        if isinstance(value, str):
            # Dynamically create the class if the user only provides a name
            cls_name = _sanitize_class_name(value)

            # Sanitization should have ensured a valid class name, but double check for safety
            cls_name = _validate_class_name(cls_name, type_.__name__)

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
            if isinstance(instance, Object) and not instance.name:
                instance.name = instance.__class__.__name__
            return instance

        raise TypeError("Unsupported type for casting")

    return _convert_to_cls_inner


def _cast_to_imperative_dataset(value: Dataset | list[dict] | str) -> Dataset:
    if isinstance(value, str):
        return Dataset(name=value, rows=Table([{"dataset_id": value}]))
    elif isinstance(value, list):
        return Dataset(rows=Table(value))
    elif isinstance(value, Dataset):
        return value
    else:
        raise TypeError("Unsupported type for casting")


def _default_dataset_name() -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


def _validate_class_name(name: str, base_class_name: str = "Class") -> str:
    """Validate the class name to be a valid Python class name."""
    # Check if name is not empty
    if not name:
        raise ValueError(f"{base_class_name} name cannot be empty")

    if not VALID_CLASS_NAME_REGEX.match(name):
        raise ValueError(
            f"Invalid `{base_class_name}` name: '{name}'. `{base_class_name}` names must start with a letter or underscore "
            "and contain only alphanumeric characters and underscores."
        )

    # Check if name is not a Python keyword
    if keyword.iskeyword(name):
        raise ValueError(
            f"`{base_class_name}` name '{name}' cannot be a Python keyword"
        )

    return name


class ScorerCache:
    _cached_scorers: dict[str, Scorer]
    _cached_scorers_lock: Any
    _max_size: int

    def __init__(self, max_size: int = 1000) -> None:
        self._cached_scorers = {}
        self._cached_scorers_lock = Lock()
        self._max_size = max_size

    def get_scorer(
        self, scorer_id: str, default_factory: Callable[[], Scorer]
    ) -> Scorer:
        with self._cached_scorers_lock:
            if scorer_id not in self._cached_scorers:
                if len(self._cached_scorers) >= self._max_size:
                    self._cached_scorers.popitem()
                self._cached_scorers[scorer_id] = default_factory()
        return self._cached_scorers[scorer_id]


global_scorer_cache = ScorerCache()


class _LogScoreContext:
    """Context manager for logging scores with automatic call stack management.

    ```python
    with pred.log_score("correctness") as score_ctx:
        # Operations here become children of the score call
        result = calculate_correctness(...)
        score_ctx.value = result
    # Score is automatically logged on exit
    ```
    """

    def __init__(
        self, score_logger: ScoreLogger, scorer: Scorer | dict | str, score_call: Call
    ):
        self.score_logger = score_logger
        self.scorer = scorer
        self.score_call = score_call
        self._score_value: ScoreType | None = None
        self._call_stack_context: (
            contextlib.AbstractContextManager[list[Call]] | None
        ) = None

    @property
    def value(self) -> ScoreType | None:
        """Get the current score value."""
        return self._score_value

    @value.setter
    def value(self, val: ScoreType) -> None:
        """Set the score value that will be logged on exit."""
        self._score_value = val

    def __enter__(self) -> _LogScoreContext:
        """Enter context and set call stack to include the score call."""
        # Set call stack to include the score call so operations become children
        self._call_stack_context = call_context.set_call_stack(
            [
                self.score_logger.evaluate_call,
                self.score_logger.predict_and_score_call,
                self.score_call,
            ]
        )
        self._call_stack_context.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context, restore call stack, and finish the score call."""
        try:
            # scorer is guaranteed to be a Scorer instance here because it was prepared in _create_score_call
            if self._score_value is not None:
                # Finish the score call with the value
                self.score_logger._finish_score_call(
                    self.score_call, cast(Scorer, self.scorer), self._score_value
                )
            elif exc_type is not None:
                # If there was an exception and no value was set, finish with the exception
                self.score_logger._finish_score_call(
                    self.score_call, cast(Scorer, self.scorer), exception=exc_val
                )
            else:
                # If no exception occurred but no value was set, raise an error
                raise ValueError(
                    f"Score value was not set for scorer '{cast(Scorer, self.scorer).name}'. "
                    "Please set score_ctx.value within the context manager."
                )
        finally:
            # Restore call stack - always happens even if finish fails
            if self._call_stack_context is not None:
                self._call_stack_context.__exit__(exc_type, exc_val, exc_tb)


class ScoreLogger:
    """Interface for logging scores and managing prediction outputs.

    This class is returned by `EvaluationLogger.log_prediction()` and can be used
    either directly or as a context manager.

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

        # Or use log_score as a context manager for complex scoring
        with pred.log_score("reasoning_quality") as score:
            analysis = analyze_response(...)
            score.value = analysis.score
    # Automatically calls finish() on exit and restores call stack
    ```
    """

    def __init__(
        self,
        predict_and_score_call: Call,
        evaluate_call: Call,
        predict_call: Call,
        predefined_scorers: list[str] | None = None,
    ) -> None:
        self.predict_and_score_call = predict_and_score_call
        self.evaluate_call = evaluate_call
        self.predict_call = predict_call
        self.predefined_scorers = predefined_scorers

        self._captured_scores: dict[str, ScoreType] = {}
        self._has_finished: bool = False
        self._predict_output: Any = None
        self._call_stack_context: (
            contextlib.AbstractContextManager[list[Call]] | None
        ) = None

    def finish(self, output: Any | None = None) -> None:
        """Finish the prediction and log all scores.

        Args:
            output: Optional output to override the prediction output. If not provided,
                uses the output passed to log_prediction.
        """
        if self._has_finished:
            logger.warning("(NO-OP): Already called finish, returning.")
            return

        scores = self._captured_scores

        # Use the provided output or fall back to the stored output
        final_output = output if output is not None else self._predict_output

        wc = require_weave_client()

        # First, finish the predict_call to compute its summary (including child costs)
        wc.finish_call(
            self.predict_call,
            output=final_output,
        )

        # Then finish the predict_and_score_call with the scores
        wc.finish_call(
            self.predict_and_score_call,
            output={
                "output": final_output,
                "scores": scores,
                "model_latency": None,
            },
        )

        self._has_finished = True

    def _prepare_scorer(self, scorer: Scorer | dict | str) -> Scorer:
        """Prepare and validate a scorer."""
        if not isinstance(scorer, Scorer):
            scorer_id = json.dumps(scorer)
            scorer = global_scorer_cache.get_scorer(
                scorer_id, lambda: _cast_to_cls(Scorer)(scorer)
            )
        scorer = cast(Scorer, scorer)

        # Check if scorer is in predefined list
        if self.predefined_scorers:
            scorer_name = cast(str, scorer.name)
            if scorer_name not in self.predefined_scorers:
                logger.warning(
                    f"Scorer '{scorer_name}' is not in the predefined scorers list. "
                    f"Expected one of: {sorted(self.predefined_scorers)}"
                )

        return scorer

    def _create_score_call(self, scorer: Scorer | dict | str) -> tuple[Call, Scorer]:
        """Create a score call but don't finish it yet."""
        scorer = self._prepare_scorer(scorer)

        # Create a placeholder score method
        @op(name=scorer.name, enable_code_capture=False)
        def score_method(self: Scorer, *, output: Any, inputs: Any) -> ScoreType:
            raise NotImplementedError("Score method should not be called directly")

        scorer.__dict__["score"] = MethodType(score_method, scorer)

        # Create the score call with predict_and_score as parent
        with attributes(IMPERATIVE_SCORE_MARKER):
            wc = require_weave_client()
            score_call = wc.create_call(
                as_op(scorer.score),
                inputs={
                    "self": scorer,
                    "output": self._predict_output,
                    "inputs": self.predict_call.inputs,
                },
                parent=self.predict_and_score_call,
                use_stack=False,
            )

        return score_call, scorer

    def _finish_score_call(
        self,
        score_call: Call,
        scorer: Scorer,
        score_value: ScoreType | None = None,
        exception: BaseException | None = None,
    ) -> None:
        """Finish a score call and record the score."""
        wc = require_weave_client()
        wc.finish_call(score_call, output=score_value, exception=exception)
        if exception is None and score_value is not None:
            self._captured_scores[cast(str, scorer.name)] = score_value

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

        2. Context manager (deferred with automatic call stack):
        ```python
        with pred.log_score("correctness") as score_ctx:
            result = calculate_score(...)
            score_ctx.value = result
        ```
        """
        # If no score provided, return a context manager for deferred scoring
        if score is NOT_SET:
            score_call, prepared_scorer = self._create_score_call(scorer)
            return _LogScoreContext(self, prepared_scorer, score_call)

        # Type narrowing: score is now guaranteed to be ScoreType
        assert not isinstance(score, _NotSetType), "score should not be NOT_SET here"
        score_value: ScoreType = score

        # Otherwise, log the score immediately
        # When in an active asyncio test environment (like pytest.mark.asyncio),
        # we need special handling to avoid "already running" errors
        try:
            loop = asyncio.get_running_loop()
            if asyncio.current_task() is None:
                # We're not in an async context, but a loop exists
                return loop.run_until_complete(self.alog_score(scorer, score_value))

            # We're in an async context, we need to handle this differently
            result = None
            exception = None

            def run_in_new_loop() -> None:
                nonlocal result, exception
                try:
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(
                            self.alog_score(scorer, score_value)
                        )
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception = e

            thread = Thread(target=run_in_new_loop)
            thread.start()
            thread.join()

            if exception:
                raise exception
            else:
                return result
        except RuntimeError:
            # No event loop exists, create one with asyncio.run
            return asyncio.run(self.alog_score(scorer, score_value))

    async def alog_score(
        self,
        scorer: Scorer | dict | str,
        score: ScoreType,
    ) -> None:
        if self._has_finished:
            raise ValueError("Cannot log score after finish has been called")

        scorer = self._prepare_scorer(scorer)

        @op(name=scorer.name, enable_code_capture=False)
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
                with attributes(IMPERATIVE_SCORE_MARKER):
                    await self.predict_call.apply_scorer(scorer)

        # this is always true because of how the scorer is created in the validator
        scorer_name = cast(str, scorer.name)
        self._captured_scores[scorer_name] = score

    @property
    def output(self) -> Any:
        """Get the current output value."""
        return self._predict_output

    @output.setter
    def output(self, value: Any) -> None:
        """Set the output value that will be used when finishing."""
        self._predict_output = value

    def __enter__(self) -> ScoreLogger:
        """Enter context manager and set call stack to predict_call."""
        self._call_stack_context = call_context.set_call_stack([self.predict_call])
        self._call_stack_context.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, restore call stack, and automatically finish."""
        try:
            if not self._has_finished:
                self.finish()
        finally:
            if self._call_stack_context is not None:
                self._call_stack_context.__exit__(exc_type, exc_val, exc_tb)


class EvaluationLogger:
    """This class provides an imperative interface for logging evaluations.

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
        self.name = name
        self.scorers = scorers
        self.eval_attributes = eval_attributes if eval_attributes is not None else {}

        # Convert model to Model instance if needed
        if model is None:
            model = Model()
        self.model: Model = _cast_to_cls(Model)(model)

        # Convert dataset to Dataset instance if needed
        if dataset is None:
            dataset = Dataset(rows=Table([{"dataset_id": _default_dataset_name()}]))
        self.dataset: Dataset = _cast_to_imperative_dataset(dataset)

        # Private state
        self._is_finalized: bool = False
        self._accumulated_predictions: list[ScoreLogger] = []

        # Register this instance in the global registry for atexit cleanup
        _active_evaluation_loggers.append(self)

        # At this point dataset has been processed and converted to a Dataset object
        self._pseudo_evaluation = Evaluation(
            dataset=self.dataset,
            scorers=[],
            metadata={"scorers": self.scorers, **self.eval_attributes},
        )

        # The following section is a "hacky" way to create Model and Evaluation
        # objects that "look right" to our object saving system.

        # --- Setup the model object ---
        # If the model doesn't have a predict method, create a placeholder
        try:
            assert isinstance(self.model, Model)
            self.model.get_infer_method()
        except MissingInferenceMethodError:

            @op(name="Model.predict", enable_code_capture=False)
            def predict(self: Model, inputs: dict) -> Any:
                # Get the output from the context variable
                return current_output.get()

            self.model.__dict__["predict"] = MethodType(predict, self.model)

        # Always create a context-aware predict method for use during log_prediction
        @op(name="Model.predict", enable_code_capture=False)  # type: ignore[no-redef]
        def predict(self: Model, inputs: dict) -> Any:
            # Get the output from the context variable
            return current_output.get()

        self._context_predict_method = MethodType(predict, self.model)

        # --- Setup the evaluation object ---
        @op(name="Evaluation.evaluate", enable_code_capture=False)
        def evaluate(self: Evaluation, model: Model) -> None: ...

        @op(name="Evaluation.predict_and_score", enable_code_capture=False)
        def predict_and_score(self: Evaluation, model: Model, example: dict) -> dict:
            predict_method = cast(Op, model.get_infer_method())
            with attributes(IMPERATIVE_EVAL_MARKER):
                output, predict_call = predict_method.call(
                    model, example, __require_explicit_finish=True
                )
                current_predict_call.set(predict_call)

            # This data is just a placeholder to give a sense of the data shape.
            # The actual output is explicitly replaced in ScoreLogger.finish.
            return {
                "output": output,
                "scores": {},
                "model_latency": None,
            }

        @op(name="Evaluation.summarize", enable_code_capture=False)
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
            attributes=self.attributes,
            use_stack=False,  # Don't push to global stack to prevent nesting
        )

    @property
    def ui_url(self) -> str | None:
        return self._evaluate_call.ui_url

    @property
    def attributes(self) -> dict[str, Any]:
        return self.eval_attributes | IMPERATIVE_EVAL_MARKER

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

    def _finalize_evaluation(
        self, output: Any = None, exception: BaseException | None = None
    ) -> None:
        """Handles the final steps of the evaluation: cleaning up predictions and finishing the main call."""
        if self._is_finalized:
            return

        self._cleanup_predictions()

        # Finish the evaluation call
        wc = require_weave_client()
        # Ensure the call is finished even if there was an error during summarize or elsewhere
        try:
            wc.finish_call(self._evaluate_call, output=output, exception=exception)
        except Exception:
            # Log error but continue cleanup
            logger.error(
                "Failed to finish evaluation call during finalization.", exc_info=True
            )

        self._is_finalized = True

    def log_prediction(self, inputs: dict[str, Any], output: Any = None) -> ScoreLogger:
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
        # Use set_call_stack to temporarily set the evaluation as the parent
        assert self._evaluate_call is not None

        # Temporarily swap the predict method to use our context-aware version
        # This ensures we use the passed output instead of calling the model
        original_method = self.model.__dict__.get("predict")
        self.model.__dict__["predict"] = self._context_predict_method

        try:
            with call_context.set_call_stack([self._evaluate_call]):
                # Make the prediction call
                with _set_current_output(output):
                    with attributes(IMPERATIVE_EVAL_MARKER):
                        _, predict_and_score_call = (
                            self._pseudo_evaluation.predict_and_score.call(
                                self._pseudo_evaluation,
                                self.model,
                                inputs,
                                __require_explicit_finish=True,
                            )
                        )
        finally:
            # Restore the original predict method
            if original_method is not None:
                self.model.__dict__["predict"] = original_method
            else:
                self.model.__dict__.pop("predict", None)

        # Get the predict_call from the context variable
        predict_call = current_predict_call.get()
        if predict_call is None:
            raise ValueError("predict_call should not be None")

        # Set the output on the predict_call now so it's available for apply_scorer
        predict_call.output = output

        pred = ScoreLogger(
            predict_and_score_call=predict_and_score_call,
            evaluate_call=self._evaluate_call,
            predict_call=predict_call,
            predefined_scorers=self.scorers,
        )
        # Store the output so we can use it when finishing the predict_call
        pred._predict_output = output
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

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """Log a summary dict to the Evaluation.

        This will calculate the summary, call the summarize op, and then finalize
        the evaluation, meaning no more predictions or scores can be logged.
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

        # Call the summarize op
        assert self._evaluate_call is not None, (
            "Evaluation call should exist for summary"
        )

        # Use set_call_stack to temporarily set the evaluation as the parent
        with call_context.set_call_stack([self._evaluate_call]):
            try:
                with _set_current_summary(final_summary):
                    with attributes(IMPERATIVE_EVAL_MARKER):
                        self._pseudo_evaluation.summarize()
            except Exception:
                logger.error("Error during execution of summarize op.", exc_info=True)
                # Even if summarize fails, try to finalize with the calculated summary

        self._finalize_evaluation(output=final_summary)

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
        if isinstance(content, str) and len(content) == 0:
            raise ValueError("Content cannot be an empty string")

        if not isinstance(name, str) or len(name) == 0:
            raise ValueError("`name` must be a non-empty string")

        wc = require_weave_client()

        set_call_view(
            call=self._evaluate_call,
            client=wc,
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
        if self._is_finalized:
            return

        # Finalize with None output, indicating closure without summary
        self._finalize_evaluation(output=None, exception=exception)

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
