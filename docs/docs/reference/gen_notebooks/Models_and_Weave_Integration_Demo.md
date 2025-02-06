---
title: Weave with W&B Models
---

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/Models_and_Weave_Integration_Demo.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/Models_and_Weave_Integration_Demo.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


# Use Weave with W&B Models

This notebook demonstrates how to use W&B Weave with [W&B Models](https://docs.wandb.ai/guides/) using the scenario of two different teams working on an end-to-end implementation of a Retrieval-Augmented Generation (RAG) application, from fine-tuning the model to building an app around the model. Specifically, the Model Team fine-tunes a new Chat Model (Llama 3.2),and saves it to the [W&B Models Registry](https://docs.wandb.ai/guides/registry/). Then, the App Team retrieves the fine-tuned Chat Model from the Registry, and uses Weave to create and evaluate a RAG chatbot application

The guide walks you through the following steps, which are the same steps that the teams in the described scenario would follow:

1. Downloading a fine-tuned Llama 3.2 model registered in [W&B Models Registry](https://docs.wandb.ai/guides/registry/)
2. Implementing a RAG application using the fine-tuned Llama 3.2 model 
3. Tracking and evaluating the RAG application using Weave
4. Registering the improved RAG app to Registry

Find the public workspace for both W&B Models and W&B Weave [here](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/evaluations).

<img src="https://github.com/NiWaRe/agent-dev-collection/blob/master/screenshots/weave_models_workflow.jpeg?raw=true"  alt="Weights & Biases" />






## Prerequisites

First, install the necessary libraries, set up API keys, log in to W&B, and create a new W&B project.

1. Install `weave`, `pandas`, `unsloth`, `wandb`, `litellm`, `pydantic`, `torch`, and `faiss-gpu` using `pip`.


```python
%%capture
!pip install weave wandb pandas pydantic litellm faiss-gpu
```


```python
%%capture
!pip install unsloth
# Also get the latest nightly Unsloth!
!pip uninstall unsloth -y && pip install --upgrade --no-cache-dir "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

2. Add the necessary API keys from your environment.


```python
import os
from google.colab import userdata

os.environ["WANDB_API_KEY"] = userdata.get('WANDB_API_KEY')  # W&B Models and Weave
os.environ["OPENAI_API_KEY"] = userdata.get('OPENAI_API_KEY') # OpenAI - for retrieval embeddings
os.environ["GEMINI_API_KEY"] = userdata.get('GEMINI_API_KEY') # Gemini - for the base chat model
```

3. Log in to W&B, and create a new project.


```python
import wandb
import weave
import pandas as pd

wandb.login()

PROJECT = "weave-cookboook-demo"
ENTITY = "wandb-smle"

weave.init(ENTITY+"/"+PROJECT)
```

##  Download `ChatModel` from Models Registry and implement `UnslothLoRAChatModel`

In our scenario, the Llama-3.2 model has already been fine-tuned by the Model Team using the `unsloth` library for performance optimization, and is [available in the W&B Models Registry](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/object-versions?filter=%7B%22objectName%22%3A%22RagModel%22%7D&peekPath=%2Fwandb-smle%2Fweave-rag-experiments%2Fobjects%2FChatModelRag%2Fversions%2F2mhdPb667uoFlXStXtZ0MuYoxPaiAXj3KyLS1kYRi84%3F%26). In this step, we'll retrieve the fine-tuned [`ChatModel`](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/object-versions?filter=%7B%22objectName%22%3A%22RagModel%22%7D&peekPath=%2Fwandb-smle%2Fweave-rag-experiments%2Fobjects%2FChatModelRag%2Fversions%2F2mhdPb667uoFlXStXtZ0MuYoxPaiAXj3KyLS1kYRi84%3F%26) from the Registry and convert it into a `weave.Model` to make it compatible with the [`RagModel`](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/object-versions?filter=%7B%22objectName%22%3A%22RagModel%22%7D&peekPath=%2Fwandb-smle%2Fweave-cookboook-demo%2Fobjects%2FRagModel%2Fversions%2FcqRaGKcxutBWXyM0fCGTR1Yk2mISLsNari4wlGTwERo%3F%26). 

:::important
The `RagModel` referenced below is a top-level `weave.Model` that can be considered a complete RAG Application. It contains a `ChatModel`, vector database, and a prompt. The `ChatModel` is also a `weave.Model`, which contains code to download an artifact from the W&B Registry. `ChatModel` can be changed modularly to support any kind of other LLM chat model as part of the `RagModel`. For more information, [view the model in Weave](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/evaluations?peekPath=%2Fwandb-smle%2Fweave-cookboook-demo%2Fobjects%2FRagModel%2Fversions%2Fx7MzcgHDrGXYHHDQ9BA8N89qDwcGkdSdpxH30ubm8ZM%3F%26).
:::

To load the `ChatModel`, `unsloth.FastLanguageModel` or `peft.AutoPeftModelForCausalLM` with adapters are used, enabling efficient integration into the app. After downloading the model from the Registry, you can set up the initialization and prediction logic by using the `model_post_init` method. The required code for this step is available in the **Use** tab of the Registry and can be copied directly into your implementation

The code below defines the `UnslothLoRAChatModel` class to manage, initialize, and use the fine-tuned Llama-3.2 model retrieved from the W&B Models Registry. `UnslothLoRAChatModel` uses `unsloth.FastLanguageModel` for optimized inference. The `model_post_init` method handles downloading and setting up the model, while the `predict` method processes user queries and generates responses. To adapt the code for your use case, update the `MODEL_REG_URL` with the correct Registry path for your fine-tuned model and adjust parameters like `max_seq_length` or `dtype` based on your hardware or requirements.



```python
import weave
from pydantic import PrivateAttr
from typing import Any, List, Dict, Optional
from unsloth import FastLanguageModel
import torch

class UnslothLoRAChatModel(weave.Model):
    """
    We define an extra ChatModel class to be able store and version more parameters than just the model name.
    Especially, relevant if we consider fine-tuning (locally or aaS) because of specific parameters.
    """
    chat_model: str
    cm_temperature: float
    cm_max_new_tokens: int
    cm_quantize: bool
    inference_batch_size: int
    dtype: Any
    device: str
    _model: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()

    def model_post_init(self, __context):
      # we can simply paste this from the "Use" tab from the registry
      run = wandb.init(project=PROJECT, job_type="model_download")
      artifact = run.use_artifact(f"{self.chat_model}")
      model_path = artifact.download()

      # unsloth version (enable native 2x faster inference)
      self._model, self._tokenizer = FastLanguageModel.from_pretrained(
          model_name = model_path,
          max_seq_length = self.cm_max_new_tokens,
          dtype = self.dtype,
          load_in_4bit = self.cm_quantize,
      )
      FastLanguageModel.for_inference(self._model)

    @weave.op()
    async def predict(self, query: List[str]) -> dict:
      # add_generation_prompt = true - Must add for generation
      input_ids = self._tokenizer.apply_chat_template(
          query, tokenize = True, add_generation_prompt = True, return_tensors = "pt",
      ).to("cuda")

      output_ids = self._model.generate(
          input_ids = input_ids, max_new_tokens = 64, use_cache = True, temperature = 1.5, min_p = 0.1
      )

      decoded_outputs = self._tokenizer.batch_decode(
          output_ids[0][input_ids.shape[1]:], skip_special_tokens=True
      )

      return ''.join(decoded_outputs).strip()
```


```python
MODEL_REG_URL = "wandb32/wandb-registry-RAG Chat Models/Finetuned Llama-3.2:v3"

max_seq_length = 2048 # Choose any! We auto support RoPE Scaling internally!
dtype = None          # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
load_in_4bit = True   # Use 4bit quantization to reduce memory usage. Can be False.

new_chat_model = UnslothLoRAChatModel(
    name = "UnslothLoRAChatModelRag",
    chat_model = MODEL_REG_URL,
    cm_temperature = 1.0,
    cm_max_new_tokens = max_seq_length,
    cm_quantize = load_in_4bit,
    inference_batch_size = max_seq_length,
    dtype = dtype,
    device = "auto",
)
```


```python
await new_chat_model.predict([{"role": "user", "content": "What is the capital of Germany?"}])
```

## Integrate the new `ChatModel` version into `RagModel`

Building a RAG application from a fine-tuned chat model improves conversational AI by using tailored components without having to rebuild the entire pipeline. In this step, we retrieve the existing `RagModel` from our Weave project and update its `ChatModel` to use the newly fine-tuned model. This seamless swap means that other components like the vector database (VDB) and prompts remain untouched, preserving the application's overall structure while improving performance.

The code below retrieves the `RagModel` object using a reference from the Weave project. The `chat_model` attribute of the `RagModel` is then updated to use the new `UnslothLoRAChatModel` instance created in the previous step. After this, the updated `RagModel` is published to create a new version. Finally, the updated `RagModel` is used to run a sample prediction query, verifying that the new chat model is being used. 



```python
RagModel = weave.ref("weave:///wandb-smle/weave-cookboook-demo/object/RagModel:cqRaGKcxutBWXyM0fCGTR1Yk2mISLsNari4wlGTwERo").get()
```


```python
RagModel.chat_model.chat_model
```


```python
await RagModel.predict("When was the first conference on climate change?")
```


```python
# MAGIC: exchange chat_model and publish new version (no need to worry about other RAG components)
RagModel.chat_model = new_chat_model
```


```python
RagModel.chat_model.chat_model
```


```python
# first publish new version so that in prediction we reference new version
PUB_REFERENCE = weave.publish(RagModel, "RagModel")
```


```python
await RagModel.predict("When was the first conference on climate change?")
```

## Run a `weave.Evaluation` 

In the next step, we evaluate the performance of our updated `RagModel` using an existing `weave.Evaluation`. This process ensures that the new fine-tuned chat model is performing as expected within the RAG application. To streamline integration and enable collaboration between the Models and Apps teams, we log evaluation results for both the model's W&B run and as part of the Weave workspace.

In Models:
- The evaluation summary is logged to the W&B run used to download the fine-tuned chat model. This includes summary metrics and graphs displayed in a [workspace view](https://wandb.ai/wandb-smle/weave-cookboook-demo/workspace?nw=eglm8z7o9) for analysis.
- The evaluation trace ID is added to the run's configuration, linking directly to the Weave page for easier traceability by the Model Team.

In Weave:
- The artifact or registry link for the `ChatModel` is stored as an input to the `RagModel`.
- The W&B run ID is saved as an extra column in the evaluation traces for better context.

The code below demonstrates how to retrieve an evaluation object, execute the evaluation using the updated `RagModel`, and log the results to both W&B and Weave. Ensure that the evaluation reference (`WEAVE_EVAL`) matches your project setup. 



```python
# MAGIC: we can simply get an evaluation with a eval dataset and scorers and use them
WEAVE_EVAL = "weave:///wandb-smle/weave-cookboook-demo/object/climate_rag_eval:ntRX6qn3Tx6w3UEVZXdhIh1BWGh7uXcQpOQnIuvnSgo"
climate_rag_eval = weave.ref(WEAVE_EVAL).get()
```


```python
with weave.attributes({'wandb-run-id': wandb.run.id}):
  # use .call attribute to retrieve both the result and the call in order to save eval trace to Models
  summary, call = await climate_rag_eval.evaluate.call(climate_rag_eval, RagModel)
```


```python
# log to models
wandb.run.log(pd.json_normalize(summary, sep='/').to_dict(orient="records")[0])
wandb.run.config.update({"weave_url": f"https://wandb.ai/wandb-smle/weave-cookboook-demo/r/call/{call.id}"})
wandb.run.finish()
```

## Save the new RAG Model to the Registry

To make the updated `RagModel` available for future use by both the Models and Apps teams, we push it to the W&B Models Registry as a reference artifact.

The code below retrieves the `weave` object version and name for the updated `RagModel` and uses them to create reference links. A new artifact is then created in W&B with metadata containing the model's Weave URL. This artifact is logged to the W&B Registry and linked to a designated registry path.

Before running the code, ensure the `ENTITY` and `PROJECT` variables match your W&B setup, and the target registry path is correctly specified. This process finalizes the workflow by publishing the new `RagModel` to the W&B ecosystem for easy collaboration and reuse.



```python
MODELS_OBJECT_VERSION = PUB_REFERENCE.digest # weave object version
MODELS_OBJECT_NAME = PUB_REFERENCE.name # weave object name
```


```python
models_url = f"https://wandb.ai/{ENTITY}/{PROJECT}/weave/objects/{MODELS_OBJECT_NAME}/versions/{MODELS_OBJECT_VERSION}"
models_link = f"weave:///{ENTITY}/{PROJECT}/object/{MODELS_OBJECT_NAME}:{MODELS_OBJECT_VERSION}"

with wandb.init(project=PROJECT, entity=ENTITY) as run:
  # create new Artifact
  artifact_model = wandb.Artifact(
      name = "RagModel", type = "model", description="Models Link from RagModel in Weave", metadata={'url':models_url}
  )
  artifact_model.add_reference(models_link, name = "model", checksum = False)

  # log new artifact
  run.log_artifact(artifact_model, aliases=[MODELS_OBJECT_VERSION])

  # link to registry
  run.link_artifact(
    artifact_model,
    target_path="wandb32/wandb-registry-RAG Models/RAG Model"
  )
```
