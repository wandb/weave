# Building an English Teaching Assistant using RAG

A lot of teachers in the education system have to spend a lot of time manually grading and evaluating their students’ answersheets which which takes up a significant chunk of their time and focus from teaching. In this cookbook, we attempt to showcase a recipe to build an assistant to a teacher that can help with the grading of students' assignments and help clarify students' confusions and other questions regarding the syllabus and study material using a Retrieval Augmented Generation (RAG) pipeline built using

- [LlamaIndex](https://www.llamaindex.ai/) as our data framework for building the RAG pipeline.
- [GroqCloud](https://groq.com/) as our LLM vendor.
- [Instructor](https://python.useinstructor.com/) to get structured data from the LLM.
- [Weave](https://wandb.github.io/weave/) for tracking and evaluating LLM application.
- [Weights & Biases Artifacts](https://docs.wandb.ai/guides/artifacts) to manage and version our vector store and evaluation dataset.

We demonstrate the RAG pipeline to act as an assistant to an English teacher teaching the proses from the English textbook [Flamingo](https://ncert.nic.in/textbook.php?lefl1=0-13), which is part of the syllabus of [CBSE](https://www.cbse.gov.in/) board's English syllabus for Class XII.

## Table of Content

| Recipe | Notebook |
|---|---|
| [Building a data ingestion pipeline and vector store](./vector_index.md) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/00_vector_index.ipynb) |
| [Building the Query Engine](./vector_index.md) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/01_rag_engine.ipynb) |
| [Building Task-specific Assistants using Prompt Engineering](./vector_index.md) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/03_prompt_engineering.ipynb) |
| [Building an Evaluation Pipeline](./evaluation.md) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/04_evaluation.ipynb) |
