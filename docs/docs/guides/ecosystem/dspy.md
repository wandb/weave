---
sidebar_position: 2
hide_table_of_contents: true
---

# DSPy

[DSPy](https://dspy-docs.vercel.app/) is a framework for algorithmically optimizing LM prompts and weights, especially when LMs are used one or more times within a pipeline. Weave automatically tracks and logs calls made using DSPy modules and functions.

## Traces

It’s important to store traces of langugae model applications in a central database, both during development and in production. These traces can be useful for debugging, and as a dataset that will help you improve your application.

Weave will automatically capture traces for [DSPy](https://dspy-docs.vercel.app/). You can use the library as usual, start by calling `weave.init(project_name="<YOUR-WANDB-PROJECT-NAME>")`:

```python
import os
import dspy
import weave

os.environ["OPENAI_API_KEY"] = "<YOUR-OPENAI-API-KEY>"

weave.init(project_name="<YOUR-WANDB-PROJECT-NAME>")

gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
dspy.configure(lm=gpt3_turbo)
classify = dspy.Predict("sentence -> sentiment")
classify(sentence="it's a charming and often affecting journey.")
```

[![dspy_trace.png](imgs/dspy_trace.png)](https://wandb.ai/geekyrakshit/dspy-project/weave/calls)
