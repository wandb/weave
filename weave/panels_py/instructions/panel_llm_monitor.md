## OpenAI Monitoring Quickstart

Start monitoring your OpenAI calls with the steps below.

- Set the OpenAI API Base to `https://api.wandb.ai/proxy/openai/v1`.
- Set the OpenAI API Key to the concatenation of your [W&B API key](https://wandb.ai/authorize) and [OpenAI API key](https://platform.openai.com/account/api-keys).

### 1. Set Environment Variables via Terminal:

```shell
export WANDB_API_KEY="" # API Key from https://wandb.ai/authorize
export WANDB_OPENAI_API_KEY="$WANDB_API_KEY:$OPENAI_API_KEY"
```

### 2. Set the API Base and API Key:

```python
import os
import openai
openai.api_base = "https://api.wandb.ai/proxy/openai/v1"
openai.api_key = os.getenv("WANDB_OPENAI_API_KEY")
```

### 3. Create a Monitoring Board

Use OpenAI as normal and navigate to `monitoring/openai` via the project browser on the left to create a board to visualize your usage.

## In-depth Tutorials

For more details and ways to monitor LLMs, you can follow along with one of the following tutorials.

| Method | Tutorial | Use Case | 
|--------|----------|---------------|
| Python Client |[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/monitoring/openai_client_quickstart.ipynb)| For devs, visualize, understand, and customize analysis of your LLMs | 
| OpenAI Proxy | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/monitoring/openai_proxy_quickstart.ipynb) | For teams, track LLM usage and key metrics like cost/latency across projects |
| Monitoring API | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/examples/monitoring/weave_monitor_api.ipynb) | Monitor any generic functions or app over time |

For full details and features, see the [Weave Monitoring README](https://github.com/wandb/weave/tree/master/examples/monitoring).
