# Verifiers

[Verifiers](https://github.com/willccbb/verifiers) is a flexible framework for creating RL environments and evaluations with custom multi-turn interaction protocols. The Weave integration automatically traces Verifiers environments, rollouts, rubric scoring, parser logic, and tool calls so you can debug, compare, and monitor training and evaluation runs.

Learn more in the Verifiers docs: [Overview](https://verifiers.readthedocs.io/en/latest/), [Environments](https://verifiers.readthedocs.io/en/latest/environments.html), [Training](https://verifiers.readthedocs.io/en/latest/training.html).

## What gets traced

Weave captures the most important Verifiers ops and removes `logprobs` from logged copies to keep traces lightweight while preserving training-time data in-memory. Traced entry points include (non-exhaustive):

- Environment: `Environment.evaluate`, `Environment.generate`, `Environment.a_generate`, `Environment.get_model_response`
- Multi-turn: `MultiTurnEnv.rollout`, `EnvGroup.rollout`, `SingleTurnEnv.env_response`
- Tool use: `ToolEnv.is_completed`, `ToolEnv.env_response`, `ToolEnv.call_tool`, `StatefulToolEnv.update_tool_args`, `StatefulToolEnv.call_tool`, `StatefulToolEnv.env_response`
- Rubrics: `Rubric.score_rollouts`, `Rubric.score_rollout`
- Parsers: `Parser.parse`, `Parser.get_format_reward_func()` and its returned function; specialized parsers like `ThinkParser` and `XMLParser` methods

You’ll see a hierarchical trace of rollouts and scoring for each example, with inputs, outputs, timing, token/cost (when model usage is available), and any parser/rubric sub-ops.

## Getting started

Weave enables implicit patching by default. As long as you call `weave.init()` in your script, Verifiers will be auto-patched when imported.

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

