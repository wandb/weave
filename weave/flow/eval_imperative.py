"""
Imperative evaluation logging for Weave.

This module provides an imperative interface for logging evaluations, predictions,
and scores in Weave. Instead of using the declarative evaluation API, users can
manually log predictions and scores as they run evaluations.

The main classes are:
- EvaluationLogger: For logging complete evaluations with predictions and scores
- ScoreLogger: For logging individual prediction scores

Example:
    Basic usage with EvaluationLogger:

    ```python
    import weave
    from weave.flow.eval_imperative import EvaluationLogger

    # Initialize the evaluation logger
    eval_logger = EvaluationLogger(
        name="my_evaluation",
        model="my_model",
        dataset=[
            {"input": "Hello", "expected": "Hi"},
            {"input": "Goodbye", "expected": "Bye"}
        ]
    )

    # Log predictions and scores
    for example in dataset:
        output = my_model.predict(example["input"])
        score_logger = eval_logger.log_prediction(example, output)

        # Log scores for this prediction
        accuracy_score = calculate_accuracy(output, example["expected"])
        score_logger.log_score("accuracy", accuracy_score)

    # Finalize the evaluation
    eval_logger.log_summary({"total_examples": len(dataset)})
    ```
"""

from __future__ import annotations

import atexit
import datetime
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from multiprocessing import Lock
from types import MethodType
from typing import Annotated, Any, TypeVar, Union, cast

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
)

import weave
from weave.flow.dataset import Dataset
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.flow.scorer import auto_summarize as auto_summarize_fn
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


def _cleanup_all_evaluations() -> None:
    """
    Clean up all active evaluation loggers on program exit.

    This function is registered with atexit to ensure that all active
    EvaluationLogger instances are properly finalized when the program
    terminates, preventing resource leaks.

    Examples:
        This function is automatically called on program exit:

        ```python
        # When the program exits, all active evaluations are cleaned up
        # No manual intervention required
        ```
    """
    for eval_logger in _active_evaluation_loggers:
        _cleanup_evaluation(eval_logger)


def _cleanup_evaluation(eval_logger: EvaluationLogger) -> None:
    """
    Clean up a single evaluation logger instance.

    Args:
        eval_logger (EvaluationLogger): The evaluation logger to clean up.

    Examples:
        ```python
        eval_logger = EvaluationLogger()
        # ... use the logger ...
        _cleanup_evaluation(eval_logger)  # Manual cleanup
        ```
    """
    try:
        if not eval_logger._is_finalized:
            eval_logger.finish()
    except Exception:
        logger.error("Error during cleanup of EvaluationLogger", exc_info=True)


# Register cleanup handler for program exit
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
    """
    Set the current output in a thread-safe way using context variables.

    This context manager temporarily sets the current output value for use
    in imperative evaluation logging, ensuring thread safety.

    Args:
        output (Any): The output value to set in the current context.

    Yields:
        None: Context manager yields control to the caller.

    Examples:
        ```python
        with _set_current_output("hello world"):
            # Within this context, current_output.get() returns "hello world"
            result = current_output.get()
            assert result == "hello world"
        ```
    """
    token = current_output.set(output)
    try:
        yield
    finally:
        current_output.reset(token)


@contextmanager
def _set_current_score(score: ScoreType) -> Iterator[None]:
    """
    Set the current score in a thread-safe way using context variables.

    Args:
        score (ScoreType): The score value to set in the current context.

    Yields:
        None: Context manager yields control to the caller.

    Examples:
        ```python
        with _set_current_score(0.85):
            # Within this context, current_score.get() returns 0.85
            result = current_score.get()
            assert result == 0.85
        ```
    """
    token = current_score.set(score)
    try:
        yield
    finally:
        current_score.reset(token)


@contextmanager
def _set_current_summary(summary: dict) -> Iterator[None]:
    """
    Set the current summary in a thread-safe way using context variables.

    Args:
        summary (dict): The summary dictionary to set in the current context.

    Yields:
        None: Context manager yields control to the caller.

    Examples:
        ```python
        summary_data = {"accuracy": 0.85, "count": 100}
        with _set_current_summary(summary_data):
            # Within this context, current_summary.get() returns summary_data
            result = current_summary.get()
            assert result == summary_data
        ```
    """
    token = current_summary.set(summary)
    try:
        yield
    finally:
        current_summary.reset(token)


