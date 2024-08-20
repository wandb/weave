---
title: Prompt Optimization
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/dspy_prompt_optimization.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/dspy_prompt_optimization.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{prompt-optim-notebook} -->

# Optimizing LLM Workflows Using DSPy and Weave

The [BIG-bench (Beyond the Imitation Game Benchmark)](https://github.com/google/BIG-bench) is a collaborative benchmark intended to probe large language models and extrapolate their future capabilities consisting of more than 200 tasks. The [BIG-Bench Hard (BBH)](https://github.com/suzgunmirac/BIG-Bench-Hard) is a suite of 23 most challenging BIG-Bench tasks that can be quite difficult to be solved using the current generation of language models.

This tutorial demonstrates how we can improve the performance of our LLM workflow implemented  on the **causal judgement task** from the BIG-bench Hard benchmark and evaluate our prompting strategies. We will use [DSPy](https://dspy-docs.vercel.app/) for implementing our LLM workflow and optimizing our prompting strategy. We will also use [Weave](../../introduction.md) to track our LLM workflow and evaluate our prompting strategies.

## Installing the Dependencies

We need the following libraries for this tutorial:

- [DSPy](https://dspy-docs.vercel.app/) for building the LLM workflow and optimizing it.
- [Weave](../../introduction.md) to track our LLM workflow and evaluate our prompting strategies.
- [datasets](https://huggingface.co/docs/datasets/index) to access the Big-Bench Hard dataset from HuggingFace Hub.


```python
!pip install -qU dspy-ai weave datasets
```

Since we'll be using [OpenAI API](https://openai.com/index/openai-api/) as the LLM Vendor, we will also need an OpenAI API key. You can [sign up](https://platform.openai.com/signup) on the OpenAI platform to get your own API key.


```python
import os
from getpass import getpass

api_key = getpass("Enter you OpenAI API key: ")
os.environ["OPENAI_API_KEY"] = api_key
```

## Enable Tracking using Weave

Weave is currently integrated with DSPy, and including [`weave.init`](../../reference/python-sdk/weave/index.md) at the start of our code lets us automatically trace our DSPy functions which can be explored in the Weave UI. Check out the [Weave integration docs for DSPy](../../guides/integrations/dspy.md) to learn more.



```python
import weave

weave.init(project_name="dspy-bigbench-hard")
```

In this tutorial, we use a metadata class inherited from [`weave.Object`](../../guides/tracking/objects.md) to manage our metadata.


```python
class Metadata(weave.Object):
    dataset_address: str = "maveriq/bigbenchhard"
    big_bench_hard_task: str = "causal_judgement"
    num_train_examples: int = 50
    openai_model: str = "gpt-3.5-turbo"
    openai_max_tokens: int = 2048
    max_bootstrapped_demos: int = 8
    max_labeled_demos: int = 8


metadata = Metadata()
```

:::tip Object Versioning
The `Metadata` objects are automatically versioned and traced when functions consuming them are traced
:::

## Load the BIG-Bench Hard Dataset

We will load this dataset from HuggingFace Hub, split into training and validation sets, and [publish](../../guides/core-types/datasets.md) them on Weave, this will let us version the datasets, and also use [`weave.Evaluation`](../../guides/core-types/evaluations.md) to evaluate our prompting strategy.


```python
import dspy
from datasets import load_dataset


@weave.op()
def get_dataset(metadata: Metadata):
    # load the BIG-Bench Hard dataset corresponding to the task from Huggingface Hug
    dataset = load_dataset(metadata.dataset_address, metadata.big_bench_hard_task)[
        "train"
    ]

    # create the training and validation datasets
    rows = [{"question": data["input"], "answer": data["target"]} for data in dataset]
    train_rows = rows[0 : metadata.num_train_examples]
    val_rows = rows[metadata.num_train_examples :]

    # create the training and validation examples consisting of `dspy.Example` objects
    dspy_train_examples = [
        dspy.Example(row).with_inputs("question") for row in train_rows
    ]
    dspy_val_examples = [dspy.Example(row).with_inputs("question") for row in val_rows]

    # publish the datasets to the Weave, this would let us version the data and use for evaluation
    weave.publish(
        weave.Dataset(
            name=f"bigbenchhard_{metadata.big_bench_hard_task}_train", rows=train_rows
        )
    )
    weave.publish(
        weave.Dataset(
            name=f"bigbenchhard_{metadata.big_bench_hard_task}_val", rows=val_rows
        )
    )

    return dspy_train_examples, dspy_val_examples


dspy_train_examples, dspy_val_examples = get_dataset(metadata)
```

## The DSPy Program

[DSPy](https://dspy-docs.vercel.app) is a framework that pushes building new LM pipelines away from manipulating free-form strings and closer to programming (composing modular operators to build text transformation graphs) where a compiler automatically generates optimized LM invocation strategies and prompts from a program.

We will use the [`dspy.OpenAI`](https://dspy-docs.vercel.app/api/language_model_clients/OpenAI) abstraction to make LLM calls to [GPT3.5 Turbo](https://platform.openai.com/docs/models/gpt-3-5-turbo).


```python
system_prompt = """
You are an expert in the field of causal reasoning. You are to analyze the a given question carefully and answer in `Yes` or `No`.
You should also provide a detailed explanation justifying your answer.
"""

llm = dspy.OpenAI(model="gpt-3.5-turbo", system_prompt=system_prompt)
dspy.settings.configure(lm=llm)
```

### Writing the Causal Reasoning Signature

A [signature](https://dspy-docs.vercel.app/docs/building-blocks/signatures) is a declarative specification of input/output behavior of a [DSPy module](https://dspy-docs.vercel.app/docs/building-blocks/modules) which are task-adaptive components—akin to neural network layers—that abstract any particular text transformation.


```python
from pydantic import BaseModel, Field


class Input(BaseModel):
    query: str = Field(description="The question to be answered")


class Output(BaseModel):
    answer: str = Field(description="The answer for the question")
    confidence: float = Field(
        ge=0, le=1, description="The confidence score for the answer"
    )
    explanation: str = Field(description="The explanation for the answer")


class QuestionAnswerSignature(dspy.Signature):
    input: Input = dspy.InputField()
    output: Output = dspy.OutputField()


class CausalReasoningModule(dspy.Module):
    def __init__(self):
        self.prog = dspy.TypedPredictor(QuestionAnswerSignature)

    @weave.op()
    def forward(self, question) -> dict:
        return self.prog(input=Input(query=question)).output.dict()
```

Let's test our LLM workflow, i.e., the `CausalReasoningModule` on an example from the causal reasoning subset of Big-Bench Hard.


```python
import rich

baseline_module = CausalReasoningModule()

prediction = baseline_module(dspy_train_examples[0]["question"])
rich.print(prediction)
```

## Evaluating our DSPy Program

Now that we have a baseline prompting strategy, let's evaluate it on our validation set using [`weave.Evaluation`](../../guides/core-types/evaluations.md) on a simple metric that matches the predicted answer with the ground truth. Weave will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual outputs and scores.

First, we need to create a simple weave evaluation scoring function that tells whether the answer from the baseline module's output is the same as the ground truth answer or not. Scoring functions need to have a `model_output` keyword argument, but the other arguments are user defined and are taken from the dataset examples. It will only take the necessary keys by using a dictionary key based on the argument name.


```python
@weave.op()
def weave_evaluation_scorer(answer: str, model_output: Output) -> dict:
    return {"match": int(answer.lower() == model_output["answer"].lower())}
```

Next, we can simply define the evaluation and run it.


```python
validation_dataset = weave.ref(
    f"bigbenchhard_{metadata.big_bench_hard_task}_val:v0"
).get()

evaluation = weave.Evaluation(
    name="baseline_causal_reasoning_module",
    dataset=validation_dataset,
    scorers=[weave_evaluation_scorer],
)

await evaluation.evaluate(baseline_module.forward)
```

:::note
If you're running from a python script, you can use the following code to run the evaluation:

```python
import asyncio
asyncio.run(evaluation.evaluate(baseline_module.forward))
```
:::

:::warning
Running the evaluation causal reasoning dataset will cost approximately $0.24 in OpenAI credits.
:::

## Optimizing our DSPy Program

Now, that we have a baseline DSPy program, let us try to improve its performance for causal reasoning using a [DSPy teleprompter](https://dspy-docs.vercel.app/docs/building-blocks/optimizers) that can tune the parameters of a DSPy program to maximize the specified metrics. In this tutorial, we use the [BootstrapFewShot](https://dspy-docs.vercel.app/api/category/optimizers) teleprompter.


```python
from dspy.teleprompt import BootstrapFewShot


@weave.op()
def get_optimized_program(model: dspy.Module, metadata: Metadata) -> dspy.Module:
    @weave.op()
    def dspy_evaluation_metric(true, prediction, trace=None):
        return prediction["answer"].lower() == true.answer.lower()

    teleprompter = BootstrapFewShot(
        metric=dspy_evaluation_metric,
        max_bootstrapped_demos=metadata.max_bootstrapped_demos,
        max_labeled_demos=metadata.max_labeled_demos,
    )
    return teleprompter.compile(model, trainset=dspy_train_examples)


optimized_module = get_optimized_program(baseline_module, metadata)
```

:::warning
Running the evaluation causal reasoning dataset will cost approximately $0.04 in OpenAI credits.
:::

Now that we have our optimized program (the optimized prompting strategy), let's evaluate it once again on our validation set and compare it with our baseline DSPy program.


```python
evaluation = weave.Evaluation(
    name="optimized_causal_reasoning_module",
    dataset=validation_dataset,
    scorers=[weave_evaluation_scorer],
)

await evaluation.evaluate(optimized_module.forward)
```

When coomparing the evalution of the baseline program with the optimized one shows that the optimized program answers the causal reasoning questions with siginificantly more accuracy.

## Conclusion

In this tutorial, we learned how to use DSPy for prompt optimization alongside using Weave for tracking and evaluation to compare the original and optimized programs.
