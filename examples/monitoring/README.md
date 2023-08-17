# Monitor & Visualize LLM Usage with Weave

These example notebooks demonstrate LLM monitoring with Weave, starting with visualizing and understanding OpenAI API usage for a project or team.

## Notebooks

* [OpenAI Monitoring Demo](../monitoring/openai_ux_demo.ipynb): create, explore, and share OpenAI Monitoring Boards in Weave
* [Weave Monitoring API](../monitoring/monitor_api.ipynb): understand the Weave monitoring API
* [OpenAI Proxy Quickstart](../monitoring/openai_proxy_quickstart.ipynb): set up a proxy to monitor OpenAI API calls

## OpenAI Integration

There are two main ways to authenticate OpenAI API calls so you can view them in a monitoring board.

### OpenAI API

1. Set your OPENAI_API_KEY in your environment/script/notebook (e.g. via `os.environ["OPENAI_API_KEY"]`).
2. Import openai as follows: `from weave.monitoring import openai`.
3. Make calls via the OpenAI SDK as usual.

See details and create an interactive board in the [OpenAI monitoring notebook](../monitoring/openai_ux_demo.ipynb).

### OpenAI Proxy

To log all calls made via an OpenAI proxy:

1. Find [your wandb API key](https://wandb.ai/authorize) and [your OpenAI API key](https://platform.openai.com/account/api-keys).
2. Set your OPENAI_API_KEY to these two keys joined by ":", i.e. wandb_api_key:openai_api_key.
3. Change the OpenAI base url to `https://wandb.ai/proxy/openai/v1`.
4. Optionally set headers on each call to configure the wandb entity, project, and data stream name.
5. Call OpenAI via the OpenAI SDK or CURL from the base url. 

See details and try some calls from the [proxy quickstart notebook](../monitoring/openai_proxy_quickstart.ipynb).