def _cast_to_cls(type_: type[T]) -> Callable[[str | dict | T], T]:
    """
    Create a casting function that converts various inputs to a specific class type.

    This function returns a casting function that can convert strings, dictionaries,
    or existing instances to the specified class type. It's used for flexible
    input handling in evaluation logging.

    Args:
        type_ (type[T]): The target class type to cast to.

    Returns:
        Callable[[str | dict | T], T]: A function that performs the casting.

    Raises:
        ValueError: If string name is invalid or dict is missing 'name' key.
        TypeError: If the input type is not supported for casting.

    Examples:
        ```python
        from weave.flow.model import Model

        # Create a casting function for Model
        cast_to_model = _cast_to_cls(Model)

        # Cast from string
        model1 = cast_to_model("MyModel")

        # Cast from dict
        model2 = cast_to_model({"name": "MyModel", "version": "1.0"})

        # Cast from existing instance
        existing_model = Model(name="ExistingModel")
        model3 = cast_to_model(existing_model)
        ```
    """

    def _convert_to_cls_inner(value: str | dict | T) -> T:
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
    """
    Convert various input types to a Dataset object for imperative evaluation.

    This function provides flexible input handling for datasets in imperative
    evaluation logging, accepting strings, lists of dictionaries, or existing
    Dataset objects.

    Args:
        value (Dataset | list[dict] | str): The input to convert to a Dataset.
            - str: Creates a Dataset with a single row containing the string as dataset_id
            - list[dict]: Creates a Dataset with the provided rows
            - Dataset: Returns the Dataset unchanged

    Returns:
        Dataset: A Dataset object ready for use in imperative evaluation.

    Raises:
        TypeError: If the input type is not supported.

    Examples:
        ```python
        # From string identifier
        dataset1 = _cast_to_imperative_dataset("my_dataset_id")

        # From list of dictionaries
        rows = [
            {"input": "Hello", "expected": "Hi"},
            {"input": "Goodbye", "expected": "Bye"}
        ]
        dataset2 = _cast_to_imperative_dataset(rows)

        # From existing Dataset
        existing = Dataset(rows=weave.Table([{"a": 1}]))
        dataset3 = _cast_to_imperative_dataset(existing)
        ```
    """
    if isinstance(value, str):
        return Dataset(name=value, rows=weave.Table([{"dataset_id": value}]))
    elif isinstance(value, list):
        return Dataset(rows=weave.Table(value))
    elif isinstance(value, Dataset):
        return value
    else:
        raise TypeError("Unsupported type for casting")


def _default_dataset_name() -> str:
    """
    Generate a default dataset name with current date and unique identifier.

    Creates a memorable dataset name using the current date and a randomly
    generated memorable name component.

    Returns:
        str: A default dataset name in format "YYYY-MM-DD-{memorable_name}-dataset".

    Examples:
        ```python
        name = _default_dataset_name()
        # Returns something like: "2024-01-15-brave-elephant-dataset"

        assert "dataset" in name
        assert len(name.split("-")) >= 4  # date + memorable name + "dataset"
        ```
    """
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


def _validate_class_name(name: str) -> str:
    """
    Validate and return a class name following Python naming conventions.

    Ensures the provided name is a valid Python class identifier that follows
    Python naming conventions and is not a reserved keyword.

    Args:
        name (str): The class name to validate.

    Returns:
        str: The validated class name (unchanged if valid).

    Raises:
        ValueError: If the name is empty, contains invalid characters, or is a Python keyword.

    Examples:
        ```python
        # Valid names
        valid_name = _validate_class_name("MyScorer")
        assert valid_name == "MyScorer"

        # This would raise ValueError
        try:
            _validate_class_name("class")  # Python keyword
        except ValueError as e:
            print(f"Invalid name: {e}")

        try:
            _validate_class_name("123Invalid")  # Starts with number
        except ValueError as e:
            print(f"Invalid name: {e}")
        ```
    """
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


