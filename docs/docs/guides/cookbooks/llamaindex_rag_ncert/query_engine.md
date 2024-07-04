# Building the Query Engine

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/01_rag_engine.ipynb)

## Using Weave to trace LlamaIndex calls

Weave is integrated with LlamaIndex to simplify the tracking and logging of all LlamaIndex calls. To get started, simply call `weave.init()` at the beginning of your script.

```python
import weave

weave.init(project_name="groq-rag")
```

## Using GroqCloud LLMs with LlamaIndex

GroqCloud is an LLM cloud service provider that lets us use open-source LLMs like Llama3, Mixtral, Gemma, etc. The GroqCloud models run on their propreitary **Language Processing Unit** or **LPU** which has a deterministic, single core streaming architecture that sets the standard for genAI inference speed with predictable and repeatable performance for any given workload.

We can use GroqCloud models with LlamaIndex:

```python
import os
from llama_index.llms.groq import Groq

llm = Groq(
    model="mixtral-8x7b-32768",
    api_key=os.environ.get("GROQ_API_KEY")
)
```

## Fetching and Loading the Vector Store Index

First we create a service context for configuring the vector index store.

```python
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

service_context = ServiceContext.from_defaults(
    embed_model=embed_model, llm=llm
)
```

Next, we fetch the W&B vector index artifact and load back the index.

```python
import wandb

# We use `wandb.Api` to fetch the artifacts, this ensures that we don't
# create a new W&B run for every query. The queries will be tracked by Weave.
artifact = wandb.Api().artifact(
    "geekyrakshit/groq-rag/ncert-flamingoes-prose-embeddings:latest"
)
artifact_dir = artifact.download()

# Load the vector index from storage
storage_context = StorageContext.from_defaults(
    persist_dir=artifact_dir
)
index = load_index_from_storage(
    storage_context, service_context=service_context
)
```
