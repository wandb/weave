# Local Models

Many developers download and run open source models like LLama-3, Mixtral, Gemma, Phi and more locally. There are quite a few ways of running these models locally and Weave supports a few of them out of the box, as long as they support OpenAI SDK compatibility.

## Wrap local model functions with `@weave.op()`

You can easily integrate Weave with any LLM yourself simply by initializing Weave with `weave.init('<your-project-name>')` and then wrapping the calls to your LLMs with `weave.op()`. See our guide on [tracing](/guides/tracking/tracing) for more details.

## Updating your OpenAI SDK code to use local models

All of the frameworks of services that support OpenAI SDK compatibility require a few minor changes.

First and most important, is the `base_url` change during the `openai.OpenAI()` initialization.

```python
client = openai.OpenAI(
    api_key='fake',
    base_url="http://localhost:1234",
)
```

In the case of local models, the `api_key` can be any string but it should be overridden, as otherwise OpenAI will try to use it from environment variables and show you an error.

## OpenAI SDK supported Local Model runners

Here's a list of apps that allows you to download and run models from Hugging Face on your computer, that support OpenAI SDK compatibility.

1. Nomic [GPT4All](https://www.nomic.ai/gpt4all) - support via Local Server in settings ([FAQ](https://docs.gpt4all.io/gpt4all_help/faq.html))
1. [LMStudio](https://lmstudio.ai/) - Local Server OpenAI SDK support [docs](https://lmstudio.ai/docs/local-server)
1. [Ollama](https://ollama.com/) - [Experimental Support](https://github.com/ollama/ollama/blob/main/docs/openai.md) for OpenAI SDK
1. llama.cpp via [llama-cpp-python](https://llama-cpp-python.readthedocs.io/en/latest/server/) python package
1. [llamafile](https://github.com/Mozilla-Ocho/llamafile#other-example-llamafiles) - `http://localhost:8080/v1` automatically supports OpenAI SDK on Llamafile run
