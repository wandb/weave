from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import MethodType
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, PrivateAttr

import weave
from weave.flow.eval import Evaluation
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


stub_dataset = weave.Dataset(rows=[{"THIS_IS_A_DUMMY": "IGNORE"}])


class EvaluationLogger(BaseModel):
    model_id: ID = ""
    _eval_started: bool = PrivateAttr(False)
    _logged_summary: bool = PrivateAttr(False)
    _evaluate_call: Call | None = PrivateAttr(None)
    _pseudo_model: Model = PrivateAttr(default_factory=Model)
    _pseudo_evaluation: Evaluation = PrivateAttr(
        default_factory=lambda: Evaluation(dataset=[{"": None}])
    )

    def log_prediction(self, inputs: dict, output: Any) -> PredictionLogger:
        eval_self = self
        if not self._eval_started:
            self._eval_started = True

            @weave.op
            def predict(self: Model, inputs: dict) -> Any:
                # Get the output from the context variable
                return current_output.get()

            # Hacks: Put custom predict and predict_and_score methods back on the model
            self._pseudo_model.__dict__["predict"] = MethodType(
                predict, self._pseudo_model
            )

            @weave.op(name="Evaluation.evaluate")
            def evaluate(self: Evaluation, model: Model) -> None: ...

            self._pseudo_evaluation.__dict__["evaluate"] = MethodType(
                evaluate, self._pseudo_evaluation
            )

            @weave.op
            def predict_and_score(self: Evaluation, model: Model, inputs: dict) -> dict:
                assert eval_self._pseudo_model is not None
                res = eval_self._pseudo_model.predict(inputs)
                return {
                    "model_output": res,
                    "scores": NOT_DEFINED,
                    "model_latency": NOT_DEFINED,
                }

            self._pseudo_evaluation.__dict__["predict_and_score"] = MethodType(
                predict_and_score, self._pseudo_evaluation
            )

            # Create a placeholder summarize method
            @weave.op
            def summarize(self: Evaluation) -> dict:
                # This is just a placeholder - the real implementation
                # will be set in log_summary
                return {}

            # Attach the placeholder to the evaluation object
            self._pseudo_evaluation.__dict__["summarize"] = MethodType(
                summarize, self._pseudo_evaluation
            )

            # Define a summarize factory that will be used later in log_summary
            def summarize_factory(summary_value: dict) -> Callable:
                @weave.op
                def new_summarize(self: Evaluation) -> dict:
                    return summary_value

                return new_summarize

            self._pseudo_evaluation.__dict__["summarize_factory"] = summarize_factory

            # _, evaluate_call = evaluate.call(
            #     self._pseudo_evaluation, self._pseudo_model
            # )
            wc = require_weave_client()
            evaluate_call = wc.create_call(
                op=evaluate,
                inputs={
                    "self": self._pseudo_evaluation,
                    "model": self._pseudo_model,
                },
            )

            self._evaluate_call = evaluate_call
            # hack: put the evaluate call back on the stack
            call_context.push_call(evaluate_call)

        # Use a context manager to set the current output in a thread-safe way
        with set_current_output(output):
            assert self._pseudo_evaluation is not None
            _, predict_and_score_call = self._pseudo_evaluation.predict_and_score.call(
                self._pseudo_evaluation, self._pseudo_model, inputs
            )

        # Extract the model_output directly from the call output
        model_output = (
            predict_and_score_call.output.get("model_output")
            if predict_and_score_call.output
            else None
        )

        return PredictionLogger(
            model_id="123",
            inputs=inputs,
            output=model_output,
            hack_reference_to_predict_and_score=predict_and_score_call,
            hack_reference_to_evaluate=self._evaluate_call,
        )

    def log_summary(self, summary: dict) -> None:
        # basically materialize everything here
        # create Dataset object
        # create Evaluation object
        # write the summary records
        if self._logged_summary:
            return

        self._logged_summary = True
        assert self._evaluate_call is not None
        assert self._pseudo_evaluation is not None

        # Get the new summarize implementation with the real summary value
        new_summarize = self._pseudo_evaluation.summarize_factory(summary)

        # Replace the placeholder with the real implementation
        self._pseudo_evaluation.__dict__["summarize"] = MethodType(
            new_summarize, self._pseudo_evaluation
        )

        # Call it within the proper context
        with call_context.set_call_stack([self._evaluate_call]):
            self._pseudo_evaluation.summarize()

        wc = require_weave_client()
        wc.finish_call(self._evaluate_call, output=summary)
