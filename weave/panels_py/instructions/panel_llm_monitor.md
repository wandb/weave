# OpenAI Monitoring Quickstart

To record history, monitor performance, & analyze cost/latency of OpenAI calls:

1. Set the OpenAI API Base to `https://proxy.wandb.ai/proxy/openai/v1`.
2. Set the OpenAI API Key to the concatenation of your [W&B API key](https://wandb.ai/authorize) and [OpenAI API key](https://platform.openai.com/account/api-keys).

Setup can be achieved 3 different ways: via environment variables, the python library, or direct http requests. After setup, simply use OpenAI as normal and navigate to `monitoring/openai` via the browser on the left to create a board and visualize your usage.

## Monitoring

### Via environment variables

```shell
OPENAI_API_BASE="https://proxy.wandb.ai/proxy/openai/v1"
OPENAI_API_KEY="$WANDB_API_KEY:$OPENAI_API_KEY"
python prompt.py # Run your existing scripts
```

### Via Python Library

```python
import openai
openai.api_base = "https://proxy.wandb.ai/proxy/openai/v1"
openai.api_key = f"{WANDB_API_KEY}:{OPENAI_API_KEY}"
```

### Via HTTP Request

```shell
curl "https://proxy.wandb.ai/proxy/openai/v1/chat/completions" \
-H "Authorization: Bearer $WANDB_API_KEY:$OPENAI_API_KEY" \
-H "Content-Type: application/json" \
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


## Analyze Data
Once you've logged your data, use the browser on your left to find your table. From there, choose a template to get started!

![](https://raw.githubusercontent.com/wandb/weave/master/docs/assets/full_board_view.png)
