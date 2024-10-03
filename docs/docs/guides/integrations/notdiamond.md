# Not Diamond

When building complex LLM workflows users may need to prompt different models according to accuracy,
cost, or call latency. Users can use [Not Diamond][nd] to route prompts in these workflows to the
right model for their needs, helping maximize accuracy while saving on model costs.

## Getting started

Make sure you have [created an account][account] and [generated an API key][keys], then insert your API key below.

![[Create an API key](imgs/notdiamond/api-keys.png)]

## Tracing

Weave integrates with [Not Diamond's Python library][python] to [automatically log API calls][ops].
You only need to run `weave.init()` at the start of your workflow:

```python
from notdiamond import NotDiamond

import weave
weave.init()

client = NotDiamond()
session_id, provider = client.chat.completions.model_select(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Concisely explain merge sort."}
    ],
    model=['openai/gpt-4o', 'anthropic/claude-3-5-sonnet-20240620']
)
```

## Custom routing

Users can also train their own custom routers on [Evaluations][evals], allowing Not Diamond to route prompts
according to eval performance.

Start by training a custom router:

```python
from weave.flow.eval import EvaluationResults
from weave.integrations.notdiamond.custom_router import train_evaluations

model_evals = {
    'openai/gpt-4o': EvaluationResults(...),
    'anthropic/claude-3-5-sonnet-20240620': EvaluationResults(...),
}
preference_id = train_evaluations(
    model_evals=model_evals,
    prompt_column="prompt",
    response_column="actual",
    language="en",
    maximize=True,
    api_key=api_key,
)
```

Then use the custom router by submitting the preference ID alongside any `model_select` request:

```python
from notdiamond import NotDiamond
client = NotDiamond()

session_id, provider = client.chat.completions.model_select(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Concisely explain merge sort."}
    ],
    model=['openai/gpt-4o', 'anthropic/claude-3-5-sonnet-20240620'],
    preference_id=preference_id
)
```

## Additional support

Visit the [docs] for Not Diamond or [send a message][support] us for further support.

You can also [chat with Not Diamond][chat] to learn about prompt routing.

[account]: https://app.notdiamond.ai
[chat]: https://chat.notdiamond.ai
[docs]: https://docs.notdiamond.ai
[evals]: ../../guides/core-types/evaluations.md
[keys]: https://app.notdiamond.ai/keys
[nd]: https://www.notdiamond.ai/
[ops]: ../../guides/tracking/ops.md
[python]: https://github.com/Not-Diamond/notdiamond-python
[support]: mailto:support@notdiamond.ai
