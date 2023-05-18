from datasets import load_dataset
import random
import time
import weave
import argh


def main(update_duration=60, output_file="/tmp/output.md", only_download_data=False):
    print(f"starting main with update_duration={update_duration}, output_file={output_file}, only_download_data={only_download_data}")
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

    if only_download_data:
        return

    op = weave.save(weave_input, name="webgpt-data:main")

    print(f"saved dataset, {len(weave_input)} items")
    # Write to random items

    t0 = time.time()
    num_rows = len(weave.use(op))
    count = 0

    print(f"starting to update items for {update_duration} seconds")
    st0 = time.time()
    while time.time() - t0 < update_duration:
        idx = random.randint(0, num_rows)
        # In reality we'll be setting the feedback column but this tests the same operation
        rand_str = random.choice(["👍👎"])
        op[idx]["feedback"].set(rand_str)
        count += 1
        curr_time = time.time()
        if curr_time - st0 > 3:
            print(f"Items modified: {count}, {count/(curr_time - t0):0.2f} updates per sec")
            st0 = curr_time
    ups = count/(curr_time - t0)
    status = "🟥"
    if ups > 1:
        status = "🟧"
    elif ups > 5:
        status = "🟩"

    print(f"Items modified after {update_duration} seconds: {count}")
    print(f"::set-output name=updates-per-sec::{ups:0.2f}")
    with open(output_file, "w") as f:
        f.write(f"Items modified after {update_duration} seconds: {count}\n")
        f.write(f"Updates per second: `{ups:0.2f}`\n")
        f.write(f"# status: {status}")

if __name__ == "__main__":
    argh.dispatch_command(main)