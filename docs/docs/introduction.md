---
slug: /
sidebar_position: 1
hide_table_of_contents: true

---

# Introduction

**Weave** is a lightweight toolkit for tracking and evaluating LLM applications, built by Weights & Biases.

Our goal is to bring rigor, best-practices, and composability to the inherently experimental process of developing AI applications, without introducing cognitive overhead.

**[Get started](/quickstart)** by decorating Python functions with `@weave.op()`. 

![Weave Hero](../static/img/weave-hero.png)

Seriously, try the 🍪 **[quickstart](/quickstart)** 🍪 or <a class="vertical-align-colab-button" target="_blank" href="http://wandb.me/weave_colab"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

You can use Weave to:
- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production


## Key concepts

Weave's **core types** layer contains everything you need for organizing Generative AI projects, with built-in lineage, tracking, and reproducibility.

  - **[Datasets](/guides/core-types/datasets)**: Version, store, and share rich tabular data.
  - **[Models](/guides/core-types/models)**: Version, store, and share parameterized functions.
  - **[Evaluations](/guides/core-types/evaluations)**: Test suites for AI models.
  - [soon] Agents: ...

Weave's **tracking** layer brings immutable tracing and versioning to your programs and experiments.

  - **[Objects](/guides/tracking/objects)**: Weave's extensible serialization lets you easily version, track, and share Python objects.
  - **[Ops](/guides/tracking/ops)**: Versioned, reproducible functions, with automatic tracing.
  - **[Tracing](/guides/tracking/tracing)**: Automatic organization of function calls and data lineage.

Weave's **integrations** is a batteries-included experience for other libraries, systems, and best practices.

  - **[OpenAI](/guides/integrations/openai)**: automatic tracking for openai api calls
  - [soon] Langchain auto-logging
  - [soon] llama-index auto-logging

Weave's **tools** layer contains utilities for making use of Weave objects.
  
  - **[Serve](/guides/tools/serve)**: FastAPI server for Weave Ops and Models
  - **[Deploy](/guides/tools/deploy)**: Deploy Weave Ops and Models to various targets




## What's next?

Try the [Quickstart](/quickstart) to see Weave in action.
