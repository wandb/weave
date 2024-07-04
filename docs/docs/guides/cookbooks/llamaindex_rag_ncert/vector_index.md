# Building a data ingestion pipeline and vector store

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/00_vector_index.ipynb)

## Install the dependencies

First, let us install all the libraries that we would need to build the application.

```shell
pip install -qU rich
pip install -qU wandb weave
pip install -qU llama-index
pip install -qU llama-index-embeddings-huggingface llama-index-llms-groq
```

## Loading the Data

The first step in building our RAG pipeline would be to load data. In our case this consist of the chapter-wise PDF documents from the [Flamingo textbook](https://ncert.nic.in/textbook.php?lefl1=0-13) open-sourced by NCERT. For ease of use, we have uploaded the PDFs to our W&B project as a dataset artifact. We can fetch the artifact using the following code snippet:

```python
import wandb

# initialize a W&B run
wandb.init(project="groq-rag", job_type="build-vector-index")

# Fetch the W&B artifact containing the chapter-wise PDF docs
artifact = wandb.use_artifact(
    "geekyrakshit/groq-rag/ncert-flamingoes:latest", type="dataset"
)
artifact_dir = artifact.download()
```

Next we're going to use the [`SimpleDirectoryReader`](https://docs.llamaindex.ai/en/stable/module_guides/loading/simpledirectoryreader/?source=post_page-----b1709f770f55--------------------------------) data loader from LlamaIndex to load our PDF files.

```python
# Load the documents from the artifact by simply passing the
# `artifact_dir` to `SimpleDirectoryReader`.
docs_path = os.path.join(artifact_dir, "prose", "chapters")
reader = SimpleDirectoryReader(input_dir=docs_path)

# Call `reader.load_data` to load the data
documents = reader.load_data(num_workers=4, show_progress=True)
```

## Building the Vector Store

### The Vector Embedding Model

Vector embeddings are essential in a RAG pipeline enabling efficient and semantically meaningful information retrieval from large datasets. Llamaindex offers a bundle of embedding model options ranging from both open-sourced models & LLM vendors. In this recipe, we're going to use the `BAAI/bge-small-en-v1.5` model from HuggingFace Hub as our embedding model using [`HuggingFaceEmbedding`](https://docs.llamaindex.ai/en/stable/examples/embeddings/huggingface/) from Llamaindex.

```python
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
```
### Chunking

Chunking plays a crucial role in a RAG pipeline by breaking down large documents or texts into smaller, manageable pieces or "chunks." This process allows the retrieval system to efficiently handle and search through extensive information by focusing on these smaller units rather than entire documents.

In this recipe, we're going to use **Semantic chunking** proposed by [Greg Kamradt](https://x.com/GregKamradt) in his video tutorial on [5 levels of embedding chunking](https://www.youtube.com/watch?v=8OJC21T2SL4&t=1933s), using the [`SemanticSplitterNodeParser`](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/?h=semanticsplitternodeparser#semanticsplitternodeparser) from LlamaIndex.

```python
from llama_index.core.node_parser import SemanticSplitterNodeParser


splitter = SemanticSplitterNodeParser(
    buffer_size=1,
    breakpoint_percentile_threshold=95,
    embed_model=embed_model
)
nodes = splitter.get_nodes_from_documents(documents)
```
