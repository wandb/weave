# Microsoft Azure

Weights & Biases (W&B) Weave integrates with Microsoft Azure OpenAI services, helping teams to optimize their Azure AI applications. Using W&B, you can 

:::tip
For the latest tutorials, visit [Weights & Biases on Microsoft Azure](https://wandb.ai/site/partners/azure).
:::

## Getting started

To get started using Azure with Weave, simply decorate the function(s) you want to track with `weave.op()`.

```python
@weave.op()
def call_azure_chat(model_id: str, messages: list, max_tokens: int = 1000, temperature: float = 0.5):
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    return {"status": "success", "response": response.choices[0].message.content}

```

## Learn more

Learn more about advanced Azure with Weave topics using the resources below.

### Use the Azure AI Model Inference API with Weave

Learn how to use the [Azure AI Model Inference API] with Weave to gain insights into Azure models in [this guide](https://wandb.ai/byyoung3/ML-NEWS2/reports/A-guide-to-using-the-Azure-AI-model-inference-API--Vmlldzo4OTY1MjEy#tutorial:-implementing-azure-ai-model-inference-api-with-w&b-weave-).

### Trace Azure OpenAI models with Weave

Learn how to trace Azure OpenAI models using Weave in [this guide](https://wandb.ai/a-sh0ts/azure-weave-cookbook/reports/How-to-use-Azure-OpenAI-and-Azure-AI-Studio-with-W-B-Weave--Vmlldzo4MTI0NDgy).  
