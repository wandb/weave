---
title: Extracting Structured Data from Documents using Instructor and Weave
---

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/parse_arxiv_papers.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/parse_arxiv_papers.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


# Extracting Structured Data from Documents using Instructor and Weave

LLMs are widely used in downstream applications which necessitates outputs to be structured in a consistent manner. This often requires the LLM-powered applications to parse unstructured documents (such as PDF files) and extract specific information structured according to a specififc schema.

In this tutorial, you will learn how to extract specific information from machine learning papers (such as key findings, novel methodologies, research directions, etc.). We will use [Instructor](https://python.useinstructor.com/) to get structured output from an OpenAI [GPT-4o](https://platform.openai.com/docs/models/gpt-4o) model in the form of [Pydantic objects](https://docs.pydantic.dev/latest/concepts/models/). We will also use [Weave](../../introduction.md) to track and evaluate our LLM workflow.

## Installing the Dependencies

We need the following libraries for this tutorial:

- [Instructor](https://python.useinstructor.com/) to easily get structured output from LLMs.
- [OpenAI](https://openai.com/index/openai-api/) as our LLM vendor.
- [Weave](../../introduction.md) to track our LLM workflow and evaluate our prompting strategies.


```python
!pip install -qU pymupdf4llm instructor openai weave wget
```

Since we'll be using [OpenAI API](https://openai.com/index/openai-api/) as the LLM Vendor, we will also need an OpenAI API key. You can [sign up](https://platform.openai.com/signup) on the OpenAI platform to get your own API key.


```python
import os
from getpass import getpass

api_key = getpass("Enter you OpenAI API key: ")
os.environ["OPENAI_API_KEY"] = api_key
os.environ["WEAVE_PARALLELISM"] = "1"
```

## Enable Tracking using Weave

Weave is currently integrated with OpenAI, and including [`weave.init`](../../reference/python-sdk/weave/index.md) at the start of our code lets us automatically trace our OpenAI chat completions which can be explored in the Weave UI. Check out the [Weave integration docs for OpenAI](../../guides/integrations/openai.md) to learn more.


```python
import weave

weave.init(project_name="arxiv-data-extraction")
```

## Structured Data Extraction Workflow

In order to extract the required structured data from a machine learning paper using GPT-4o and instructor, let's first define our schema as [Pydantic Model](https://docs.pydantic.dev/latest/concepts/models/) outlining the exact information that we need from a paper.


```python
from typing import List, Optional

from pydantic import BaseModel


class Finding(BaseModel):
    finding_name: str
    explanation: str


class Method(BaseModel):
    method_name: str
    explanation: str
    citation: Optional[str]


class Evaluation(BaseModel):
    metric: str
    benchmark: str
    value: float
    observation: str


class PaperInfo(BaseModel):
    main_findings: List[Finding]  # The main findings of the paper
    novel_methods: List[Method]  # The novel methods proposed in the paper
    existing_methods: List[Method]  # The existing methods used in the paper
    machine_learning_techniques: List[
        Method
    ]  # The machine learning techniques used in the paper
    metrics: List[Evaluation]  # The evaluation metrics used in the paper
    github_repository: (
        str  # The link to the GitHub repository of the paper (if there is any)
    )
    hardware: str  # The hardware or accelerator setup used in the paper
    further_research: List[
        str
    ]  # The further research directions suggested in the paper
```

Next, we write a detailed system prompt that serve as a set of instructions providing context and guidelines to help the model perform the required task.

First of all, we ask the model to play the role of "helpful assistant to a machine learning researcher who is reading a paper from arXiv", thus establishing the basic context of the task. Next, we provide the information regarding all the information in it needs to extract from the paper, in accordance with the schema `PaperInfo`.


```python
system_prompt = """
You are a helpful assistant to a machine learning researcher who is reading a paper from arXiv.
You are to extract the following information from the paper:

- a list of main findings in from the paper and their corresponding detailed explanations
- the list of names of the different novel methods proposed in the paper and their corresponding detailed explanations
- the list of names of the different existing methods used in the paper, their corresponding detailed explanations, and
    their citations
- the list of machine learning techniques used in the paper, such as architectures, optimizers, schedulers, etc., their
    corresponding detailed explanations, and their citations
- the list of evaluation metrics used in the paper, the benchmark datasets used, the values of the metrics, and their
    corresponding detailed observation in the paper
- the link to the GitHub repository of the paper if there is any
- the hardware or accelerators used to perform the experiments in the paper if any
- a list of possible further research directions that the paper suggests
"""
```

:::note
You can also checkout OpenAI's [Prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering) for more details on writing good prompts for models like GPT-4o.
:::

Next, we patch the OpenAI client to return structured outputs.


```python
import instructor
from openai import OpenAI

openai_client = OpenAI()
structured_client = instructor.from_openai(openai_client)
```

Finally, we write our LLM execution workflow as a [Weave Model](../../guides/core-types/models.md) thus combining the configurations associated with the workflow along with the code that defines how the model operates into a single object that will now be tracked and versioned using Weave.


```python
from io import BytesIO

import pymupdf
import pymupdf4llm
import requests


class ArxivModel(weave.Model):
    model: str
    system_prompt: str
    max_retries: int = 5
    seed: int = 42

    @weave.op()
    def get_markdown_from_arxiv(self, url):
        response = requests.get(url)
        with pymupdf.open(stream=BytesIO(response.content), filetype="pdf") as doc:
            return pymupdf4llm.to_markdown(doc)

    @weave.op()
    def predict(self, url_pdf: str) -> PaperInfo:
        md_text = self.get_markdown_from_arxiv(url_pdf)
        return structured_client.chat.completions.create(
            model=self.model,
            response_model=PaperInfo,
            max_retries=self.max_retries,
            seed=self.seed,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": md_text},
            ],
        )
```


```python
import rich

arxiv_parser_model = ArxivModel(model="gpt-4o", system_prompt=system_prompt)

result = arxiv_parser_model.predict(url_pdf="http://arxiv.org/pdf/1711.06288v2.pdf")
rich.print(result)
```

:::warning
Executing this LLM workflow will cost approximately $0.05-$0.25 in OpenAI credits, depending on the number of attempts instructor needs makes to get the output in the desired format (which is set to 5).
:::

| ![](https://i.imgur.com/Etnjoyq.png) |
|---|
| Here's how you can explore the traces of the `ArxivModel` in the Weave UI |

## Evaluating the Prompting Workflow

Let us now evaluate how accurately our LLM workflow is able to extract the methods from the paper using [Weave Evaluation](../../guides/core-types/evaluations.md). For this we will write a simple scoring function that compares the list of novel methods, existing methods, and ML techniques predicted by the promting worflow against a ground-truth list of methods associated with the paper to compute an accuracy score.


```python
@weave.op()
def arxiv_method_score(
    method: List[dict], model_output: Optional[PaperInfo]
) -> dict[str, float]:
    if model_output is None:
        return {"method_prediction_accuracy": 0.0}
    predicted_methods = (
        model_output.novel_methods
        + model_output.existing_methods
        + model_output.machine_learning_techniques
    )
    num_correct_methods = 0
    for gt_method in method:
        for predicted_method in predicted_methods:
            predicted_method = (
                f"{predicted_method.method_name}\n{predicted_method.explanation}"
            )
            if (
                gt_method["name"].lower() in predicted_method.lower()
                or gt_method["full_name"].lower() in predicted_method.lower()
            ):
                num_correct_methods += 1
    return {
        "method_prediction_accuracy": num_correct_methods / len(predicted_methods)
    }
```

For this tutorial, we will use a dataset of more than 6000 machine learning research papers and their corresponding metadata created using the [paperswithcode client](https://paperswithcode-client.readthedocs.io/en/latest/) (check [this gist](https://gist.github.com/soumik12345/996c2ea538f6ff5b3747078ba557ece4) for reference). The dataset is stored as a [Weave Dataset](../../guides/core-types/datasets.md) which you can explore [here](https://wandb.ai/geekyrakshit/arxiv-data-extraction/weave/objects/cv-papers/versions/7wICKJjt3YyqL3ssICHi08v3swAGSUtD7TF4PVRJ0yc).


```python
WEAVE_DATASET_REFERENCE = "weave:///geekyrakshit/arxiv-data-extraction/object/cv-papers:7wICKJjt3YyqL3ssICHi08v3swAGSUtD7TF4PVRJ0yc"
eval_dataset = weave.ref(WEAVE_DATASET_REFERENCE).get()

rich.print(f"{len(eval_dataset.rows)=}")
```

Now, we can evaluate our LLM workflow using [Weave Evalations](../../guides/core-types/evaluations.md), that will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual outputs and scores.


```python
evaluation = weave.Evaluation(
    name="baseline_workflow_evaluation",
    dataset=eval_dataset.rows[:5],
    scorers=[arxiv_method_score],
)
await evaluation.evaluate(arxiv_parser_model)
```

:::warning
Running the evaluation on 5 examples from evaluation dataset will cost approximately $0.25-$1.25 in OpenAI credits, depending on the number of attempts instructor needs makes to get the output in the desired format (which is set to 5) in evaluating each example.
:::

## Improving the LLM Workflow

Let us try to improve the LLM workflow by adding some more instructions to our system prompt. We will provide the model with a set of rules, which act as a set of clues to guide the model to look for specific type of information in the document.


```python
system_prompt += """
Here are some rules to follow:
1. When looking for the main findings in the paper, you should look for the abstract.
2. When looking for the explanations for the main findings, you should look for the introduction and methods section of
    the paper.
3. When looking for the list of existing methods used in the paper, first look at the citations, and then try explaining
    how they were used in the paper.
4. When looking for the list of machine learning methods used in the paper, first look at the citations, and then try
    explaining how they were used in the paper.
5. When looking for the evaluation metrics used in the paper, first look at the results section of the paper, and then
    try explaining the observations made from the results. Pay special attention to the tables to find the metrics,
    their values, the corresponding benchmark and the observation association with the result.
6. If there are no github repositories associated with the paper, simply return "None".
7. When looking for hardware and accelerators, pay special attentions to the quantity of each type of hardware and
    accelerator. If there are no hardware or accelerators used in the paper, simply return "None".
8. When looking for further research directions, look for the conclusion section of the paper.
"""

improved_arxiv_parser_model = ArxivModel(model="gpt-4o", system_prompt=system_prompt)
```

We will not evaluate this improved workflow again and try to check if the accuracy has increased or not.


```python
evaluation = weave.Evaluation(
    name="improved_workflow_evaluation",
    dataset=eval_dataset.rows[:5],
    scorers=[arxiv_method_score],
)
await evaluation.evaluate(arxiv_parser_model)
```

:::warning
Running the evaluation on 5 examples from evaluation dataset will cost approximately $0.25-$1.25 in OpenAI credits, depending on the number of attempts instructor needs makes to get the output in the desired format (which is set to 5) in evaluating each example.
:::

| ![](https://i.imgur.com/qFbt8T0.png) |
|---|
| Here's how you can explore and compare the evaluations traces in the Weave UI |
