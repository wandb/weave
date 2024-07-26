# Google Gemini

Google offers two ways of calling Gemini via API:

1. Via the Vertex APIs ([docs](https://cloud.google.com/vertexai/docs))
2. Via the Gemini API ([docs](https://ai.google.dev/gemini-api/docs/quickstart?lang=python))

## Vertex API

Full Weave support for the `Vertex AI SDK` python package is currently in development, however there is a way you can integrate Weave with the Vertex API. 

Vertex API supports OpenAI SDK compatibility ([docs](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/call-gemini-using-openai-library)), and if this is a way you build your application, Weave will automatically track your LLM calls via our [OpenAI](/guides/integrations/openai) SDK integration.

\* Please note that some features may not fully work as Vertex API doesn't implement the full OpenAI SDK capabilities.

## Gemini API

:::info

Weave native client integration with the `google-generativeai` python package is currently in development
:::

While we build the native integration with the Gemini API native python package, you can easily integrate Weave with the Gemini API yourself simply by initializing Weave with `weave.init('<your-project-name>')` and then wrapping the calls that call your LLMs with `weave.op()`. See our guide on [tracing](/guides/tracking/tracing) for more details.
