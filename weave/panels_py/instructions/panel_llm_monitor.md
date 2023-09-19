## OpenAI Monitoring Quicksart

To start monitoring OpenAI calls:

1. Set the OpenAI API Base to `https://api.wandb.ai/proxy/openai/v1`.
2. Set the OpenAI API Key to the concatenation of your [W&B API key](https://wandb.ai/authorize) and [OpenAI API key](https://platform.openai.com/account/api-keys).

### Via environment variables

```shell
OPENAI_API_BASE="https://api.wandb.ai/proxy/openai/v1"
OPENAI_API_KEY="$WANDB_API_KEY:$OPENAI_API_KEY"
```

### Via Python

```python
import openai
openai.api_base = "https://api.wandb.ai/proxy/openai/v1"
openai.api_key = f"{WANDB_API_KEY}:{OPENAI_API_KEY}"
```

## Configure and script OpenAI monitoring and visualization

Log your OpenAI data to W&B via one of the following:

| Method         | Full tutorial                                                                                                                                                                           | Scenario                                                                     |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Python Client  | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://github.com/wandb/weave/blob/master/examples/prompts/llm_monitoring/openai_client_quickstart.ipynb) | For devs, visualize, understand, and customize analysis of your LLMs         |
| OpenAI Proxy   | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://github.com/wandb/weave/blob/master/examples/prompts/llm_monitoring/openai_proxy_quickstart.ipynb)  | For teams, track LLM usage and key metrics like cost/latency across projects |
| Monitoring API | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://github.com/wandb/weave/blob/master/examples/prompts/llm_monitoring/weave_monitor_api.ipynb)        | Monitor any generic functions or app over time                               |

For full details and features, see the [Weave Monitoring README](https://github.com/wandb/weave/tree/master/examples/prompts/llm_monitoring).
