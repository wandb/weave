# Monitor & Visualize LLM Usage with Weave

These example notebooks demonstrate LLM monitoring with Weave, focusing on the OpenAI API to start.

## Notebooks

* [OpenAI Monitoring Demo](../monitoring/openai_ux_demo.ipynb): create, explore, and share an OpenAI Monitoring Board in Weave
* [Weave Monitor API](../monitoring/monitor_api.ipynb): understand the monitoring API
* [OpenAI Proxy Quickstart](../monitoring/openai_proxy_quickstart.ipynb): set up a proxy to monitor OpenAI API calls

## OpenAI Integration

There are two main ways to authenticate OpenAI API calls to set up a monitoring board

### OpenAI API

1. Set your OPENAI_API_KEY in your environment/script/notebook (e.g. via `os.environ["OPENAI_API_KEY"]`
2. Import openai as follows: `from weave.monitoring import openai`
3. Make calls via the OpenAI SDK.

### OpenAI Proxy

To use the proxy:

1. Find [your wandb API key](https://wandb.ai/authorize) and [your OpenAI API key](https://platform.openai.com/account/api-keys).
2. Set your OPENAI_API_KEY to these two keys joined by ":", i.e. wandb_api_key:openai_api_key.
3. Change the OpenAI base url to `https://wandb.ai/proxy/openai/v1`.
4. Optionally set headers on each call to configure the wandb entity, project, and data stream.
5. Call OpenAI via the OpenAI SDK or CURL from the base url. 

See details and try this yourself in the [quickstart notebook](../monitoring/openai_proxy_quickstart.ipynb)
