import typing
import weave

from .dataset import Dataset
from .model import Model
from .chat_model import ChatModel
from .structured_output import StructuredOutputChatModel


@weave.type()
class Score:
    @weave.op()
    def compute(self, example, prediction):
        ...


@weave.type()
class ScoreExactMatch(Score):
    extract_output: typing.Callable[[typing.Any], typing.Any]

    @weave.op()
    def compute(self, example, prediction):
        return self.extract_output(example) == prediction


@weave.type()
class ScoreLLM(Score):
    chat_llm: StructuredOutputChatModel
    messages_template: typing.Callable[[typing.Any, typing.Any], typing.Any]

    @weave.op()
    def compute(self, example, prediction):
        messages = self.messages_template(example, prediction)
        result_type = weave.types.TypedDict(
            {
                "score": weave.types.Float(),
                "rationale": weave.types.String(),
            }
        )
        response = self.chat_llm.complete(messages, result_type)
        return {
            "score": response["score"],
            "rationale": response["rationale"],
        }


@weave.op()
def evaluate2(score: Score, dataset: Dataset, model: Model) -> typing.Any:
    from .. import weave_internal

    outputs = dataset.rows.apply(lambda ex: model.predict(ex))
    scores = dataset.rows.apply(
        lambda ex, i: score.compute(ex, weave_internal.const(outputs)[i])
    )

    eval_table_columns: dict[str, weave.WeaveList] = {
        "example": dataset.rows,  # type: ignore
        "output": outputs,
        "score": scores,
    }
    return weave.WeaveList(eval_table_columns)