class ScorerCache:
    """
    Thread-safe cache for scorer instances to avoid redundant object creation.

    This cache stores scorer instances by their unique ID to prevent creating
    duplicate scorer objects during evaluation logging. It uses a simple LRU
    eviction policy when the cache reaches its maximum size.

    Attributes:
        _cached_scorers (dict[str, Scorer]): Dictionary mapping scorer IDs to instances.
        _cached_scorers_lock (Any): Lock for thread-safe access to the cache.
        _max_size (int): Maximum number of scorers to cache.

    Examples:
        ```python
        from weave.flow.scorer import Scorer

        # Create a cache with custom size
        cache = ScorerCache(max_size=500)

        # Get or create a scorer
        def create_scorer():
            return Scorer(name="accuracy")

        scorer = cache.get_scorer("accuracy_v1", create_scorer)

        # Subsequent calls return the cached instance
        same_scorer = cache.get_scorer("accuracy_v1", create_scorer)
        assert scorer is same_scorer
        ```
    """

    _cached_scorers: dict[str, Scorer]
    _cached_scorers_lock: Any
    _max_size: int

    def __init__(self, max_size: int = 1000) -> None:
        """
        Initialize the scorer cache.

        Args:
            max_size (int, optional): Maximum number of scorers to cache.
                Defaults to 1000.

        Examples:
            ```python
            # Default cache size
            cache1 = ScorerCache()

            # Custom cache size
            cache2 = ScorerCache(max_size=500)
            ```
        """
        self._cached_scorers = {}
        self._cached_scorers_lock = Lock()
        self._max_size = max_size

    def get_scorer(
        self, scorer_id: str, default_factory: Callable[[], Scorer]
    ) -> Scorer:
        """
        Get a scorer from the cache or create it using the factory function.

        If the scorer is not in the cache, it will be created using the provided
        factory function and added to the cache. If the cache is full, the oldest
        entry will be evicted.

        Args:
            scorer_id (str): Unique identifier for the scorer.
            default_factory (Callable[[], Scorer]): Function to create the scorer
                if it's not in the cache.

        Returns:
            Scorer: The cached or newly created scorer instance.

        Examples:
            ```python
            cache = ScorerCache()

            # Define a factory function
            def create_accuracy_scorer():
                return Scorer(name="accuracy")

            # Get scorer (will be created and cached)
            scorer1 = cache.get_scorer("acc_v1", create_accuracy_scorer)

            # Get same scorer (will return cached instance)
            scorer2 = cache.get_scorer("acc_v1", create_accuracy_scorer)
            assert scorer1 is scorer2
            ```
        """
        with self._cached_scorers_lock:
            if scorer_id not in self._cached_scorers:
                if len(self._cached_scorers) >= self._max_size:
                    self._cached_scorers.popitem()
                self._cached_scorers[scorer_id] = default_factory()
        return self._cached_scorers[scorer_id]


