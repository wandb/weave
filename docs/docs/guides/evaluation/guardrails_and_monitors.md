import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Guardrails and Monitors

In order to prevent your LLM from generating harmful or inappropriate content, you can set guardrails and monitors using Weave.

## Core Concepts

Everything is built around the concept of a `Scorer`. A `Scorer` is an instance of a sublcass of the `Scorer` class - particularly one that exposes a `score` method. See [Evaluation Metrics](./scorers.md) for more information.

### Monitors
Now, many times you will want to apply a Scorer directly after calling an Op. This can be achieved by using the `apply_scorer` method on the `Call` object.

```python
res, call = op.call(user_input)
# optionally subsample to 25%
if random.random() < 0.25:
    await call.apply_scorer(scorer)
```

This will log the score to Weave which can be viewed and analyzed in the UI.

:::info

Note that this style of Monitor will run the scoring function on the same machine as the call. This might not be desirable in all production environments. Coming soon will be the ability to apply scorers as monitors that run on W&B Weave's servers.

:::

### Guardrails

Guardrails are a way to prevent the LLM from generating harmful or inappropriate content. In Weave, we use the same technique as monitors to apply a Scorer, but in addition to logging the score, we also modify the application logic based on the scorer output

```python
res, call = op.call(user_input)
scorer_res = await call.apply_scorer(guardrail)
if scorer_res.score < 0.5:
    # Do something 
else:
    # Do something else
```



