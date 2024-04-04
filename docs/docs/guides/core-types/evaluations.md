---
sidebar_position: 4
hide_table_of_contents: true
---

# Evaluation

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` or set of examples using scoring functions.

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
def match_score1(expected: dict, model_output: dict) -> dict:
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

Weave will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual ouputs and scores.

### Define an evaluation dataset

First, define a [Dataset](/guides/core-types/datasets) or list of dictionaries with a collection of examples to be evaluated. These examples are often failure cases that you want to test for, these are similar to unit tests in Test-Driven Development (TDD).

### Define a scoring function

Then, define a list of scoring functions. Each function should take an example and a `model_output`, and return a dictionary with the scores. 

Scoring functions need to have a `model_output` keyword argument, but the other arguments are user defined and are taken from the dataset examples. It will only take the neccessary keys by using a dictionary key based on the argument name.

This will take `expected` from the dictionary for scoring.

```python
import weave
# Define any custom scoring function
@weave.op()
def match_score1(expected: dict, model_output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {'match': expected == model_output['generated_text']}
```

### Configuring the input argument to the model or function being evaluated

To evaluate a `Model`, call `evaluate` on it using an `Evaluation`. `Models` are used when you have attributes that you want to experiment with and capture in weave.

```python
from weave import Model
class MyModel(Model)
    prompt: str

    @weave.op()
    def predict(question: str):
        # here's where you would add your LLM call and return the output
        return {'generated_text': 'Hello, ' + self.prompt}

model = MyModel(prompt='World')
evaluation.evaluate(model)
```
This will run `predict` on each example and score the output with each scoring functions.

You can also evaluate a function that is wrapped in a `@weave.op()`.
```python
@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'some response'}

evaluation.evaluate(function_to_evaluate)
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
def match_score1(expected: dict, model_output: dict) -> dict:
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