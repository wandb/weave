from datasets import load_dataset
import random
import time
import weave
import argh


def main():
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
    count = 0
    st0 = time.time()
    while time.time() - t0 < 2*60:
        idx = random.randint(0, num_rows)
        # In reality we'll be setting the feedback column but this tests the same operation
        rand_str = random.choice(["👍👎"])
        op[idx]["feedback"].set(rand_str)
        count += 1
        curr_time = time.time()
        if curr_time - st0 > 3:
            print(f"Items modified: {count}, {count/(curr_time - t0):0.2f} updates per sec")
            st0 = curr_time
    print(f"Items modified after 5 minutes: {count}")


if __name__ == "__main__":
    argh.dispatch_command(main)