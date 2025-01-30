---
slug: /
---

# W&B Weave

Weights & Biases (W&B) Weave is a framework for tracking, experimenting with, evaluating, deploying, and improving LLM-based applications. Designed for flexibility and scalability, Weave supports every stage of your LLM application development workflow:

- **Tracing & Monitoring**: [Track LLM calls and application logic](./guides/tracking/) to debug and analyze production systems.
- **Systematic Iteration**: Refine and iterate on [prompts](./guides/core-types/prompts.md), [datasets](./guides/core-types/datasets.md), and [models](./guides/core-types/models.md).
- **Experimentation**: Experiment with different models and prompts in the [LLM Playground](./guides/tools/playground.md). 
- **Evaluation**: Use custom or [pre-built scorers](./guides/evaluation/scorers#predefined-scorers) alongside our [comparison tools](./guides/tools/comparison.md) to systematically assess and enhance application performance.
- **Guardrails**: Protect your application with [pre- and post-safeguards](./guides/evaluation/guardrails_and_monitors.md) for content moderation, prompt safety, and more.

Integrate Weave with your existing development stack via the:
- [Python SDK](./reference/python-sdk/weave/index.md)
- [TypeScript SDK](./reference/typescript-sdk/weave/README.md)
- [Service API](./reference/service-api/call-start-call-start-post)

Weave supports [numerous LLM providers, local models, frameworks, and third-party services](./guides/integrations/index.md).

## Get started

Are you new to Weave? Set up and start using Weave with the [Python quickstart](/quickstart) or [TypeScript quickstart](./reference/generated_typescript_docs/intro-notebook.md).

## Advanced guides

Learn more about advanced topics:

- [Integrations](./guides/integrations/index.md): Use Weave with popular LLM providers, local models, frameworks, and third-party services.
- [Cookbooks](./reference/gen_notebooks/01-intro_notebook.md): Build with Weave using Python and TypeScript. Tutorials are available as interactive notebooks.
- [W&B AI Academy](https://www.wandb.courses/pages/w-b-courses): Build advanced RAG systems, improve LLM prompting, fine-tune LLMs, and more.
