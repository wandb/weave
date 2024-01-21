---
sidebar_position: 1
hide_table_of_contents: true

---

# Introduction

Weave is a toolkit for developing AI-powered applications.

Our goal is to bring rigor, best-practices, and composability, to the inherently experimental process of developing AI-based software, without introducing cognitive overhead.

Weave's core concept is that as your code executes, it keeps track of function calls, and their inputs and outputs. You don't need to learn a declarative language or a complex object hierarchy. Just decorate functions with `@weave.op` to [get started](/docs/get-started/quickstart)


## Key Concepts

Weave's **tracking** layer brings immutable tracing and versioning to your programs and experiments.

  - **[Objects](/docs/using-weave/objects)**: Weave's extensible serialization lets you easily version, track, and share Python objects.
  - **[Ops](/docs/using-weave/objects)**: Versioned, reproducible functions, with automatic tracing.
  - **[Tracing](/docs/using-weave/tracing)**: Automatic organization of function calls and data lineage.

Weave's **core types** layer contains everything you need for organizing AI projects, with built-in tracking.

  - **[Datasets](/docs/using-weave/dataset)**: Version, store, and share rich tabular data.
  - **[Models](/docs/using-weave/model)**: Version, store and share parameterized functions.
  - **[Evaluations](/docs/using-weave/evaluation)**: Test suites for AI models.
  - [soon] Agents: ...

Weave's **ecosystem** is batteries included for other libraries, systems, and best practices.

  - **[Auto-tracing](/docs/using-weave/autotracing)**: openai, [coming soon] langchain, llama-index, and more
  - ...

Weave's **toolbelt** contains utilities for making use of Weave objects.
  
  - **[Serve](/docs/using-weave/serve)**: FastAPI server for Weave Ops and Models
  - **[Deploy](/docs/using-weave/deply)**: Deploy Weave Ops and Models to various targets




## What's next?

Try the [Quickstart](/docs/get-started/quickstart) to see Weave in action.
