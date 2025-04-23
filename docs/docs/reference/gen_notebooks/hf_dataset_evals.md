---
title: Using HuggingFace Datasets in evaluations with `preprocess_model_input`
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/hf_dataset_evals.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/hf_dataset_evals.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



# Using HuggingFace Datasets in evaluations with `preprocess_model_input`

## Note: This is a temporary workaround
> This guide demonstrates a workaround for using HuggingFace Datasets with Weave evaluations.<br /><br/>
We are actively working on developing more seamless integrations that will simplify this process.\
> While this approach works, expect improvements and updates in the near future that will make working with external datasets more straightforward.

## Setup and imports
First, we initialize Weave and connect to Weights & Biases for tracking experiments.


```python
!pip install datasets wandb weave
```


```python
# Initialize variables
HUGGINGFACE_DATASET = "wandb/ragbench-test-sample"
WANDB_KEY = ""
WEAVE_TEAM = ""
WEAVE_PROJECT = ""

# Init weave and required libraries
import asyncio

import nest_asyncio
import wandb
from datasets import load_dataset

import weave
from weave import Evaluation

# Login to wandb and initialize weave
wandb.login(key=WANDB_KEY)
client = weave.init(f"{WEAVE_TEAM}/{WEAVE_PROJECT}")

# Apply nest_asyncio to allow nested event loops (needed for some notebook environments)
nest_asyncio.apply()
```

## Load and prepare HuggingFace dataset

- We load a HuggingFace dataset.
- Create an index mapping to reference the dataset rows.
- This index approach allows us to maintain references to the original dataset.

> **Note:**<br/>
In the index, we encode the `hf_hub_name` along with the `hf_id` to ensure each row has a unique identifier.\
This unique digest value is used for tracking and referencing specific dataset entries during evaluations.


```python
# Load the HuggingFace dataset
ds = load_dataset(HUGGINGFACE_DATASET)
row_count = ds["train"].num_rows

# Create an index mapping for the dataset
# This creates a list of dictionaries with HF dataset indices
# Example: [{"hf_id": 0}, {"hf_id": 1}, {"hf_id": 2}, ...]
hf_index = [{"hf_id": i, "hf_hub_name": HUGGINGFACE_DATASET} for i in range(row_count)]
```

## Define processing and evaluation functions

### Processing pipeline
- `preprocess_example`: Transforms the index reference into the actual data needed for evaluation
- `hf_eval`: Defines how to score the model outputs
- `function_to_evaluate`: The actual function/model being evaluated


```python
@weave.op()
def preprocess_example(example):
    """
    Preprocesses each example before evaluation.
    Args:
        example: Dict containing hf_id
    Returns:
        Dict containing the prompt from the HF dataset
    """
    hf_row = ds["train"][example["hf_id"]]
    return {"prompt": hf_row["question"], "answer": hf_row["response"]}


@weave.op()
def hf_eval(hf_id: int, output: dict) -> dict:
    """
    Scoring function for evaluating model outputs.
    Args:
        hf_id: Index in the HF dataset
        output: The output from the model to evaluate
    Returns:
        Dict containing evaluation scores
    """
    hf_row = ds["train"][hf_id]
    return {"scorer_value": True}


@weave.op()
def function_to_evaluate(prompt: str):
    """
    The function that will be evaluated (e.g., your model or pipeline).
    Args:
        prompt: Input prompt from the dataset
    Returns:
        Dict containing model output
    """
    return {"generated_text": "testing "}
```

### Create and run evaluation

- For each index in hf_index:
  1. `preprocess_example` gets the corresponding data from the HF dataset.
  2. The preprocessed data is passed to `function_to_evaluate`.
  3. The output is scored using `hf_eval`.
  4. Results are tracked in Weave.


```python
# Create evaluation object
evaluation = Evaluation(
    dataset=hf_index,  # Use our index mapping
    scorers=[hf_eval],  # List of scoring functions
    preprocess_model_input=preprocess_example,  # Function to prepare inputs
)


# Run evaluation asynchronously
async def main():
    await evaluation.evaluate(function_to_evaluate)


asyncio.run(main())
```
