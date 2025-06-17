import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Weights & Biases (W&B) Inference Service

_Weights & Biases (W&B) Inference_ provides access to leading open-source foundation models via the W&B Weave UI and an OpenAI-compliant API. With W&B Inference, you can:

- Develop AI applications and agents without signing up for a hosting provider or self-hosting a model.
- Try the supported models in the W&B Weave Playground.

:::tip
For a limited time, W&B Inference is included in your free tier. For more information, visit [https://wandb.ai/site/inference](https://wandb.ai/site/inference).
:::

Using Weave, you can trace, evaluate, monitor, and iterate on your W&B Inference-powered applications.

| Model            | Type(s)       | Context Window | Parameters                  | Description                                                                 |
|------------------|---------------|----------------|-----------------------------|-----------------------------------------------------------------------------|
| DeepSeek R1-0528 | Text          | 161K           | 37B - 680B (Active - Total) | Optimized for precise reasoning tasks including complex coding, math, and structured document analysis. |
| DeepSeek V3-0324 | Text          | 161K           | 37B - 680B (Active - Total) | Robust Mixture-of-Experts model tailored for high-complexity language processing and comprehensive document analysis. |
| Llama 3.1 8B     | Text          | 128K           | 8B (Total)                  | Efficient conversational model optimized for responsive multilingual chatbot interactions. |
| Llama 3.3 70B    | Text          | 128K           | 70B (Total)                 | Multilingual model excelling in conversational tasks, detailed instruction-following, and coding. |
| Llama 4 Scout    | Text, Vision  | 64K            | 17B - 109B (Active - Total) | Multimodal model integrating text and image understanding, ideal for visual tasks and combined analysis. |
| Phi 4 Mini       | Text          | 128K           | 3.8B (Active - Total)       | Compact, efficient model ideal for fast responses in resource-constrained environments. |

This guide provides the following information:

- [Prerequisites](#prerequisites)
  - [Additional prerequisites for using the API via Python](#additional-prerequisites-for-using-the-api-via-python)
- [API specification](#api-specification)
  - [Endpoint](#endpoint)
  - [Available methods](#available-methods)
      - [Chat completions](#chat-completions)
      - [List supported models](#list-supported-models)
  - [Usage examples](#usage-examples)
      - [List available models](#list-available-models)
      - [Llama 3.1 8B](#llama-31-8b)
      - [DeepSeek V3-0324](#deepseek-v3-0324)
      - [Llama 3.3 70B](#llama-33-70b)
      - [DeepSeek R1-0528](#deepseek-r1-0528)
      - [Llama 4 Scout](#llama-4-scout)
      - [Phi 4 Mini](#phi-4-mini)
- [UI](#ui)
  - [Access the Inference service](#access-the-inference-service)
      - [From the Inference tab](#from-the-inference-tab)
      - [From the Playground tab](#from-the-playground-tab)
  - [Try a model in the Playground](#try-a-model-in-the-playground)
  - [Compare multiple models](#compare-multiple-models)
      - [Access the Compare view from the Inference tab ](#access-the-compare-view-from-the-inference-tab)
      - [Access the Compare view from the Playground tab](#access-the-compare-view-from-the-playground-tab)
  - [View billing information](#view-billing-and-usage-information)
- [Usage information and limits ](#usage-information-and-limits)
  - [Geographic restrictions](#geographic-restrictions)
  - [Concurrency limits](#concurrency-limits)
  - [Pricing](#pricing)
- [API errors](#api-errors)
- [FAQ](#faq)

## Prerequisites

The following prerequisites are required to access the W&B Inference service via the API or the W&B Weave UI.

1. A W&B account. Sign up [here](https://app.wandb.ai/login?signup=true&_gl=1*1yze8dp*_ga*ODIxMjU5MTk3LjE3NDk0OTE2NDM.*_ga_GMYDGNGKDT*czE3NDk4NDYxMzgkbzEyJGcwJHQxNzQ5ODQ2MTM4JGo2MCRsMCRoMA..*_ga_JH1SJHJQXJ*czE3NDk4NDU2NTMkbzI1JGcxJHQxNzQ5ODQ2MTQ2JGo0NyRsMCRoMA..*_gcl_au*MTE4ODk1MzY1OC4xNzQ5NDkxNjQzLjk1ODA2MjQwNC4xNzQ5NTgyMTUzLjE3NDk1ODIxNTM.).
2. A W&B API key. Get your API key at [https://wandb.ai/authorize](https://wandb.ai/authorize).
3. A W&B project. 
4. If you are using the Inference service via Python, see [Additional prerequisites for using the API via Python](#additional-prerequisites-for-using-the-api-via-python).

### Additional prerequisites for using the API via Python

To use the Inference API via Python, first complete the general prerequisites. Then, install the `openai` and `weave` libraries in your local environment:

```bash
pip install openai weave
```

:::note
The `weave` library is only required if you'll be using Weave to trace your LLM applications. For information on getting started with Weave, see the [Weave Quickstart](../../quickstart.md).
:::

## API specification

The following section provides API specification information and API usage examples. 

- [Endpoint](#endpoint)
- [Available methods](#available-methods)
- [Usage examples](#usage-examples)

### Endpoint

The Inference service can be accessed via the following endpoint:

```plaintext
https://api.inference.wandb.ai/v1
```

:::important
To access this endpoint, you must have a valid W&B account with Inference service credits allocated, and a valid W&B API key.
:::

### Available methods

#### Chat completions

The primary API method available is `/chat/completions`, which supports OpenAI-compatible request formats for sending messages to a supported model and receiving a completion. For usage examples involving specific models, see the [API usage examples](#usage-examples)

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-api-key>" \
      -H "OpenAI-Project: <your-entity>/<your-project>" \
      -d '{
        "model": "<model-id>",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    # Initialize the OpenAI-compatible client
    client = openai.OpenAI(
        base_url='https://api.inference.wandb.ai/v1',
        api_key="<your-api-key>"
    )

    # Call the chat completion endpoint
    response = client.chat.completions.create(
        model="<model-id>",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
        extra_headers={
            "OpenAI-Project": "<your-entity>/<your-project>"
        },
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### List supported models

You can also programmatically list the supported models with the `\models` method. For usage information, see [List available models](#list-available-models).

### Usage examples

This section describes several ways to interact with the W&B Inference service:

- [List the available models using the API](#list-available-models).
- [Chat completion with Llama 3.1 8B](#llama-31-8b)
- [Chat completion with DeepSeek V3-0324](#deepseek-v3-0324)
- [Chat completion with Llama 3.3 70B](#llama-33-70b)
- [Chat completion with DeepSeek R1-0528](#deepseek-r1-0528)
- [Chat completion with Llama 4 Scout](#llama-4-scout)
- [Chat completion with Phi 4 Mini](#phi-4-mini)

#### Using Weave wuth the infernce service

Use Weave with the Inference service to [trace model calls](../tracking/tracing.mdx), [evaluate performance](../core-types/evaluations.md), and [publish a leaderboard](../core-types/leaderboards.md). The following Python code sample  compares two models on a simple question–answer dataset.

```python
import os
import asyncio
import openai
import weave
from weave.flow import leaderboard
from weave.trace.ref_util import get_ref

weave.init("inference-demo")

dataset = [
    {"input": "What is 2 + 2?", "target": "4"},
    {"input": "Name a primary color.", "target": "red"},
]

@weave.op
def exact_match(target: str, output: str) -> float:
    return float(target.strip().lower() == output.strip().lower())

class WBInferenceModel(weave.Model):
    model: str

    @weave.op
    def predict(self, prompt: str) -> str:
        client = openai.OpenAI(
            base_url="https://api.inference.wandb.ai/v1",
            api_key=os.environ["WANDB_API_KEY"],
            project="my-team/my-project",
        )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

llama = WBInferenceModel(model="meta-llama/Llama-3.1-8B-Instruct")
deepseek = WBInferenceModel(model="deepseek-ai/DeepSeek-V3-0324")

evaluation = weave.Evaluation(
    name="QA",
    dataset=dataset,
    scorers=[exact_match],
)

async def run_eval():
    await evaluation.evaluate(llama)
    await evaluation.evaluate(deepseek)

asyncio.run(run_eval())

spec = leaderboard.Leaderboard(
    name="Inference Leaderboard",
    description="Compare models on a QA dataset",
    columns=[
        leaderboard.LeaderboardColumn(
            evaluation_object_ref=get_ref(evaluation).uri(),
            scorer_name="exact_match",
            summary_metric_path="mean",
        )
    ],
)

weave.publish(spec)
print(leaderboard.get_leaderboard_results(spec, weave.WeaveClient()))
```

Open the **Leaders** tab in the Weave UI to [view the leaderboard](../core-types/leaderboards.md)

#### List available models

Use the API to query all currently available models and their IDs. This is useful for selecting models dynamically or inspecting what's available in your environment.

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/models \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <your-entity>/<your-project>" \
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    client = openai.OpenAI(
        base_url="https://api.inference.wandb.ai/v1",
        api_key="<your-apikey>"
    )

    response = client.models.list(
        extra_headers={
            "OpenAI-Project": "hello-world-team/new-inference-project"
        }
    )

    for model in response.data:
        print(model.id)
    ```
  </TabItem>
</Tabs>

#### Llama 3.1 8B

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### DeepSeek V3-0324

<Tabs groupId="programming-language">
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "deepseek-ai/DeepSeek-V3-0324",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3-0324",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### Llama 3.3 70B

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### DeepSeek R1-0528

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "deepseek-ai/DeepSeek-R1-0528",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python 
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-0528",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### Llama 4 Scout

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>

#### Phi 4 Mini

<Tabs groupId="programming-language" queryString>
  <TabItem value="bash" label="Bash" default>
    ```bash
    curl https://api.inference.wandb.ai/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your-apikey>" \
      -H "OpenAI-Project: <team>/<project>" \
      -d '{
        "model": "microsoft/Phi-4-mini-instruct",
        "messages": [
          { "role": "system", "content": "You are a helpful assistant." },
          { "role": "user", "content": "Tell me a joke." }
        ]
      }'
    ```
  </TabItem>
  <TabItem value="python" label="Python">
    ```python 
    import openai

    client = openai.OpenAI(
        # The custom base URL points to W&B Inference
        base_url='https://api.inference.wandb.ai/v1',

        # Get your API key from https://wandb.ai/authorize
        # Consider setting it in the environment as OPENAI_API_KEY instead for safety
        api_key="<your-apikey>",

        # Team and project are required for usage tracking
        project="<team>/<project>",
    )

    response = client.chat.completions.create(
        model="microsoft/Phi-4-mini-instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
    )

    print(response.choices[0].message.content)
    ```
  </TabItem>
</Tabs>



## UI

The following section describes how to use the Inference service from the W&B UI. Before you can access the Inference service via the UI, complete the [prerequisites](#prerequisites).

### Access the Inference service

You can access the Inference service via the Weave UI from two different locations:

- [From the Inference tab](#from-the-inference-tab)
- [From the Playground tab](#from-the-playground-tab)

#### From the Inference tab

1. Navigate to your W&B account at [https://wandb.ai/](https://wandb.ai/).
2. From the left sidebar, select **Inference**. A page with available models and model information displays.

#### From the Playground tab

1. From the left sidebar, select **Playground**. The Playground chat UI displays.
2. From the LLM dropdown list, mouseover **W&B Inference**. A dropdown with available W&B Inference models displays to the right.
3. From the W&B Inference models dropdown, you can:
   - Click the name of any available model to [try it in the Playground](#try-a-model-in-the-playground).
   - Mouseover the information icon to the right of the model name for model information. You can also click the link to [view detailed model information](#view-model-information).
   - Compare one or models in the Playground

### Try a model in the Playground

Once you've [selected a model using one of the access options](#access-the-inference-service), you can try the model in Playground. The following actions are available:

- [Customize model settings and parameters](../tools/playground.md#customize-settings)
- [Add, retry, edit, and delete messages](../tools/playground.md#message-controls) 
- [Save and reuse a model with custom settings](../tools/playground.md#saved-models)
- [Compare multiple models](#compare-multiple-models)

### Compare multiple models

You can compare multiple Inference models in the Playground. The Compare view can be accessed from two different locations:

- [Access the Compare view from the Inference tab ](#access-the-compare-view-from-the-inference-tab)
- [Access the Compare view from the Playground tab](#access-the-compare-view-from-the-playground-tab)

#### Access the Compare view from the Inference tab 

1. From the left sidebar, select **Inference**. A page with available models and model information displays.
2. To select models for comparison, click anywhere on a model card (except for the model name). The border of the model card is highlighted in blue to indicate the selection.
3. Repeat step 2 for each model you want to compare.
4. In any of the selected cards, click the **Compare N models in the Playground** button (`N` is the number of models you are comparing. For example, when 3 models are selected, the button displays as **Compare 3 models in the Playground**). The comparison view opens. 

Now, you can compare models in the Playground, and use any of the features described in [Try a model in the Playground](#try-a-model-in-the-playground).

#### Access the Compare view from the Playground tab

1. From the left sidebar, select **Playground**. The Playground chat UI displays.
2. From the LLM dropdown list, mouseover **W&B Inference**. A dropdown with available W&B Inference models displays to the right.
3. From the dropdown, select **Compare**. The **Inference** tab displays.
4. To select models for comparison, click anywhere on a model card (except for the model name). The border of the model card is highlighted in blue to indicate the selection.
5. Repeat step 4 for each model you want to compare.
6. In any of the selected cards, click the **Compare N models in the Playground** button (`N` is the number of models you are comparing. For example, when 3 models are selected, the button displays as **Compare 3 models in the Playground**). The comparison view opens. 

Now, you can compare models in the Playground, and use any of the features described in [Try a model in the Playground](#try-a-model-in-the-playground).

### View billing and usage information

1. In the W&B UI, navigate to the W&B **Billing** page.
2. In the bottom righthand corner, the Inference billing information card is displayed. From here, you can click the **View usage** button in the Inference billing information card to view your usage over time.

## Usage information and limits 

The following section describes important usage information and limits. Familiarize yourself with this information before using the service.

### Geographic restrictions

The Inference service is only accessible from supported geographic locations. For more information, see the [Terms of Service](https://docs.coreweave.com/docs/policies/terms-of-service/terms-of-use#geographic-restrictions).

### Concurrency limits

To ensure fair usage and stable performance, the W&B Inference API enforces rate limits at the user and project level. These limits help:

- Prevent misuse and protect API stability
- Ensure access for all users
- Manage infrastructure load effectively

If a rate limit is exceeded, the API will return a `429 Concurrency limit reached for requests ` response. To resolve this error, reduce the number of concurrent requests. 

### Pricing

For model pricing information, visit [http://wandb.com/site/pricing/inference](http://wandb.com/site/pricing/inference).

## API errors

| Error Code | Message                                                                     | Cause                                           | Solution                                                                               |
| ---------- | --------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------- |
| 401        | Invalid Authentication                                                      | Invalid authentication credentials or your W&B project entity and/or name are incorrect.              | Ensure the correct API key is being used and/or that yourW&B project name and entity are correct.                                              |
| 403        | Country, region, or territory not supported                                 | Accessing the API from an unsupported location. | Please see [Geographic restrictions](#geographic-restrictions)                                       |
| 429        | Concurrency limit reached for requests                                      | Too many concurrent requests.                   | Reduce the number of concurrent requests.               |
| 429        | You exceeded your current quota, please check your plan and billing details | Out of credits or reached monthly spending cap. | Purchase more credits or increase your limits.                       |
| 500        | The server had an error while processing your request                       | Internal server error.                          | Retry after a brief wait and contact support if it persists. |
| 503        | The engine is currently overloaded, please try again later                  | Server is experiencing high traffic.            | Retry your request after a short delay.                                                |
