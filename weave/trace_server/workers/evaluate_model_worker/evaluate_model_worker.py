import asyncio
from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from weave.flow.eval import Evaluation
from weave.scorers.llm_as_a_judge_scorer import LLMAsAJudgeScorer
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import parse_uri
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


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
    client = require_weave_client()

    loaded_evaluation = client.get(parse_uri(args.evaluation_ref))

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

    loaded_model = client.get(parse_uri(args.model_ref))

    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError(
            f"Invalid model reference: expected LLMStructuredCompletionModel, "
            f"got {type(loaded_model).__name__}"
        )

    asyncio.run(
        loaded_evaluation.evaluate(
            loaded_model, __weave={"call_id": args.evaluation_call_id}
        )
    )

    return
