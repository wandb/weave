# Evaluation Basics

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` or set of examples using scoring functions.

![Evals hero](../../../static/img/evals-hero.png)

```python
import weave
from weave import Evaluation
import asyncio

# Collect your examples
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

# Define any custom scoring function
@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {'match': expected == model_output['generated_text']}

@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'Paris'}

# Score your examples using scoring functions
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)

# Start tracking the evaluation
weave.init('intro-example')
# Run the evaluation
asyncio.run(evaluation.evaluate(function_to_evaluate))
```

## Create an Evaluation

To systematically improve your application, it's helpful to test your changes against a consistent dataset of potential inputs so that you catch regressions and can inspect your apps behaviour under different conditions. Using the `Evaluation` class, you can be sure you're comparing apples-to-apples by keeping track of all of the details that you're experimenting and evaluating with.

Weave will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual outputs and scores.

### Define an evaluation dataset

First, define a [Dataset](/guides/core-types/datasets) or list of dictionaries with a collection of examples to be evaluated. These examples are often failure cases that you want to test for, these are similar to unit tests in Test-Driven Development (TDD).

### Defining scoring functions

Then, create a list of scoring functions. These are used to score each example. Each function should have a `model_output` and optionally, other inputs from your examples, and return a dictionary with the scores.

Scoring functions need to have a `model_output` keyword argument, but the other arguments are user defined and are taken from the dataset examples. It will only take the necessary keys by using a dictionary key based on the argument name.

This will take `expected` from the dictionary for scoring.

```python
import weave

# Collect your examples
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

# Define any custom scoring function
@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {'match': expected == model_output['generated_text']}
```

### Optional: Define a custom `Scorer` class

In some applications we want to create custom `Scorer` classes - where for example a standardized `LLMJudge` class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score.

See the tutorial on defining a `Scorer` class in the next chapter on [Model-Based Evaluation of RAG applications](/tutorial-rag#optional-defining-a-scorer-class) for more information.

### Define a Model to evaluate

To evaluate a `Model`, call `evaluate` on it using an `Evaluation`. `Models` are used when you have attributes that you want to experiment with and capture in weave.

```python
from weave import Model, Evaluation
import asyncio

class MyModel(Model):
    prompt: str

    @weave.op()
    def predict(self, question: str):
        # here's where you would add your LLM call and return the output
        return {'generated_text': 'Hello, ' + self.prompt}

model = MyModel(prompt='World')

evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)
weave.init('intro-example') # begin tracking results with weave
asyncio.run(evaluation.evaluate(model))
```

This will run `predict` on each example and score the output with each scoring functions.

#### Custom Naming

You can change the name of the Evaluation itself by passing a `name` parameter to the `Evaluation` class.

```python
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1], name="My Evaluation"
)
```

You can also change the name of individual evaluations by setting the `display_name` key of the `__weave` dictionary.

:::note

Using the `__weave` dictionary sets the call display name which is distinct from the Evaluation object name. In the
UI, you will see the display name if set, otherwise the Evaluation object name will be used.

:::

```python
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)
evaluation.evaluate(model, __weave={"display_name": "My Evaluation Run"})
```

### Define a function to evaluate

Alternatively, you can also evaluate a function that is wrapped in a `@weave.op()`.

```python
@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'some response'}

asyncio.run(evaluation.evaluate(function_to_evaluate))
```

### Pulling it all together

```python
from weave import Evaluation, Model
import weave
import asyncio
weave.init('intro-example')
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    return {'match': expected == model_output['generated_text']}

@weave.op()
def match_score2(expected: dict, model_output: dict) -> dict:
    return {'match': expected == model_output['generated_text']}

class MyModel(Model):
    prompt: str

    @weave.op()
    def predict(self, question: str):
        # here's where you would add your LLM call and return the output
        return {'generated_text': 'Hello, ' + question + self.prompt}

model = MyModel(prompt='World')
evaluation = Evaluation(dataset=examples, scorers=[match_score1, match_score2])

asyncio.run(evaluation.evaluate(model))

@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'some response' + question}

asyncio.run(evaluation.evaluate(function_to_evaluate))
```

## Advanced evaluation usage

### Using `preprocess_model_input` to format dataset rows before evaluating

The `preprocess_model_input` parameter allows you to transform your dataset examples before they are passed to your evaluation function. This is useful when you need to:
- Rename fields to match your model's expected input
- Transform data into the correct format
- Add or remove fields
- Load additional data for each example

Here's a simple example that shows how to use `preprocess_model_input` to rename fields:

```python
import weave
from weave import Evaluation
import asyncio

# Our dataset has "input_text" but our model expects "question"
examples = [
    {"input_text": "What is the capital of France?", "expected": "Paris"},
    {"input_text": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"input_text": "What is the square root of 64?", "expected": "8"},
]

@weave.op()
def preprocess_example(example):
    # Rename input_text to question
    return {
        "question": example["input_text"]
    }

@weave.op()
def match_score(expected: str, model_output: dict) -> dict:
    return {'match': expected == model_output['generated_text']}

@weave.op()
def function_to_evaluate(question: str):
    return {'generated_text': f'Answer to: {question}'}

# Create evaluation with preprocessing
evaluation = Evaluation(
    dataset=examples,
    scorers=[match_score],
    preprocess_model_input=preprocess_example
)

# Run the evaluation
weave.init('preprocessing-example')
asyncio.run(evaluation.evaluate(function_to_evaluate))
```

In this example, our dataset contains examples with an `input_text` field, but our evaluation function expects a `question` parameter. The `preprocess_example` function transforms each example by renaming the field, allowing the evaluation to work correctly.

The preprocessing function:
1. Receives the raw example from your dataset
2. Returns a dictionary with the fields your model expects
3. Is applied to each example before it's passed to your evaluation function

This is particularly useful when working with external datasets that may have different field names or structures than what your model expects.

### Using HuggingFace Datasets with evaluations

We are continuously improving our integrations with third-party services and libraries. 

While we work on building more seamless integrations, you can use `preprocess_model_input` as a temporary workaround for using HuggingFace Datasets in Weave evaluations. 

See our [Using HuggingFace Datasets in evaluations cookbook](/reference/gen_notebooks/hf_dataset_evals) for the current approach.
