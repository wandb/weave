---
slug: /
sidebar_position: 1
hide_table_of_contents: true

---

# Introduction

*🍲 This version of Weave is pre-release software. 🍲*

Weave is a toolkit for developing AI-powered applications, built by [Weights & Biases](https://wandb.ai).

Our goal is to bring rigor, best-practices, and composability to the inherently experimental process of developing AI-based software, without introducing cognitive overhead.

Weave's core concept is that as your code executes, it keeps track of function calls and their inputs and outputs. You don't need to learn a declarative language or a complex object hierarchy. Just decorate functions with `@weave.op()` to [get started](/quickstart)

## Why use Weave?

Building applications with large language models is a new style of software development. While these models are incredibly powerful, they are also non-deterministic and therefore tricky to make use of. Weave helps you harness this potential.

You can use Weave to:
- log and debug language model inputs, outputs, and traces
- build rigorous, apples-to-apples evaluations for language model use cases
- organize all the information generated across the LLM workflow, from experimentation, to evaluations, to production


## Key concepts

Weave's **core types** layer contains everything you need for organizing AI projects, with built-in lineage, tracking, and reproducibility.

  - **[Datasets](/guides/core-types/datasets)**: Version, store, and share rich tabular data.
  - **[Models](/guides/core-types/models)**: Version, store, and share parameterized functions.
  - **[Evaluations](/guides/core-types/evaluations)**: Test suites for AI models.
  - [soon] Agents: ...

Weave's **tracking** layer brings immutable tracing and versioning to your programs and experiments.

  - **[Objects](/guides/tracking/objects)**: Weave's extensible serialization lets you easily version, track, and share Python objects.
  - **[Ops](/guides/tracking/ops)**: Versioned, reproducible functions, with automatic tracing.
  - **[Tracing](/guides/tracking/tracing)**: Automatic organization of function calls and data lineage.

Weave's **ecosystem** is batteries included for other libraries, systems, and best practices.

  - **[OpenAI](/guides/ecosystem/openai)**: automatic tracking for openai api calls
  - [soon] Langchain auto-logging
  - [soon] llama-index auto-logging

Weave's **tools** layer contains utilities for making use of Weave objects.
  
  - **[Serve](/guides/tools/serve)**: FastAPI server for Weave Ops and Models
  - **[Deploy](/guides/tools/deploy)**: Deploy Weave Ops and Models to various targets




## What's next?

Try the [Quickstart](/quickstart) to see Weave in action.
