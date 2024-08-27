# Cerebras

Weave automatically tracks and logs LLM calls made via the [Cerebras Cloud SDK](https://inference-docs.cerebras.ai/introduction). Because when you're using Cerebras, every millisecond counts!

## Traces

In the world of AI, speed is king. It's crucial to keep track of your LLM calls, not just for debugging, but also to ensure you're getting the lightning-fast [inference Cerebras](https://inference-docs.cerebras.ai/introduction) is known for. Weave helps you do just that by automatically capturing traces for the Cerebras Cloud SDK.

Let's dive in and see how Weave can help you track your speed demon of an AI:

```python
import weave
from cerebras.cloud.sdk import Cerebras
import os

weave.init("cerebras_speedster")

# Use the Cerebras SDK as usual
api_key = os.environ["CEREBRAS_API_KEY"]
model = "llama3.1-8b"  # Cerebras model

client = Cerebras(api_key=api_key)

response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "What's the fastest land animal?"}],
)

print(response.choices[0].message.content)
```

Weave will now track and log all LLM calls made through the Cerebras SDK. You can view the traces in the Weave web interface, including details like token usage and response time.

[![cerebras_calls.png](imgs/cerebras_calls.png)](https://wandb.ai/capecape/cerebras_speedster/weave/traces)

## Wrapping with your own ops

Want to make your results reproducible while still maintaining that Cerebras speed? Weave ops have got you covered. They automatically version your code as you experiment and capture inputs and outputs. Here's how you can use them with Cerebras:

```python
@weave.op
def animal_speedster(animal: str, model: str) -> str:
    "Find out how fast an animal can run"
    
    client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": f"How fast can a {animal} run?"}],
    )
    return response.choices[0].message.content

animal_speedster("cheetah", "llama3.1-8b")
animal_speedster("ostrich", "llama3.1-8b")
animal_speedster("human", "llama3.1-8b")
```

## Create a `Model` for easier experimentation

When you're pushing the boundaries of speed with Cerebras, you need to keep track of your experiments. The [`Model`](/guides/core-types/models) class helps you organize and compare different iterations of your app.

Here's an example of how you can use it with Cerebras:

```python
import weave
from cerebras.cloud.sdk import Cerebras

weave.init("cerebras_speedster")

client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])

class AnimalSpeedModel(weave.Model):
    model: str
    temperature: float

    @weave.op
    def predict(self, animal: str) -> str:
        "Predict the top speed of an animal"        

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": f"What's the top speed of a {animal}?"}],
            temperature=self.temperature
        )
        return response.choices[0].message.content

speed_model = AnimalSpeedModel(
    model="llama3.1-8b",
    temperature=0.7
)
result = speed_model.predict(animal="peregrine falcon")
print(result)
```

With this setup, you can easily experiment with different models and parameters, all while keeping track of your blazing-fast Cerebras-powered inferences!

[![cerebras_model.png](imgs/cerebras_model.png)](https://wandb.ai/capecape/cerebras_speedster/weave/traces)
