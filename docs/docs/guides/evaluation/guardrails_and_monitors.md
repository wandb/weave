import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Online Evaluation

![Feedback](./../../../static/img/guardrails_scorers.png)

## Introduction

Building production LLM applications? Two questions likely keep you up at night:
1. How do you ensure your LLMs generate safe, appropriate content?
2. How do you measure and improve output quality over time?

Weave's unified scoring system answers both questions through a simple yet powerful framework. Whether you need active safety controls (guardrails) or passive quality monitoring, this guide will show you how to implement robust evaluation systems for your LLM applications.

The foundation of Weave's evaluation system is the [**Scorer**](./scorers.md) - a component that evaluates your function's inputs and outputs to measure quality, safety, or any other metric you care about. Scorers are versatile and can be used in two ways:

- **As Guardrails**: Block or modify unsafe content before it reaches users
- **As Monitors**: Track quality metrics over time to identify trends and improvements

:::note Terminology
Throughout this guide, we'll refer to functions decorated with `@weave.op` as "ops". These are regular Python functions that have been enhanced with Weave's tracking capabilities.
:::

#### Ready-to-Use Scorers
While this guide shows you how to create custom scorers, Weave comes with a variety of [predefined scorers](./builtin_scorers.mdx) that you can use right away, including:
- [Hallucination detection](./builtin_scorers.mdx#hallucinationfreescorer)
- [Summarization quality](./builtin_scorers.mdx#summarizationscorer)
- [Embedding similarity](./builtin_scorers.mdx#embeddingsimilarityscorer)
- [Relevancy evaluation](./builtin_scorers.mdx#ragas---contextrelevancyscorer)
- And more!

### Guardrails vs. Monitors: When to Use Each

While scorers power both guardrails and monitors, they serve different purposes:

| Aspect | Guardrails | Monitors |
|--------|------------|----------|
| **Purpose** | Active intervention to prevent issues | Passive observation for analysis |
| **Timing** | Real-time, before output reaches users | Can be asynchronous or batched |
| **Performance** | Must be fast (affects response time) | Can be slower, run in background |
| **Sampling** | Usually every request | Often sampled (e.g., 10% of calls) |
| **Control Flow** | Can block/modify outputs | No impact on application flow |
| **Resource Usage** | Must be efficient | Can use more resources if needed |

For example, a toxicity scorer could be used:
- 🛡️ **As a Guardrail**: Block toxic content immediately
- 📊 **As a Monitor**: Track toxicity levels over time

:::note
Every scorer result is automatically stored in Weave's database. This means your guardrails double as monitors without any extra work! You can always analyze historical scorer results, regardless of how they were originally used.
:::

### Using the `.call()` Method

To use scorers with Weave ops, you'll need access to both the operation's result and its tracking information. The `.call()` method provides both:

```python
# Instead of calling the op directly:
result = generate_text(input)  # Primary way to call the op but doesn't give access to the Call object

# Use the .call() method to get both result and Call object:
result, call = generate_text.call(input)  # Now you can use the call object with scorers
```

:::tip Why Use `.call()`?
The Call object is essential for associating the score with the call in the database. While you can directly call the scoring function, this would not be associated with the call, and therefore not searchable, filterable, or exportable for later analysis.

For more details about Call objects, see our [Calls guide section on Call objects](../tracking/tracing.mdx#getting-a-handle-to-the-call-object-during-execution).
:::

## Next Steps

For detailed implementation guidance, see:
- [Implementing Guardrails](./guardrails.md)
- [Implementing Monitors](./monitors.md)
- [Available Scorers](./scorers.md)
- [Weave Ops](../../guides/tracking/ops.md)

