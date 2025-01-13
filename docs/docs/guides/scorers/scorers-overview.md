import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Scorers

In Weave, a _scorer_ is a function that processes the input or output of an Large Language Model (LLM), evaluates it for a specific quality, and generates a corresponding score. Depending on the [use case](#use-cases), the scorer output might be a Boolean, a float, or a value within a specific range. Various types of [built-in scorers are available for common scenarios](../scorers/built-in-scorers.md) such as hallucination detection or leaked PII data (in Python only). You can also create [custom scorers](../scorers/custom-scorers.md) for your specific scenario.

:::tip
Toggle between tabs to view code samples and details specific to Python or TypeScript.
:::

## Use cases

Scorers are the core Weave concept that powers three major use cases. 

| Use Case    | Goal                                                                                      | Example                                                                                        | Relationship to Scorers                                                                               |
|-------------|-------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| [Evaluations](../core-types/evaluations.md) | You want to measure and improve the performance of LLM applications.                       | Compare the accuracy of two language models by evaluating them against a labeled dataset.                                            | Evaluations use one or more scorers as metrics to assess model quality.                              |
| Guardrails  | You want to change LLM application logic when model predictions meet certain criteria.        | A chatbot prediction leaks PII, triggering a guardrail that prevents the PII from being sent to the end user.        | Guardrails use scorers to emit value thresholds that drive changes in application logic.             |
| Monitoring  | You want to measure performance in live LLM applications over time by observing trends.      | Monitor the language tone of a live chatbot application over time.                                  | Monitoring uses scorers to plot or analyze metrics, enabling continuous performance evaluation.       |

## Types of scorers

The types of scorers available depend on whether you are using Python or TypeScript.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    Scorers are passed to a `weave.Evaluation` object during evaluation. There are three types of scorers available for Python:

    1. [Built-in scorers](../scorers/built-in-scorers.md): Scorers built by W&B for common use cases.
    2. [Function-based scorers](../scorers/custom-scorers#function-based-scorers): Simple Python functions decorated with `@weave.op`.
    3. [Class-based scorers](../scorers/custom-scorers.md#class-based-scorers): Python classes that inherit from `weave.Scorer` for more complex evaluations.

    Scorers must return a dictionary and can include multiple metrics, nested metrics and non-numeric values. See the [Custom scorers page](../scorers/custom-scorers.md) for more information.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Scorers are special `ops` passed to a `weave.Evaluation` object during evaluation.

    Only [function-based scorers](../scorers/custom-scorers.md#function-based-scorers) are available for TypeScript. For [class-based](../scorers/custom-scorers.md#class-based-scorers) and [built-in scorers](../scorers/built-in-scorers.md), you must use Python.
  </TabItem>
</Tabs>

