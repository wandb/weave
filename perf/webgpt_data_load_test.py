from datasets import load_dataset
import random
import string
import time
import weave

print("loading dataset")
dataset = load_dataset("openai/webgpt_comparisons", split="train", keep_in_memory=True)
print("removing columns from the dataset")
dataset = dataset.remove_columns(
    ["quotes_0", "tokens_0", "score_0", "quotes_1", "tokens_1", "score_1"]
)
print("flattening the dataset")
dataset = dataset.flatten()
print("removing more columns dataset")
dataset = dataset.remove_columns(["question.id", "question.dataset"])

print("saving dataset")
weave_input = []
for data in dataset:
    data.update(feedback="?")
    weave_input.append(data)

op = weave.save(weave_input, name="webgpt-data:main")

print("saved dataset")
# Write to random items

t0 = time.time()
num_rows = len(weave.use(op))
i = 0
while time.time() - t0 < 5*60:
    idx = random.randint(0, num_rows)
    # In reality we'll be setting the feedback column but this tests the same operation
    rand_str = random.choice(["👍👎"])
    op[idx]["feedback"].set(rand_str)
    i += 1
print(f"Items modified after 5 minutes: {i}")
