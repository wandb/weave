# Monitor & Visualize LLM Usage with Weave

These example notebooks demonstrate LLM monitoring with Weave.
Easily track, visualize, and understand LLM usage across your organization.
Maintain data privacy and control by leveraging W&B's [hosting options](https://docs.wandb.ai/guides/hosting) and data access at the project/team level.

## Notebooks

- [OpenAI Monitoring Demo](./openai_client_quickstart.ipynb): create, explore, and share OpenAI Monitoring Boards in Weave
- OpenAI Proxy Quickstart: set up a proxy to monitor OpenAI API calls
  - [Enterprise Mode OpenAI Proxy Quickstart](./openai_proxy_quickstart_enterprise_mode.ipynb) - Quickstart designed for enterprise users
  - [General OpenAI Proxy Quickstart](./openai_proxy_quickstart.ipynb) - Quickstart designed for non-enterprise / free users

<img src="../../../docs/assets/mini_prodmon_overview.gif" width="65%">

## OpenAI Integration

There are two main ways to authenticate OpenAI API calls so you can view them in a monitoring board.

### OpenAI API

1. Set your OPENAI_API_KEY in your environment/script/notebook (e.g. via `os.environ["OPENAI_API_KEY"]`).
2. Import openai as follows: `from weave.legacy.monitoring import openai`.
3. Make calls via the OpenAI SDK as usual.

See details and create an interactive board in the [OpenAI monitoring notebook](./openai_client_quickstart.ipynb).

### OpenAI Proxy

To log all calls made via an OpenAI proxy:

1. Find your wandb API key: for the public cloud instance, this will be at [wandb.ai/authorize](https://wandb.ai/authorize). On other instances, append "/authorize" to the base url of your instance.
2. Find [your OpenAI API key](https://platform.openai.com/account/api-keys).
3. Set your OPENAI_API_KEY to these two keys joined by ":", i.e. wandb_api_key:openai_api_key.
4. Change the OpenAI base url to `https://proxy.wandb.ai/proxy/openai/v1` for the public cloud instance (or replace `wandb.ai` with the base url for your instance).
5. Optionally set headers on each call to customize the wandb entity, project, and other aspects of logging (see the table below for details).
6. Call OpenAI via the OpenAI SDK or CURL from the base url.

Try some calls from the [proxy quickstart notebook](./openai_proxy_quickstart.ipynb).

### OpenAI Proxy Headers

You can configure where your data is streamed and stored via proxy headers. For OpenAI SDK calls, pass a dictionary of "header name" keys to "header value" values in the `headers` argument.
For CURL, add each header as an argument flag in the CURL command with the syntax `-H header_name: header_value`.

All these headers are optional. By default, your request data will be logged to the `openai` stream in a `monitoring` project under your default wandb entity. You can navigate to all the stream tables and boards from the browser in the Weave home page on your wandb instance, which lists avaiable entities, then projects, then any existing Boards and Tables saved in those projects.

If you specify a project name or stream name that does not yet exist under the given wandb entity, a new instance will be created.
If you specify a wandb entity to which you do not have access, no data will be logged.

The last header type, `X-Wandb-Attribute-`, lets you add custom attribute fields and values to any call. For example, logging `X-Wandb-Attribute-my_attr` : "my_attr_value" will add a column named `attributes.my_attr` to the stream table and store `my_attr_value` in the row for this call.

| Header name        | Description                                                      | SDK Example                                                                                   | CURL Example                                                                                 | Default setting                          |
| ------------------ | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------- |
| X-Wandb-Entity     | Set the wandb entity for this call                               | `{"X-Wandb-Entity": "my_dream_team"}`                                                         | `-H "X-Wandb-Entity: my_dream_team"`                                                         | Your default entity on your W&B instance |
| X-Wandb-Project    | Set the wandb project name for this call (creates this project)  | `{"X-Wandb-Project": "my_dream_llm"}`                                                         | `-H "X-Wandb-Project: my_dream_llm"`                                                         | monitoring                               |
| X-Wandb-Stream     | Set the StreamTable name for this call                           | `{"X-Wandb-Stream": "my_chatbot_test"}`                                                       | `-H "X-Wandb-Stream: my_chatbot_test"`                                                       | openai                                   |
| X-Wandb-Client-Id  | Set this to group related requests together                      | `{"X-Wandb-Client-Id": "user_A_bottest"}`                                                     | `-H "X-Wandb-Client-Id: user_A_bottest"`                                                     | unique client id for each request        |
| X-Wandb-Attribute- | Add custom attributes as extra columns in your data stream table | `{"X-Wandb-Attribute-chatbot_name": "wandbot", "X-Wandb-Attribute-chatbot_version": "0.0.0"}` | `-H "X-Wandb-Attribute-chatbot_name: wandbot" -H "X-Wandb-Attribute-chatbot_version: 0.0.0"` | none                                     |
