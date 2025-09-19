import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Verifiers

[Verifiers](https://github.com/willccbb/verifiers) is a library of modular components for creating Reinforcement Learning (RL) environments and training LLM agents. Environments built with Verifiers can serve as LLM evaluations, synthetic data pipelines, agent harnesses for any OpenAI‑compatible endpoint, and RL training.

Along with using W&B to record your training metrics, you can integrate Weave with your Verifiers RL workflows to gain observability into how your model performs during training. Weave records inputs, outputs, and timestamps for each step so you can inspect how data transforms at every turn, debug complex multi‑round conversations, and optimize training results.

You can also use Weave and Verifiers together to perform evaluations.

This guide shows you how to install Verifiers, W&B, and Weave, and provides two examples of how to use Verifiers with Weave and W&B.

![verifiers wandb run page](imgs/verifiers/verifiers.gif)

## Getting started

To integrate Verifiers with Weave, start by installing the Verifiers library using `uv` ([recommended by the library's authors](https://github.com/willccbb/verifiers?tab=readme-ov-file#setup)). Use one of the following commands to install the library:

```bash
# Installs core library for local development and API-based models
uv add verifiers

# Installs full version of library with all optional dependencies, including PyTorch and GPU support
uv add 'verifiers[all]' && uv pip install flash-attn --no-build-isolation

# Installs latest version of library directly from GitHub, including latest unreleased features and fixes
uv add verifiers @ git+https://github.com/willccbb/verifiers.git
```

Then install Weave and W&B:

```bash
uv pip install weave wandb
```

Weave enables [implicit patching](../integrations/index.md) for the library by default. This allows you to use Weave with Verifiers without requiring explicit call patch functions.

### Trace rollouts and evaluate

Once you've installed the necessary libraries, you can use Weave and Verifiers together to trace calls and run evaluations.

The following example script demonstrates how to run an evaluation with Verifiers and log the results to Weave. The script tests the LLM's ability to solve math problems using the [GSM8K dataset](https://huggingface.co/datasets/openai/gsm8k). It asks GPT-4 to solve two math problems, extracts the numerical value from each response, and then grades the attempt using Verifiers as an evaluation framework.

Run the example and inspect the results in Weave:

```python
import os
from openai import OpenAI
import verifiers as vf
import weave

os.environ["OPENAI_API_KEY"] = "<YOUR-OPENAI-API-KEY>"

# Initialize Weave
weave.init("verifiers_demo")

# Minimal single-turn environment
dataset = vf.load_example_dataset("gsm8k", split="train").select(range(2))
parser = vf.ThinkParser()

def correct_answer(parser, completion, answer):
    parsed = parser.parse_answer(completion) or ""
    return 1.0 if parsed.strip() == answer.strip() else 0.0

rubric = vf.Rubric(funcs=[correct_answer, parser.get_format_reward_func()], weights=[1.0, 0.2])

env = vf.SingleTurnEnv(
    dataset=dataset,
    system_prompt="Think step-by-step, then answer.",
    parser=parser,
    rubric=rubric,
)

client = OpenAI()
results = env.evaluate(
    client, "gpt-4.1-mini", num_examples=2, rollouts_per_example=2, max_concurrent=8
)
```

### Fine-tune a model with experiment tracking and tracing

Weave can be a powerful tool in your RL fine‑tuning workflows by providing insight into how your models are performing during training. When used alongside W&B, you get comprehensive observability: W&B tracks training metrics and performance charts, while Weave captures detailed traces of each interaction during the training process.

The `verifiers` repository includes ready‑to‑run [examples](https://github.com/willccbb/verifiers/tree/main/examples/grpo) to help you get started.

The following example RL training pipeline runs a local inference server and trains a model using the GSM8K dataset. The model responds with answers to the math problems and the training loop scores the output and updates the model accordingly. W&B logs the training metrics, like loss, reward, and accuracy, while Weave captures the input, output, reasoning, and scoring.

To use this pipeline:

1. Install the framework from the source. The following commands install the Verifiers library from GitHub and the necessary dependencies:

```bash
git clone https://github.com/willccbb/verifiers
cd verifiers
uv sync --all-extras && uv pip install flash-attn --no-build-isolation
```

2. Install an off-the-shelf environment. The following command installs the pre-configured GSM8K training environment:

```bash
vf-install gsm8k --from-repo
```

3. Train your model. The following commands launch the inference server and training loop, respectively. This example workflow sets `report_to=wandb` by default, so you don't need to call `wandb.init` separately. You'll be prompted to authenticate this machine to log metrics to W&B.


```bash
# Runs inference server
CUDA_VISIBLE_DEVICES=0 vf-vllm --model willcb/Qwen3-0.6B --enforce-eager --disable-log-requests

# Runs training loop
CUDA_VISIBLE_DEVICES=1 accelerate launch --num-processes 1 --config-file configs/zero3.yaml examples/grpo/train_gsm8k.py
```

:::note
We successfully tested this example on 2xH100s and set the following environment variables for increased stability:

```bash
# In BOTH shells (server and trainer) before launch
export NCCL_CUMEM_ENABLE=0
export NCCL_CUMEM_HOST_ENABLE=0
```

These variables disable CUDA Unified Memory (CuMem) for device memory allocations.
:::

Once training begins, you can [view the traces](../../guides/tools/weave-in-workspaces) logged during your run in the UI.

Traces omit `logprobs` for the `Environment.a_generate` and `Rubric.score_rollouts` methods. This keeps payloads small while leaving the originals intact for training.

## See also

Verifiers has first‑class integration with W&B Models. See [Monitoring](https://verifiers.readthedocs.io/en/latest/training.html#monitoring) to learn more.
