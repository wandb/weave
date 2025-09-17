# Verifiers

[Verifiers](https://github.com/willccbb/verifiers) is a library of modular components for creating RL environments and training LLM agents. Environments built with Verifiers can be used as LLM evaluations, synthetic data pipelines, agent harnesses for any OpenAI‑compatible endpoint, and for RL training.

With Weave, you get automatic tracing purpose‑built for Agentic RL workflows. Agentic RL involves multiple turns of conversations, tool invocations, and environment/user interactions during rollouts. Just tracking the loss, reward and other timeseries data points are not sufficient to efficiently debug this workflow.

Weave record inputs, outputs, and timestamps for each step so you can inspect how data transforms at every turn, debug complex multi‑round conversations, and optimize training results.

## Getting started

Weave enables implicit patching by default. As long as you call `weave.init()` in your script, Verifiers will be auto-patched when imported.

Install (uv recommended):

```bash
# Local dev / evaluation with API models
uv add verifiers

# Trainer + GPU support
uv add 'verifiers[all]' && uv pip install flash-attn --no-build-isolation

# Latest main branch
uv add verifiers @ git+https://github.com/willccbb/verifiers.git
```

```python
import os
from openai import OpenAI
import verifiers as vf
import weave

os.environ["OPENAI_API_KEY"] = "<YOUR-OPENAI-API-KEY>"

# Initialize Weave
weave.init("verifiers_demo")

# Optional: explicit patch if you disabled implicit patching
# weave.integrations.patch_verifiers()

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

print(results.metrics)
```

## Multi-turn with tools

```python
import verifiers as vf

def calculate(expression: str) -> float:
    return eval(expression)

parser = vf.ThinkParser()
rubric = vf.Rubric(funcs=[parser.get_format_reward_func()])

dataset = vf.load_example_dataset("gsm8k", split="test").select(range(1))

env = vf.ToolEnv(
    dataset=dataset,
    tools=[calculate],
    parser=parser,
    rubric=rubric,
)

# Now run env.evaluate(...) as above; Weave will trace tool calls and env responses
```

## Tips

- Traces will omit `logprobs` in logged copies to keep payloads small while leaving originals intact for training.
- For larger runs, use Verifiers async generation (`a_generate`) and increase `max_concurrent` to speed up logging and evaluation.
- Combine Weave’s comparison tools to compare Verifiers evaluations over time or across models.

## See also

- Verifiers docs: [Overview](https://verifiers.readthedocs.io/en/latest/), [Environments](https://verifiers.readthedocs.io/en/latest/environments.html), [Training](https://verifiers.readthedocs.io/en/latest/training.html)