global_scorer_cache = ScorerCache()


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
        """
        Finalize the score logging for this prediction.

        This method should be called when all scores for a prediction have been
        logged. It consolidates the captured scores and finishes the associated
        predict_and_score call in Weave.

        Note:
            This method is idempotent - calling it multiple times will have no effect
            after the first call.

        Examples:
            ```python
            eval_logger = EvaluationLogger()
            score_logger = eval_logger.log_prediction({"input": "test"}, "output")

            # Log some scores
            score_logger.log_score("accuracy", 0.95)
            score_logger.log_score("precision", 0.87)

            # Finalize the score logging
            score_logger.finish()

            # Subsequent calls are no-ops
            score_logger.finish()  # No effect
            ```
        """
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
        """
        Log a score synchronously for this prediction.

        This method handles asyncio environments automatically and provides a
        synchronous interface for logging scores.

        Args:
            scorer (Scorer | dict | str): The scorer to use. Can be:
                - Scorer instance: Used directly
                - dict: Must contain 'name' key, creates a Scorer with those attributes
                - str: Creates a Scorer with the string as the name
            score (ScoreType): The score value (float, bool, or dict).

        Raises:
            ValueError: If called after finish() has been called.

        Examples:
            ```python
            score_logger = eval_logger.log_prediction({"input": "test"}, "output")

            # Log score with string scorer name
            score_logger.log_score("accuracy", 0.95)

            # Log score with dict scorer
            score_logger.log_score({"name": "precision", "version": "1.0"}, 0.87)

            # Log score with Scorer instance
            from weave.flow.scorer import Scorer
            custom_scorer = Scorer(name="custom_metric")
            score_logger.log_score(custom_scorer, {"f1": 0.91, "support": 100})
            ```
        """
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

    async def alog_score(
        self,
        scorer: Annotated[
            Scorer | dict | str,
            Field(
                description="A metadata-only scorer used for comparisons."
                "Alternatively, you can pass a dict of attributes or just a string"
                "representing the ID of your scorer."
            ),
        ],
        score: ScoreType,
    ) -> None:
        """
        Log a score asynchronously for this prediction.

        This is the async version of log_score. It creates a scorer operation
        and applies it to the prediction call, storing the score for later
        consolidation.

        Args:
            scorer (Scorer | dict | str): The scorer to use. Can be:
                - Scorer instance: Used directly
                - dict: Must contain 'name' key, creates a Scorer with those attributes
                - str: Creates a Scorer with the string as the name
            score (ScoreType): The score value (float, bool, or dict).

        Raises:
            ValueError: If called after finish() has been called.

        Examples:
            ```python
            import asyncio

            async def log_scores():
                score_logger = eval_logger.log_prediction({"input": "test"}, "output")

                # Log scores asynchronously
                await score_logger.alog_score("accuracy", 0.95)
                await score_logger.alog_score("precision", 0.87)

                score_logger.finish()

            # Run the async function
            asyncio.run(log_scores())
            ```
        """
        if not isinstance(scorer, Scorer):
            scorer_id = json.dumps(scorer)
            scorer = global_scorer_cache.get_scorer(
                scorer_id, lambda: _cast_to_cls(Scorer)(scorer)
            )
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
        """
        Initialize the pseudo evaluation after model validation.

        This method is called automatically by Pydantic after the model is created
        and all field validation has completed. It sets up the internal evaluation
        structure and creates the necessary Weave operations.

        Args:
            __context (Any): Pydantic validation context (unused).

        Note:
            This is an internal method called by Pydantic and should not be
            called directly by users.
        """
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
        """
        Clean up any unfinished prediction loggers.

        This method iterates through all accumulated ScoreLogger instances
        and ensures they are properly finished. It's called during evaluation
        finalization to prevent resource leaks.

        Note:
            This is an internal cleanup method. Prediction cleanup happens
            automatically during evaluation finalization.
        """
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
        """
        Handle the final steps of evaluation: cleanup and call finishing.

        This method performs the critical finalization steps including cleaning
        up prediction loggers, finishing the evaluation call, and removing the
        call from the context stack.

        Args:
            output (Any, optional): The output to finish the evaluation call with.
                Typically contains summary data. Defaults to None.

        Note:
            This is an internal finalization method. It's automatically called
            by log_summary() and finish() methods.
        """
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
        """
        Log a prediction to the evaluation and return a reference for scoring.

        This method records a prediction made by the model and returns a ScoreLogger
        that can be used to attach scores to this specific prediction.

        Args:
            inputs (dict): The input data that was provided to the model.
            output (Any): The output produced by the model for these inputs.

        Returns:
            ScoreLogger: A logger instance for recording scores for this prediction.

        Examples:
            ```python
            eval_logger = EvaluationLogger(
                name="text_classification",
                model="my_classifier"
            )

            # Log a prediction
            inputs = {"text": "This movie is great!"}
            output = {"label": "positive", "confidence": 0.95}
            score_logger = eval_logger.log_prediction(inputs, output)

            # Use the score logger to record scores
            score_logger.log_score("accuracy", 1.0)
            score_logger.log_score("confidence", 0.95)

            # Log another prediction
            inputs2 = {"text": "This movie is terrible!"}
            output2 = {"label": "negative", "confidence": 0.87}
            score_logger2 = eval_logger.log_prediction(inputs2, output2)
            score_logger2.log_score("accuracy", 1.0)

            # Finalize the evaluation
            eval_logger.log_summary()
            ```
        """
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

    def log_summary(
        self,
        summary: dict | None = None,
        auto_summarize: bool = True,
    ) -> None:
        """
        Log a summary dict to the evaluation and finalize it.

        This method calculates summary statistics from the logged scores, optionally
        merges them with a provided summary dictionary, and finalizes the evaluation.
        After calling this method, no more predictions or scores can be logged.

        Args:
            summary (dict | None, optional): Additional summary data to include.
                This will be merged with auto-generated summary statistics.
                Defaults to None.
            auto_summarize (bool, optional): Whether to automatically calculate
                summary statistics from the logged scores. Defaults to True.

        Note:
            This method finalizes the evaluation. After calling it, the evaluation
            is considered complete and no further logging is possible.

        Examples:
            ```python
            eval_logger = EvaluationLogger()

            # Log some predictions with scores
            for i, (inputs, expected) in enumerate(test_data):
                output = model.predict(inputs)
                score_logger = eval_logger.log_prediction(inputs, output)

                accuracy = 1.0 if output == expected else 0.0
                score_logger.log_score("accuracy", accuracy)

            # Finalize with auto-summary only
            eval_logger.log_summary()

            # OR finalize with custom summary data
            custom_summary = {
                "model_version": "1.2.3",
                "test_set_size": len(test_data),
                "evaluation_date": "2024-01-15"
            }
            eval_logger.log_summary(summary=custom_summary)

            # OR disable auto-summary and provide only custom data
            eval_logger.log_summary(
                summary={"custom_metric": 42},
                auto_summarize=False
            )
            ```
        """
        if self._is_finalized:
            logger.warn("(NO-OP): Evaluation already finalized, cannot log summary.")
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
        """
        Clean up the evaluation resources explicitly without logging a summary.

        This method finalizes the evaluation without calculating or logging a summary.
        It ensures all prediction calls and the main evaluation call are properly
        finished and cleaned up. Use this when you want to abort an evaluation
        or when you don't need summary statistics.

        Note:
            This method is automatically called during garbage collection and
            program exit, but it's recommended to call it explicitly for
            deterministic cleanup.

        Examples:
            ```python
            eval_logger = EvaluationLogger()

            try:
                # Log some predictions
                for inputs, output in predictions:
                    score_logger = eval_logger.log_prediction(inputs, output)
                    score_logger.log_score("accuracy", calculate_accuracy(output))

                # Normal completion with summary
                eval_logger.log_summary()

            except Exception as e:
                print(f"Error during evaluation: {e}")
                # Clean up without summary due to error
                eval_logger.finish()

            # Alternative: Use as context manager (not implemented yet)
            # with EvaluationLogger() as eval_logger:
            #     # ... log predictions ...
            #     # finish() called automatically
            ```
        """
        if self._is_finalized:
            return

        # Finalize with None output, indicating closure without summary
        self._finalize_evaluation(output=None)

        # Remove from global registry since we've manually finalized
        if self in _active_evaluation_loggers:
            _active_evaluation_loggers.remove(self)

    def __del__(self) -> None:
        """
        Ensure cleanup happens during garbage collection.

        This method is called when the EvaluationLogger instance is being
        garbage collected. It ensures that any remaining resources are
        properly cleaned up even if finish() or log_summary() were not
        called explicitly.

        Note:
            While this provides a safety net, it's recommended to explicitly
            call finish() or log_summary() for deterministic cleanup timing.
        """
        _cleanup_evaluation(self)


