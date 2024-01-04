import typing
import weave
from weave import weaveflow

weave.init("wf-obj-eval-testing1")
# weave.init_local_client()

dataset = weaveflow.Dataset(
    [
        {"id": "0", "q": "1 + 1", "a": "2"},
        {"id": "1", "q": "1 / 3", "a": "0.3333333333"},
    ]
)
dataset_ref = weave.publish(dataset, "dataset")


@weave.type()
class AddModel(weaveflow.Model):
    llm: weaveflow.ChatModel

    @weave.op()
    def predict(self, example: typing.Any) -> typing.Any:
        response = self.llm.complete(
            [
                {
                    "role": "user",
                    "content": "Answer the following. Just provide the answer: "
                    + example["q"],
                }
            ]
        )
        return response["choices"][0]["message"]["content"]


model = AddModel(weaveflow.OpenaiChatModel("gpt-3.5-turbo", 0.7))


@weave.op()
def get_answer_from_example(example: typing.Any) -> typing.Any:
    return example["a"]


exact_evaluator = weaveflow.EvaluateExactMatch(get_answer_from_example)


@weave.op()
def make_llm_eval_messages(example: typing.Any, prediction: typing.Any) -> typing.Any:
    prompt_args = {
        "question": example["q"],
        "answer": example["a"],
        "prediction": prediction,
    }
    prompt = """
Please score the following, on a scale of 1-5, with one being worse. Also provide your rationale.

Question: {question}

Answer: {answer}

Correct answer: {prediction}
""".format(
        **prompt_args
    )
    return [{"role": "user", "content": prompt}]


eval_chat_model = weaveflow.StructuredOutputChatModelSystemPrompt(
    weaveflow.OpenaiChatModel("gpt-4", 0.7)
)

llm_evaluator = weaveflow.EvaluateLLM(eval_chat_model, make_llm_eval_messages)

evaluator = weaveflow.EvaluateMulti({"exact": exact_evaluator, "llm": llm_evaluator})

print(weaveflow.evaluate(evaluator, dataset_ref, model))
