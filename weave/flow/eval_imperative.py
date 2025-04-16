from __future__ import annotations

import asyncio
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
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op
from weave.trace.weave_client import Call

T = TypeVar("T")
ID = str
ScoreType = Union[float, bool, dict]

logger = logging.getLogger(__name__)

# Context variable to store the current output safely between threads.  This also
# ensures that only 1 version of the predict method is saved because the code
# contents are always the same.
current_output: ContextVar[Any] = ContextVar("current_output", default=None)
current_score: ContextVar[ScoreType | None] = ContextVar("current_score", default=None)
current_summary: ContextVar[dict | None] = ContextVar("current_summary", default=None)
current_predict_call: ContextVar[Call | None] = ContextVar(
    "current_predict_call", default=None
)


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


@contextmanager
def _set_current_predict_call(call: Call) -> Iterator[None]:
    """Set the current predict call in a thread-safe way using context variables."""
    token = current_predict_call.set(call)
    try:
        yield
    finally:
        current_predict_call.reset(token)


def _cast_to_cls(type_: type[T]) -> Callable[[str | T], T]:
    def _convert_to_cls_inner(value: str | T) -> T:
        if isinstance(value, str):
            cls_name = value

            # Dynamically create the class if the user only provides a name
            cls_name = _validate_class_name(cls_name)
            cls = type(cls_name, (type_,), {})
            return cast(T, cls())

        elif isinstance(value, dict):
            attributes = value

            # Dynamically create the class with attributes from the dict)
            pydantic_config_dict = {
                "__annotations__": dict.fromkeys(attributes, Any),
                **attributes,
            }
            cls_name = f"Dynamic{type_.__name__}"
            cls = type(cls_name, (type_,), pydantic_config_dict)
            return cast(T, cls())

        elif isinstance(value, type_):
            return value

        raise TypeError("Unsupported type for casting")

    return _convert_to_cls_inner


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


class ImperativeScoreLogger(BaseModel):
    """This class provides an imperative interface for logging scores."""

    # model_id: ID
    inputs: dict
    output: Any
    predict_and_score_call: Call
    evaluate_call: Call
    predict_call: Call

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def log_score(self, scorer: Scorer | str, score: ScoreType) -> None:
        """Log a score synchronously by calling the async method.

        This is a convenience method for when you don't want to use async/await.
        If called from within an existing event loop, use _alog_score instead.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # If there is no running loop, run the method synchronously
            asyncio.run(self._alog_score(scorer, score))
        else:
            # If there is a running loop, run the method asynchronously
            loop.create_task(self._alog_score(scorer, score))

    @validate_call
    async def _alog_score(
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
        # this is safe; pydantic casting is done in validator above
        scorer = cast(Scorer, scorer)

        @weave.op(name=scorer.name)
        def score_method(self: Scorer, *, output: Any, **inputs: Any) -> ScoreType:
            # TODO: can't use score here because it will cause version mismatch
            # return score
            return cast(ScoreType, current_score.get())

        scorer.__dict__["score"] = MethodType(score_method, scorer)

        # attach the score feedback to the predict call
        with call_context.set_call_stack(
            [self.evaluate_call, self.predict_and_score_call]
        ):
            with _set_current_score(score):
                await self.predict_call.apply_scorer(scorer)


class ImperativeEvaluationLogger(BaseModel):
    """This class provides an imperative interface for logging evaluations.

    An evaluation is started automatically when the first prediction is logged
    using the `log_prediction` method, and finished when the `log_summary` method
    is called.

    Each time you log a prediction, you will get back an `ImperativePredictionLogger`
    object.  You can use this object to log scores and metadata for that specific
    prediction (see that class for more details).

    Example:
        ```python
        ev = ImperativeEvaluationLogger()
        pred = ev.log_prediction(inputs, output)
        pred.log_score(scorer_name, score)
        ev.log_summary(summary)
        ```
    """

    model: Annotated[
        Model | dict | str,
        BeforeValidator(_cast_to_cls(Model)),
        Field(
            default_factory=Model,
            description="A metadata-only Model used for comparisons."
            "Alternatively, you can pass a dict of attributes or just a string"
            "representing the ID of your model.",
        ),
    ]

    _eval_started: bool = PrivateAttr(False)
    _logged_summary: bool = PrivateAttr(False)
    _evaluate_call: Call | None = PrivateAttr(None)
    _pseudo_evaluation: Evaluation = PrivateAttr(
        default_factory=lambda: Evaluation(
            dataset=weave.Dataset(rows=weave.Table([{"": ""}])),
            scorers=[],
        )
    )

    def log_prediction(self, inputs: dict, output: Any) -> ImperativeScoreLogger:
        # similar to how we dynamically create the scorer class, we will
        # dynamically create the model class

        if not self._eval_started:
            self._eval_started = True

            # The following section is a "hacky" way to create Model and Evaluation
            # objects that "look right" to our object saving system.

            # --- Setup the model object ---
            @weave.op(name="Model.predict")
            def predict(self: Model, inputs: dict) -> Any:
                # Get the output from the context variable
                return current_output.get()

            self.model.__dict__["predict"] = MethodType(predict, self.model)

            # --- Setup the evaluation object ---
            @weave.op(name="Evaluation.evaluate")
            def evaluate(self: Evaluation, model: Model) -> None: ...

            @weave.op(name="Evaluation.predict_and_score")
            def predict_and_score(
                self: Evaluation, model: Model, example: dict
            ) -> dict:
                predict_method = cast(Op, model.get_infer_method())
                model_output, predict_call = predict_method.call(model, example)
                current_predict_call.set(predict_call)
                return {
                    "model_output": model_output,
                    "scores": {},
                    "model_latency": None,
                }

            @weave.op(name="Evaluation.summarize")
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
                display_name=default_evaluation_display_name,
                op=self._pseudo_evaluation.evaluate,
                inputs={
                    "self": self._pseudo_evaluation,
                    "model": self.model,
                },
            )
            assert self._evaluate_call is not None
            call_context.push_call(self._evaluate_call)

        # Make the prediction call
        with _set_current_output(output):
            _, predict_and_score_call = self._pseudo_evaluation.predict_and_score.call(
                self._pseudo_evaluation, self.model, inputs
            )

        # Get the model output from the call result
        model_output = predict_and_score_call.output.get("model_output")

        # Get the predict_call from the context variable
        predict_call = current_predict_call.get()
        if predict_call is None:
            raise ValueError("predict_call should not be None")

        assert self._evaluate_call is not None
        return ImperativeScoreLogger(
            inputs=inputs,
            output=model_output,
            predict_and_score_call=predict_and_score_call,
            evaluate_call=self._evaluate_call,
            predict_call=predict_call,
        )

    def log_summary(self, summary: dict) -> None:
        if self._logged_summary:
            logger.warn("(NO-OP): Already called summary, returning.")
            return
        self._logged_summary = True
        # Call the summarize method with the proper context
        assert self._evaluate_call is not None
        with call_context.set_call_stack([self._evaluate_call]):
            with _set_current_summary(summary):
                self._pseudo_evaluation.summarize()

        # Finish the evaluation call
        wc = require_weave_client()
        wc.finish_call(self._evaluate_call, output=summary)
