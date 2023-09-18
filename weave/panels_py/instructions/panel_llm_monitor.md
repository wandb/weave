Simply set the OpenAI API Base to `https://api.wandb.ai/proxy/openai/v1` and the OpenAI API Key to the concatenation of your W&B API Key ([wandb.ai/authorize](https://wandb.ai/authorize)) and current OpenAI API Key ([platform.openai.com/account/api-keys](https://platform.openai.com/account/api-keys)) in order to track all API calls! Please refer to the [Weave Monitoring README](https://github.com/wandb/weave/tree/master/examples/monitoring) for full details. Features:

- Automatically track LLM usage and aggregate useful metrics like cost, latency and throughput across your projects/teams
- Dynamically query and derive insights from the logs of all your OpenAI API calls
- Iterate visually to slice, aggregate, and explore your data

### Example using environment variables

```shell
OPENAI_API_BASE="https://api.wandb.ai/proxy/openai/v1"
OPENAI_API_KEY="$WANDB_API_KEY:$OPENAI_API_KEY"
```

### Example using Python library

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://github.com/wandb/weave/blob/master/examples/monitoring/openai_proxy_quickstart.ipynb)

```python
import openai
openai.api_base = "https://api.wandb.ai/proxy/openai/v1"
openai.api_key = f"{WANDB_API_KEY}:{OPENAI_API_KEY}"
openai.ChatCompletion.create(...)
```
