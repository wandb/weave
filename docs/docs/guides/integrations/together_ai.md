# Together AI

Together AI is a platform for building and finetuning generative AI models, focusing on Open Source LLMs, and allowing customers to fine-tune and host their own models.

:::info

Full Weave `together` python package support is currently in development

:::

While full Weave support for the `together` python package is currently in development, Together supports the OpenAI SDK compatibility ([docs](https://docs.together.ai/docs/openai-api-compatibility)) which Weave automatically detects and integrates with.

To switch to using the Together API, simply switch out the API key to your [Together API](https://docs.together.ai/docs/get-started#access-your-api-key) key, `base_url` to `https://api.together.xyz/v1`, and model to one of their [chat models](https://docs.together.ai/docs/inference-models#chat-models).

```python
import os
import openai
import weave

# highlight-next-line
weave.init('together-weave')

system_content = "You are a travel agent. Be descriptive and helpful."
user_content = "Tell me about San Francisco"

# highlight-next-line
client = openai.OpenAI(
# highlight-next-line
    api_key=os.environ.get("TOGETHER_API_KEY"),
# highlight-next-line
    base_url="https://api.together.xyz/v1",
# highlight-next-line
)
chat_completion = client.chat.completions.create(
    model="mistralai/Mixtral-8x7B-Instruct-v0.1",
    messages=[
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ],
    temperature=0.7,
    max_tokens=1024,
)
response = chat_completion.choices[0].message.content
print("Together response:\n", response)
```

While this is a simple example to get started, see our [OpenAI](/guides/integrations/openai#track-your-own-ops) guide for more details on how to integrate Weave with your own functions for more complex use cases.
