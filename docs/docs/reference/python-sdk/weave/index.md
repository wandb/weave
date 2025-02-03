---
sidebar_label: weave
---
    

# weave

The top-level functions and classes for working with Weave.

---


# API Overview



## Classes

- [`obj.Object`](#class-object)
- [`dataset.Dataset`](#class-dataset): Dataset object with easy saving and automatic versioning
- [`model.Model`](#class-model): Intended to capture a combination of code and data the operates on an input.
- [`prompt.Prompt`](#class-prompt)
- [`prompt.StringPrompt`](#class-stringprompt)
- [`prompt.MessagesPrompt`](#class-messagesprompt)
- [`eval.Evaluation`](#class-evaluation): Sets up an evaluation which includes a set of scorers and a dataset.
- [`base_scorer.Scorer`](#class-scorer)

## Functions

- [`api.init`](#function-init): Initialize weave tracking, logging to a wandb project.
- [`api.publish`](#function-publish): Save and version a python object.
- [`api.ref`](#function-ref): Construct a Ref to a Weave object.
- [`call_context.require_current_call`](#function-require_current_call): Get the Call object for the currently executing Op, within that Op.
- [`call_context.get_current_call`](#function-get_current_call): Get the Call object for the currently executing Op, within that Op.
- [`api.finish`](#function-finish): Stops logging to weave.
- [`op.op`](#function-op): A decorator to weave op-ify a function or method.  Works for both sync and async.
- [`api.attributes`](#function-attributes): Context manager for setting attributes on a call.


---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L32"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `init`

```python
init(
    project_name: 'str',
    settings: 'UserSettings | dict[str, Any] | None' = None,
    autopatch_settings: 'AutopatchSettings | None' = None
) → WeaveClient
```

Initialize weave tracking, logging to a wandb project. 

Logging is initialized globally, so you do not need to keep a reference to the return value of init. 

Following init, calls of weave.op() decorated functions will be logged to the specified project. 



**Args:**
 
 - <b>`project_name`</b>:  The name of the Weights & Biases project to log to. 



**Returns:**
 A Weave client. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L88"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `publish`

```python
publish(obj: 'Any', name: 'str | None' = None) → ObjectRef
```

Save and version a python object. 

If an object with name already exists, and the content hash of obj does not match the latest version of that object, a new version will be created. 

TODO: Need to document how name works with this change. 



**Args:**
 
 - <b>`obj`</b>:  The object to save and version. 
 - <b>`name`</b>:  The name to save the object under. 



**Returns:**
 A weave Ref to the saved object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L142"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `ref`

```python
ref(location: 'str') → ObjectRef
```

Construct a Ref to a Weave object. 

TODO: what happens if obj does not exist 



**Args:**
 
 - <b>`location`</b>:  A fully-qualified weave ref URI, or if weave.init() has been called, "name:version" or just "name" ("latest" will be used for version in this case). 





**Returns:**
 A weave Ref to the object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/context/call_context.py#L65"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `require_current_call`

```python
require_current_call() → Call
```

Get the Call object for the currently executing Op, within that Op. 

This allows you to access attributes of the Call such as its id or feedback while it is running. 

```python
@weave.op
def hello(name: str) -> None:
     print(f"Hello {name}!")
     current_call = weave.require_current_call()
     print(current_call.id)
``` 

It is also possible to access a Call after the Op has returned. 

If you have the Call's id, perhaps from the UI, you can use the `call` method on the `WeaveClient` returned from `weave.init` to retrieve the Call object. 

```python
client = weave.init("<project>")
mycall = client.get_call("<call_id>")
``` 

Alternately, after defining your Op you can use its `call` method. For example: 

```python
@weave.op
def hello(name: str) -> None:
     print(f"Hello {name}!")

mycall = hello.call("world")
print(mycall.id)
``` 



**Returns:**
  The Call object for the currently executing Op 



**Raises:**
 
 - <b>`NoCurrentCallError`</b>:  If tracking has not been initialized or this method is  invoked outside an Op. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/context/call_context.py#L114"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `get_current_call`

```python
get_current_call() → Call | None
```

Get the Call object for the currently executing Op, within that Op. 



**Returns:**
  The Call object for the currently executing Op, or  None if tracking has not been initialized or this method is  invoked outside an Op. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L256"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `finish`

```python
finish() → None
```

Stops logging to weave. 

Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L573"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `op`

```python
op(
    func: 'Callable | None' = None,
    name: 'str | None' = None,
    call_display_name: 'str | CallDisplayNameFunc | None' = None,
    postprocess_inputs: 'PostprocessInputsFunc | None' = None,
    postprocess_output: 'PostprocessOutputFunc | None' = None,
    tracing_sample_rate: 'float' = 1.0
) → Callable[[Callable], Op] | Op
```

A decorator to weave op-ify a function or method.  Works for both sync and async. 

Decorated functions and methods can be called as normal, but will also automatically track calls in the Weave UI. 

If you don't call `weave.init` then the function will behave as if it were not decorated. 





**Args:**
 
 - <b>`func`</b> (Optional[Callable]):  The function to be decorated. If None, the decorator  is being called with parameters. 
 - <b>`name`</b> (Optional[str]):  Custom name for the op. If None, the function's name is used. 
 - <b>`call_display_name`</b> (Optional[Union[str, Callable[["Call"], str]]]):  Custom display name  for the call in the Weave UI. Can be a string or a function that takes a Call  object and returns a string.  When a function is passed, it can use any attributes  of the Call object (e.g. `op_name`, `trace_id`, etc.) to generate a custom display name. 
 - <b>`postprocess_inputs`</b> (Optional[Callable[[dict[str, Any]], dict[str, Any]]]):  A function  to process the inputs after they've been captured but before they're logged.  This  does not affect the actual inputs passed to the function, only the displayed inputs. 
 - <b>`postprocess_output`</b> (Optional[Callable[..., Any]]):  A function to process the output  after it's been returned from the function but before it's logged.  This does not  affect the actual output of the function, only the displayed output. 
 - <b>`tracing_sample_rate`</b> (float):  The sampling rate for tracing this function. Defaults to 1.0 (always trace). 



**Returns:**
 
 - <b>`Union[Callable[[Any], Op], Op]`</b>:  If called without arguments, returns a decorator. If called with a function, returns the decorated function as an Op. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the decorated object is not a function or method. 



Example usage: 

```python
import weave
weave.init("my-project")

@weave.op
async def extract():
    return await client.chat.completions.create(
         model="gpt-4-turbo",
         messages=[

 - <b>`            {"role"`</b>:  "user", "content": "Create a user as JSON"},
        ],
    )

await extract()  # calls the function and tracks the call in the Weave UI
``` 

---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace/api/attributes#L187"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `attributes`

```python
attributes(attributes: 'dict[str, Any]') → Iterator
```

Context manager for setting attributes on a call. 



**Example:**
 

```python
with weave.attributes({'env': 'production'}):
     print(my_function.call("World"))
``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/obj.py#L38"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Object`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/obj.py#L56"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `handle_relocatable_object`

```python
handle_relocatable_object(
    v: Any,
    handler: ValidatorFunctionWrapHandler,
    info: ValidationInfo
) → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L18"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Dataset`
Dataset object with easy saving and automatic versioning 



**Examples:**
 

```python
# Create a dataset
dataset = Dataset(name='grammar', rows=[
     {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
     {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
     {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
])

# Publish the dataset
weave.publish(dataset)

# Retrieve the dataset
dataset_ref = weave.ref('grammar').get()

# Access a specific example
example_label = dataset_ref.rows[2]['sentence']
``` 


**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `rows`: `<class 'trace.table.Table'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L45"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `convert_to_table`

```python
convert_to_table(rows: Any) → Table
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/model.py#L11"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Model`
Intended to capture a combination of code and data the operates on an input. For example it might call an LLM with a prompt to make a prediction or generate text. 

When you change the attributes or the code that defines your model, these changes will be logged and the version will be updated. This ensures that you can compare the predictions across different versions of your model. Use this to iterate on prompts or to try the latest LLM and compare predictions across different settings 



**Examples:**
 

```python
class YourModel(Model):
     attribute1: str
     attribute2: int

     @weave.op()
     def predict(self, input_data: str) -> dict:
         # Model logic goes here
         prediction = self.attribute1 + ' ' + input_data
         return {'pred': prediction}
``` 


**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/model.py#L39"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_infer_method`

```python
get_infer_method() → Callable
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L74"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Prompt`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L75"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L79"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StringPrompt`




<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L82"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(content: str)
```






**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `content`: `<class 'str'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L86"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → str
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L89"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: Any) → StringPrompt
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L97"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `MessagesPrompt`




<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L100"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(messages: list[dict])
```






**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `messages`: `list[dict]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L113"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → list
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L104"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format_message`

```python
format_message(message: dict, **kwargs: Any) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L116"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: Any) → MessagesPrompt
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval.py#L77"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Evaluation`
Sets up an evaluation which includes a set of scorers and a dataset. 

Calling evaluation.evaluate(model) will pass in rows from a dataset into a model matching  the names of the columns of the dataset to the argument names in model.predict. 

Then it will call all of the scorers and save the results in weave. 

If you want to preprocess the rows from the dataset you can pass in a function to preprocess_model_input. 



**Examples:**
 

```python
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


**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `dataset`: `typing.Union[flow.dataset.Dataset, list]`
- `scorers`: `typing.Optional[list[typing.Union[typing.Callable, trace.op.Op, scorers.base_scorer.Scorer]]]`
- `preprocess_model_input`: `typing.Optional[typing.Callable]`
- `trials`: `<class 'int'>`
- `evaluation_name`: `typing.Union[str, typing.Callable[[trace.weave_client.Call], str], NoneType]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L509"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `evaluate`

```python
evaluate(model: Union[Callable, Model]) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval.py#L465"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_eval_results`

```python
get_eval_results(model: Union[Callable, Model]) → EvaluationResults
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L177"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `predict_and_score`

```python
predict_and_score(model: Union[Callable, Model], example: dict) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L444"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `summarize`

```python
summarize(eval_table: EvaluationResults) → dict
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/scorers/base_scorer.py#L17"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Scorer`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `column_map`: `typing.Optional[dict[str, str]]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/scorers/base_scorer.py#L23"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `model_post_init`

```python
model_post_init(_Scorer__context: Any) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L27"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `score`

```python
score(output: Any, **kwargs: Any) → Any
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L31"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `summarize`

```python
summarize(score_rows: list) → Optional[dict]
```





