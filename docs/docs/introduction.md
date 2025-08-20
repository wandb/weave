---
slug: /
---

# W&B Weave

Weights & Biases (W&B) Weave is a framework for tracking, experimenting with, evaluating, deploying, and improving LLM-based applications. Designed for flexibility and scalability, Weave supports every stage of your LLM application development workflow:

- **Tracing & Monitoring**: [Track LLM calls and application logic](./guides/tracking/) to debug and analyze production systems.
- **Systematic Iteration**: Refine and iterate on [prompts](./guides/core-types/prompts.md), [datasets](./guides/core-types/datasets.md), and [models](./guides/core-types/models.md).
- **Experimentation**: Experiment with different models and prompts in the [LLM Playground](./guides/tools/playground.md). 
- **Evaluation**: Use custom or [pre-built scorers](./guides/evaluation/builtin_scorers.mdx) alongside our [comparison tools](./guides/tools/comparison.md) to systematically assess and enhance application performance.
- **Guardrails**: Protect your application with [pre- and post-safeguards](./guides/evaluation/guardrails_and_monitors.md) for content moderation, prompt safety, and more.

Integrate Weave with your existing development stack via the:
- [Python SDK](./reference/python-sdk/weave/index.md)
- [TypeScript SDK](./reference/typescript-sdk/weave/README.md)
- [Service API](./reference/service-api/call-start-call-start-post)

Weave supports [numerous LLM providers, local models, frameworks, protocols, and third-party services](./guides/integrations/index.md).

## Get started

Choose your path to get started with Weave:

### Recommended: Start with W&B Inference
[Try Weave with Inference Service](/quickstart-inference) - The fastest way to experience Weave
- No API keys needed - start building immediately
- Free credits included with all plans
- Learn tracing, evaluation, and monitoring with real models
- Access powerful models like Llama 3.3 70B and DeepSeek V3

### Have your own API keys?
[Track LLM Calls](/quickstart) - Connect your existing LLM providers
- Works with OpenAI, Anthropic, and [more](./guides/integrations/index.md)
- Automatic tracing and cost tracking
- Perfect if you already have LLM infrastructure

### Using TypeScript
[TypeScript quickstart](./reference/generated_typescript_docs/intro-notebook.md) - Get started with Weave in TypeScript

## Advanced guides

Learn more about advanced topics:

- [Integrations](./guides/integrations/index.md): Use Weave with popular LLM providers, local models, frameworks, and third-party services.
- [Cookbooks](./reference/gen_notebooks/01-intro_notebook.md): Build with Weave using Python and TypeScript. Tutorials are available as interactive notebooks.
- [W&B AI Academy](https://www.wandb.courses/pages/w-b-courses): Build advanced RAG systems, improve LLM prompting, fine-tune LLMs, and more.
