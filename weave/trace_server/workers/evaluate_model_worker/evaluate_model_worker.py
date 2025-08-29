import asyncio
from abc import ABC, abstractmethod

import ddtrace
from pydantic import BaseModel, ConfigDict

import weave
from weave.evaluation.eval import Evaluation
from weave.scorers.llm_as_a_judge_scorer import LLMAsAJudgeScorer
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import Ref
from weave.trace.weave_client import WeaveClient
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)

EVALUATE_MODEL_WORKER_MARKER = {"_weave_eval_meta": {"evaluate_model_worker": True}}


class EvaluateModelArgs(BaseModel):
    project_id: str
    evaluation_ref: str
    model_ref: str
    wb_user_id: str
    evaluation_call_id: str

    model_config = ConfigDict(protected_namespaces=())


class EvaluateModelDispatcher(ABC):
    @abstractmethod
    def dispatch(self, args: EvaluateModelArgs) -> None:
        pass


def evaluate_model(args: EvaluateModelArgs) -> None:
    _evaluate_model(args)


@ddtrace.tracer.wrap(name="evaluate_model_worker.evaluate_model")
def _evaluate_model(args: EvaluateModelArgs) -> None:
    client = require_weave_client()

    loaded_evaluation = _get_valid_evaluation(client, args.evaluation_ref)

    loaded_model = _get_valid_model(client, args.model_ref)

    _run_evaluation(loaded_evaluation, loaded_model, args.evaluation_call_id)


@ddtrace.tracer.wrap(name="evaluate_model_worker.evaluate_model.get_valid_evaluation")
def _get_valid_evaluation(client: WeaveClient, evaluation_ref: str) -> Evaluation:
    loaded_evaluation = client.get(Ref.parse_uri(evaluation_ref))

    if not isinstance(loaded_evaluation, Evaluation):
        raise TypeError(
            f"Invalid evaluation reference: expected Evaluation, "
            f"got {type(loaded_evaluation).__name__}"
        )

    scorers = loaded_evaluation.scorers
    if scorers:
        for scorer in scorers:
            if not isinstance(scorer, LLMAsAJudgeScorer):
                raise TypeError(
                    f"Invalid scorer reference: expected LLMAsAJudgeScorer, "
                    f"got {type(scorer).__name__}"
                )

    return loaded_evaluation


@ddtrace.tracer.wrap(name="evaluate_model_worker.evaluate_model.get_valid_model")
def _get_valid_model(
    client: WeaveClient, model_ref: str
) -> LLMStructuredCompletionModel:
    loaded_model = client.get(Ref.parse_uri(model_ref))

    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError(
            f"Invalid model reference: expected LLMStructuredCompletionModel, "
            f"got {type(loaded_model).__name__}"
        )
    return loaded_model


@ddtrace.tracer.wrap(name="evaluate_model_worker.evaluate_model.run_evaluation")
def _run_evaluation(
    loaded_evaluation: Evaluation,
    loaded_model: LLMStructuredCompletionModel,
    evaluation_call_id: str,
) -> None:
    with weave.attributes(EVALUATE_MODEL_WORKER_MARKER):
        return asyncio.run(
            loaded_evaluation.evaluate(
                loaded_model, __weave={"call_id": evaluation_call_id}
            )
        )
