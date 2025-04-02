from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MethodType
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, PrivateAttr

import weave
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.flow.scorer import Scorer
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.weave_client import Call

ID = str

NOT_DEFINED = "Not defined for custom scoring"

# Context variable to store the current output safely between threads.  This also
# ensures that only 1 version of the predict method is saved because the code
# contents are always the same.
current_output: ContextVar[Any] = ContextVar("current_output", default=None)
current_score: ContextVar[float | None] = ContextVar("current_score", default=None)
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
def set_current_score(score: float) -> Iterator[None]:
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


class BetaScoreLogger(BaseModel):
    prediction_id: ID
    score: float
    metadata: dict | None


class BetaPredictionLogger(BaseModel):
    model_id: ID
    inputs: dict
    output: Any
    hack_reference_to_predict_and_score: Call
    hack_reference_to_evaluate: Call

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def log_score(
        self, scorer_name: str, score: float, metadata: dict | None = None
    ) -> BetaScoreLogger:
        # Define the scorer class dynamically
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
            [self.hack_reference_to_evaluate, self.hack_reference_to_predict_and_score]
        ):
            await self.hack_reference_to_predict_and_score.apply_scorer(scorer_instance)

        return BetaScoreLogger(prediction_id="123", score=score, metadata=metadata)


class BetaEvaluationLogger(BaseModel):
    model_id: ID = ""
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

    def log_prediction(self, inputs: dict, output: Any) -> BetaPredictionLogger:
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
                return current_summary.get()

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
        return BetaPredictionLogger(
            model_id="123",
            inputs=inputs,
            output=model_output,
            hack_reference_to_predict_and_score=predict_and_score_call,
            hack_reference_to_evaluate=self._evaluate_call,
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
