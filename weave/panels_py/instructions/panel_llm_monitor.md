## OpenAI Monitoring Quickstart

To record history, monitor performance, & analyze cost/latency of OpenAI calls:

1. Set the OpenAI API Base to `https://api.wandb.ai/proxy/openai/v1`.
2. Set the OpenAI API Key to the concatenation of your [W&B API key](https://wandb.ai/authorize) and [OpenAI API key](https://platform.openai.com/account/api-keys).

Setup can be achieved 2 different ways: via the python library or direct http requests. After setup, simply use OpenAI as normal and navigate to `monitoring/openai` via the browser on the left to create a board and visualize your usage.

### Via Python Library

```python
import openai
openai.api_base = "https://api.wandb.ai/proxy/openai/v1"
openai.api_key = f"{WANDB_API_KEY}:{OPENAI_API_KEY}"
openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Tell me a joke about loss functions!"}],
    headers={
        "X-Wandb-Entity": WANDB_ENTITY,
        "X-Wandb-Project": WANDB_PROJECT,
        "X-Wandb-Stream": WANDB_STREAM,
    }
)
```

### Via HTTP Request

```shell
curl "https://api.wandb.ai/proxy/openai/v1/chat/completions" \
-H "Authorization: Bearer $WANDB_API_KEY:$OPENAI_API_KEY" \
-H "Content-Type: application/json" \
-H "X-Wandb-Entity: $WANDB_ENTITY" \
-H "X-Wandb-Project: $WANDB_PROJECT" \
-H "X-Wandb-Stream: $WANDB_STREAM" \
-d '{
     "model": "gpt-3.5-turbo",
     "messages": [{"role": "user", "content": "Tell me a joke about loss functions!"}]
   }'
```

## In-depth Tutorials

For more ways to configure monitoring and understand LLM usage, follow along with one of our tutorials:

| Method        | Full tutorial                                                                                                                                                                                                 | Scenario                                                                                                                                                                            |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenAI Proxy  | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/prompts/llm_monitoring/openai_proxy_quickstart.ipynb)  | For those looking to use existing OpenAI library calls, W&B can serve as a proxy, automatically logging all necessary data. This is great for developers, teams, and organizations. |
| Python Client | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/prompts/llm_monitoring/openai_client_quickstart.ipynb) | For those looking to customize metrics and programmatically add more data to requests, developers should use the Weave python client directly.                                      |

For full details and features, see the [Weave Monitoring README](https://github.com/wandb/weave/tree/master/examples/prompts/llm_monitoring).
