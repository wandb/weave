from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MethodType
from typing import Any, Union, cast

from pydantic import BaseModel, ConfigDict, PrivateAttr

import weave
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.weave_client import Call

ID = str
ScoreType = Union[float, bool, dict]

NOT_DEFINED = "Not defined for custom scoring"

# Context variable to store the current output safely between threads.  This also
# ensures that only 1 version of the predict method is saved because the code
# contents are always the same.
current_output: ContextVar[Any] = ContextVar("current_output", default=None)
current_score: ContextVar[ScoreType | None] = ContextVar("current_score", default=None)
current_summary: ContextVar[dict | None] = ContextVar("current_summary", default=None)


@contextmanager
def set_current_output(output: Any) -> Iterator[None]:
    """Set the current output in a thread-safe way using context variables."""
    token = current_output.set(output)
    try:
        yield
    finally:
        current_output.reset(token)


@contextmanager
def set_current_score(score: ScoreType) -> Iterator[None]:
    token = current_score.set(score)
    try:
        yield
    finally:
        current_score.reset(token)


@contextmanager
def set_current_summary(summary: dict) -> Iterator[None]:
    token = current_summary.set(summary)
    try:
        yield
    finally:
        current_summary.reset(token)


def validate_scorer_name(name: str) -> None:
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


class ImperativeScoreLogger(BaseModel):
    """This class provides an imperative interface for logging scores.

    Note that logging scores is async!
    """

    # model_id: ID
    inputs: dict
    output: Any
    predict_and_score_call: Call
    evaluate_call: Call

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def log_score(
        self,
        scorer_name: str,
        score: ScoreType,
        metadata: dict | None = None,
    ) -> None:
        # Define the scorer class dynamically
        validate_scorer_name(scorer_name)
        cls_name = scorer_name.replace(".", "_")
        DynamicScorer = type(cls_name, (Scorer,), {})
        scorer_instance = DynamicScorer()

        @weave.op(name=scorer_name)
        def score_method(self: Scorer, *, output: Any, **inputs: Any) -> float:
            # return score
            # TODO: can't use score here because it will cause version mismatc
            return cast(float, current_score.get())

        scorer_instance.__dict__["score"] = MethodType(score_method, scorer_instance)

        # attach the score feedback to the predict call
        with call_context.set_call_stack(
            [self.evaluate_call, self.predict_and_score_call]
        ):
            with set_current_score(score):
                await self.predict_and_score_call.apply_scorer(scorer_instance)


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
        await pred.log_score(scorer_name, score)
        ev.log_summary(summary)
        ```
    """

    _eval_started: bool = PrivateAttr(False)
    _logged_summary: bool = PrivateAttr(False)
    _evaluate_call: Call | None = PrivateAttr(None)
    _pseudo_model: Model = PrivateAttr(default_factory=lambda: Model())
    _pseudo_evaluation: Evaluation = PrivateAttr(
        default_factory=lambda: Evaluation(
            dataset=weave.Dataset(rows=weave.Table([{"": ""}])),
            scorers=[],
        )
    )
    _starting_stack: list[Call] = PrivateAttr(default_factory=list)

    def log_prediction(self, inputs: dict, output: Any) -> ImperativeScoreLogger:
        if not self._eval_started:
            self._eval_started = True

            # The following section is a "hacky" way to create Model and Evaluation
            # objects that "look right" to our object saving system.

            # --- Setup the model object ---
            @weave.op
            def predict(self: Model, inputs: dict) -> Any:
                # Get the output from the context variable
                return current_output.get()

            self._pseudo_model.__dict__["predict"] = MethodType(
                predict, self._pseudo_model
            )

            # --- Setup the evaluation object ---
            @weave.op(name="Evaluation.evaluate")
            def evaluate(self: Evaluation, model: Model) -> None: ...

            @weave.op
            def predict_and_score(self: Evaluation, model: Model, inputs: dict) -> dict:
                model_output = model.get_infer_method()(inputs)
                return {
                    "model_output": model_output,
                    "scores": NOT_DEFINED,
                    "model_latency": NOT_DEFINED,
                }

            @weave.op
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

            self._starting_stack = call_context.get_call_stack()

            # Create the evaluation call
            wc = require_weave_client()
            self._evaluate_call = wc.create_call(
                display_name=default_evaluation_display_name,
                op=self._pseudo_evaluation.evaluate,
                inputs={
                    "self": self._pseudo_evaluation,
                    "model": self._pseudo_model,
                },
            )
            assert self._evaluate_call is not None
            call_context.push_call(self._evaluate_call)

        # Make the prediction call
        with set_current_output(output):
            _, predict_and_score_call = self._pseudo_evaluation.predict_and_score.call(
                self._pseudo_evaluation, self._pseudo_model, inputs
            )

        # Get the model output from the call result
        model_output = predict_and_score_call.output.get("model_output")

        assert self._evaluate_call is not None
        return ImperativeScoreLogger(
            inputs=inputs,
            output=model_output,
            predict_and_score_call=predict_and_score_call,
            evaluate_call=self._evaluate_call,
        )

    def log_summary(self, summary: dict) -> None:
        if self._logged_summary:
            return
        self._logged_summary = True
        # Call the summarize method with the proper context
        assert self._evaluate_call is not None
        with call_context.set_call_stack([self._evaluate_call]):
            with set_current_summary(summary):
                self._pseudo_evaluation.summarize()

        # Finish the evaluation call
        wc = require_weave_client()
        wc.finish_call(self._evaluate_call, output=summary)
