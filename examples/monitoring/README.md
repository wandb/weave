# Monitor & Visualize LLM Usage with Weave

These example notebooks demonstrate LLM monitoring with Weave, starting with visualizing and understanding OpenAI API usage for a project or team.

<img src="../../docs/assets/mini_prodmon_overview.gif" width="100%">

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

1. Find your wandb API key: for the public cloud instance, this will be at [wandb.ai/authorize](https://wandb.ai/authorize). On other instances, append "/authorize" to the base url of your instance.
2. Find [your OpenAI API key](https://platform.openai.com/account/api-keys).
3. Set your OPENAI_API_KEY to these two keys joined by ":", i.e. wandb_api_key:openai_api_key.
4. Change the OpenAI base url to `https://wandb.ai/proxy/openai/v1` for the public cloud instance (otherwise, replace `wandb.ai` with the base url for your instance).
5. Optionally set headers on each call to configure the wandb entity, project, and data stream name (see the table below for details).
6. Call OpenAI via the OpenAI SDK or CURL from the base url. 

Try some calls from the [proxy quickstart notebook](../monitoring/openai_proxy_quickstart.ipynb).

### OpenAI Proxy Headers

You can configure where your data is streamed and stored via proxy headers. For OpenAI SDK calls, pass a dictionary of "header name" keys to "header value" values in the `headers` argument.
For CURL, add each header as an argument flag in the CURL command with the syntax `-H header_name: header_value`:

| Header name | Description | SDK Example | CURL Example | Default setting |
|-------------|-------------|-------------|--------------|-----------------|
|X-Wandb-Entity| set the wandb entity for this call | {"X-Wandb-Entity" : "my_dream_team"}| `-H X-Wandb-Entity: my_dream_team`| your default entity on your W&B instance |
|X-Wandb-Project| set the wandb project name for this call | {"X-Wandb-Project" : "my_dream_llm"}| `-H X-Wandb-Project: my_dream_llm`| `monitoring` |
|X-Wandb-Stream| set the StreamTable name for this call | {"X-Wandb-Stream" : "my_chatbot_test"}| `-H X-Wandb-Stream: my_chatbot_test` | `openai` |
|X-Wandb-Atrribute-X| add custom attributes as extra columns in your data stream table | {"X-Wandb-Attribute-chatbot_version" : "0.0.0"}| `-H X-Wandb-Attribute-chatbot_version: 0.0.0` | N/A |
|X-Wandb-Client-Id| set this to group related requests together | {"X-Wandb-Client-Id" : "user_A_bottest"}| `-H X-Wandb-Client: user_A_bottest` | unique Client Id for each request |