class ImperativeEvaluationLogger(EvaluationLogger):
    """
    Legacy class name for EvaluationLogger.

    This class is maintained for backward compatibility with existing code
    that may use the old class name. All functionality is identical to
    EvaluationLogger.

    Warning:
        This class is deprecated and will be removed in a future version.
        Please use EvaluationLogger instead.

    Examples:
        ```python
        # Old usage (deprecated)
        from weave.flow.eval_imperative import ImperativeEvaluationLogger
        eval_logger = ImperativeEvaluationLogger()

        # New usage (recommended)
        from weave.flow.eval_imperative import EvaluationLogger
        eval_logger = EvaluationLogger()
        ```

    See Also:
        EvaluationLogger: The current class to use for imperative evaluation logging.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the legacy evaluation logger.

        Issues a deprecation warning and delegates to the parent EvaluationLogger.

        Args:
            *args: Positional arguments passed to EvaluationLogger.
            **kwargs: Keyword arguments passed to EvaluationLogger.

        Examples:
            ```python
            # This will show a deprecation warning
            eval_logger = ImperativeEvaluationLogger(
                name="my_eval",
                model="my_model"
            )
            ```
        """
        logger.warning(
            "ImperativeEvaluationLogger was renamed to EvaluationLogger in 0.51.44"
            "Please use EvaluationLogger instead.  ImperativeEvaluationLogger will"
            "be removed in a future version."
        )
        super().__init__(*args, **kwargs)
