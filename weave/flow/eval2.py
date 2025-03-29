from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MethodType
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr

import weave
from weave.flow.eval import Evaluation, default_evaluation_display_name
from weave.flow.model import Model
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.weave_client import Call

ID = str

NOT_DEFINED = "Not defined for custom scoring"

# Context variable to store the current output safely between threads
current_output: ContextVar[Any] = ContextVar("current_output", default=None)


@contextmanager
def set_current_output(output: Any) -> Iterator[None]:
    """Set the current output in a thread-safe way using context variables."""
    token = current_output.set(output)
    try:
        yield
    finally:
        current_output.reset(token)


class ScoreLogger(BaseModel):
    prediction_id: ID
    score: float
    metadata: dict | None


class PredictionLogger(BaseModel):
    model_id: ID
    inputs: dict
    output: Any
    hack_reference_to_predict_and_score: Call
    hack_reference_to_evaluate: Call

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def log_score(
        self, scorer_name: str, score: float, metadata: dict | None = None
    ) -> ScoreLogger:
        @weave.op(name=scorer_name)
        def scorer(model_output: Any, **inputs: Any) -> float:
            return score

        # attach the score feedback to the predict call
        with call_context.set_call_stack(
            [self.hack_reference_to_evaluate, self.hack_reference_to_predict_and_score]
        ):
            await self.hack_reference_to_predict_and_score.apply_scorer(scorer)

        return ScoreLogger(prediction_id="123", score=score, metadata=metadata)


class EvaluationLogger(BaseModel):
    model_id: ID = ""
    _eval_started: bool = PrivateAttr(False)
    _logged_summary: bool = PrivateAttr(False)
    _evaluate_call: Call | None = PrivateAttr(None)
    _pseudo_model: Model = PrivateAttr(default_factory=Model)
    _pseudo_evaluation: Evaluation = PrivateAttr(
        default_factory=lambda: Evaluation(
            dataset=weave.Dataset(rows=[{"THIS_IS_A_DUMMY": "IGNORE"}])
        )
    )

    def log_prediction(self, inputs: dict, output: Any) -> PredictionLogger:
        if not self._eval_started:
            self._eval_started = True

            # --- Setup the model with predict method ---
            @weave.op
            def predict(self: Model, inputs: dict) -> Any:
                # Get the output from the context variable
                return current_output.get()

            # Hacks: Put custom predict and predict_and_score methods back on the model
            self._pseudo_model.__dict__["predict"] = MethodType(
                predict, self._pseudo_model
            )

            # --- Setup the evaluation object ---
            @weave.op(name="Evaluation.evaluate")
            def evaluate(self: Evaluation, model: Model) -> None: ...

            @weave.op
            def predict_and_score(self: Evaluation, model: Model, inputs: dict) -> dict:
                model_output = model.predict(inputs)
                return {
                    "model_output": model_output,
                    "scores": NOT_DEFINED,
                    "model_latency": NOT_DEFINED,
                }

            @weave.op
            def summarize(self: Evaluation) -> dict:
                # Placeholder - will be replaced in log_summary
                return {}

            # Attach methods to evaluation
            self._pseudo_evaluation.__dict__["evaluate"] = MethodType(
                evaluate, self._pseudo_evaluation
            )
            self._pseudo_evaluation.__dict__["predict_and_score"] = MethodType(
                predict_and_score, self._pseudo_evaluation
            )
            self._pseudo_evaluation.__dict__["summarize"] = MethodType(
                summarize, self._pseudo_evaluation
            )

            # Create the evaluation call
            wc = require_weave_client()
            self._evaluate_call = wc.create_call(
                op=self._pseudo_evaluation.evaluate,
                inputs={
                    "self": self._pseudo_evaluation,
                    "model": self._pseudo_model,
                },
                display_name=default_evaluation_display_name,
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

        return PredictionLogger(
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

        # Replace the summarize method with real implementation
        @weave.op(name="Evaluation.summarize")
        def summarize(self: Evaluation) -> dict:
            return summary

        self._pseudo_evaluation.__dict__["summarize"] = MethodType(
            summarize, self._pseudo_evaluation
        )

        # Call the summarize method with the proper context
        assert self._evaluate_call is not None
        with call_context.set_call_stack([self._evaluate_call]):
            self._pseudo_evaluation.summarize()

        # Finish the evaluation call
        wc = require_weave_client()
        wc.finish_call(self._evaluate_call, output=summary)
