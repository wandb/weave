from datasets import load_dataset
import weave
import cProfile

dataset = load_dataset("openai/webgpt_comparisons", split="train")
dataset = dataset.remove_columns(
    ["quotes_0", "tokens_0", "score_0", "quotes_1", "tokens_1", "score_1"]
)
dataset = dataset.flatten()
dataset = dataset.remove_columns(["question.id", "question.dataset"])

weave_input = []
for data in dataset:
    weave_input.append(data)

op = weave.save(weave_input, name="webgpt-data:main")
cProfile.run('op[0]["answer_0"].set("test")')