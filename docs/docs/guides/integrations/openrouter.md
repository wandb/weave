# Open Router

Openrouter.ai is a unified interface for many LLMs, supporting both foundational models like OpenAI GPT-4, Anthropic Claude, Google Gemini but also open source models like LLama-3, Mixtral and [many more](https://openrouter.ai/models), some models are even offered for free. 

Open Router offers a Rest API and an OpenAI SDK compatibility ([docs](https://docs.together.ai/docs/openai-api-compatibility)) which Weave automatically detects and integrates with (see Open Router [quick start](https://openrouter.ai/docs/quick-start) for more details).

To get switch your OpenAI SDK code to Open Router, simply switch out the API key to your [Open Router API](https://openrouter.ai/docs/api-keys) key, `base_url` to `https://openrouter.ai/api/v1`, and model to one of their many [chat models](https://openrouter.ai/docs/models).

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
    api_key=os.environ.get("OPENROUTER_API_KEY"),
# highlight-next-line
    base_url="https://api.together.xyz/v1",
# highlight-next-line
)
chat_completion = client.chat.completions.create(
    extra_headers={
    "HTTP-Referer": $YOUR_SITE_URL, # Optional, for including your app on openrouter.ai rankings.
    "X-Title": $YOUR_APP_NAME, # Optional. Shows in rankings on openrouter.ai.
    },
    model="microsoft/phi-3-mini-128k-instruct:free",
    messages=[
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ],
    temperature=0.7,
    max_tokens=1024,
)
response = chat_completion.choices[0].message.content
print("Model response:\n", response)
```

While this is a simple example to get started, see our [OpenAI](/guides/integrations/openai#track-your-own-ops) guide for more details on how to integrate Weave with your own functions for more complex use cases.
