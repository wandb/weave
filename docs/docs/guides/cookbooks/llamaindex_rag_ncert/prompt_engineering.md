# Building a Better Assitant using Prompt Engineering

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/03_prompt_engineering.ipynb)

Now that we have a functional RAG pipeline, let's use some basic prompt engineering to make it a little more helpful. We need our teaching assistant to be able to perform the following tasks:

- emulating the ideal response of a student to a question
- emulating the teacher's response to a question from a student.
- help the teacher grade the answer given by a student to a question.

## Building a Retreiver from the Vector Store Index

Retrievers are responsible for fetching the most relevant context given a user query or chat message. We are going to use the [`as_retriever`](https://docs.llamaindex.ai/en/stable/api_reference/indices/document_summary/?h=as_retriever#llama_index.core.indices.DocumentSummaryIndex.as_retriever) instead of the `as_query_engine` in the previous recipe to build our retriever.

```python
import wandb

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    ServiceContext, StorageContext, load_index_from_storage
)

# fetch vector embeddings artifact
artifact = wandb.Api().artifact(
    "geekyrakshit/groq-rag/ncert-flamingoes-prose-embeddings:latest"
)
artifact_dir = artifact.download()

# define service and storage contexts
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
service_context = ServiceContext.from_defaults(
    embed_model=embed_model, llm=None
)
storage_context = StorageContext.from_defaults(persist_dir=artifact_dir)

# load index from storage
index = load_index_from_storage(
    storage_context, service_context=service_context
)

# build retriever
retreival_engine = index.as_retriever(
    service_context=service_context,
    similarity_top_k=10,
)
```

Now we can use this retriever to retrieve a list of [`NodeWithScore`](https://docs.llamaindex.ai/en/stable/api_reference/schema/?h=nodewithscore#llama_index.core.schema.NodeWithScore) objects which represent units of retrieved text segments. The nodes are arranged in descending order of similarity score, hence we can simply pick the first node in the list as our context.

```
query = """what was the mood in the classroom when M. Hamel gave his last French lesson?"""
response = retreival_engine.retrieve(query)

chapter_name = response[0].node.metadata["file_name"].split(".")[0].replace("_", " ").title()
context = response[0].node.text

rich.print(f"{chapter_name=}")
rich.print(f"{context=}")
```

The output is:

```
chapter_name='The Last Lesson'

context='The Last Lesson /7\nlanguage in the world — the\nclearest, the most logical; that\nwe must guard it among 
us and\nnever forget it, because when a\npeople are enslaved, as long as\nthey hold fast to their language\nit is 
as if they had the key to their\nprison. Then he opened a\ngrammar and read us our lesson.\nI was amazed to see how
well I\nunderstood it. All he said seemed\nso easy, so easy! I think, too, that\nI had never listened so 
carefully,\nand that he had never explained\neverything with so much patience.\nIt seemed almost as if the 
poor\nman wanted to give us all he knew\nbefore going away, and to put it\nall into our heads at one stroke.\nAfter
the grammar , we had a\nlesson in writing. That day M.\nHamel had new copies for us,\nwritten in a beautiful round 
hand\n— France, Alsace, France, Alsace. They looked like little\nflags floating everywhere in the school-room, hung
from\nthe rod at the top of our desks. Y ou ought to have seen how\nevery one set to work, and how quiet it was! 
The only sound\nwas the scratching of the pens over the paper . Once some\nbeetles flew in; but nobody paid any 
attention to them, not\neven the littlest ones, who worked right on tracing their\nfish-hooks, as if that was 
French, too. On the roof the\npigeons cooed very low, and I thought to myself, “Will they\nmake them sing in 
German, even the pigeons?”\nWhenever I looked up from my writing I saw M. Hamel\nsitting motionless in his chair 
and gazing first at one thing,\nthen at another , as if he wanted to fix in his mind just how\neverything looked in
that little school-room. Fancy! For\nforty years he had been there in the same place, with his\ngarden outside the 
window and his class in front of him,\n1.What was Franz expected to\nbe prepared with for school\nthat day?\n2.What
did Franz notice that was\nunusual about the school that\nday?\n3.What had been put up on 
the\nbulletin-board?\nReprint 2024-25'
```
