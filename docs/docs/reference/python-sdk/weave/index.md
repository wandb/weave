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
- [`eval_imperative.EvaluationLogger`](#class-evaluationlogger): This class provides an imperative interface for logging evaluations.
- [`scorer.Scorer`](#class-scorer)
- [`annotation_spec.AnnotationSpec`](#class-annotationspec)
- [`file.File`](#class-file): A class representing a file with path, mimetype, and size information.
- [`markdown.Markdown`](#class-markdown): A Markdown renderable.
- [`monitor.Monitor`](#class-monitor): Sets up a monitor to score incoming calls automatically.
- [`saved_view.SavedView`](#class-savedview): A fluent-style class for working with SavedView objects.
- [`audio.Audio`](#class-audio): A class representing audio data in a supported format (wav or mp3).

## Functions

- [`api.init`](#function-init): Initialize weave tracking, logging to a wandb project.
- [`api.publish`](#function-publish): Save and version a python object.
- [`api.ref`](#function-ref): Construct a Ref to a Weave object.
- [`api.get`](#function-get): A convenience function for getting an object from a URI.
- [`call_context.require_current_call`](#function-require_current_call): Get the Call object for the currently executing Op, within that Op.
- [`call_context.get_current_call`](#function-get_current_call): Get the Call object for the currently executing Op, within that Op.
- [`api.finish`](#function-finish): Stops logging to weave.
- [`op.op`](#function-op): A decorator to weave op-ify a function or method. Works for both sync and async.
- [`api.attributes`](#function-attributes): Context manager for setting attributes on a call.


---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L37"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `init`

```python
init(
    project_name: 'str',
    settings: 'UserSettings | dict[str, Any] | None' = None,
    autopatch_settings: 'AutopatchSettings | None' = None,
    global_postprocess_inputs: 'PostprocessInputsFunc | None' = None,
    global_postprocess_output: 'PostprocessOutputFunc | None' = None,
    global_attributes: 'dict[str, Any] | None' = None
) → WeaveClient
```

Initialize weave tracking, logging to a wandb project. 

Logging is initialized globally, so you do not need to keep a reference to the return value of init. 

Following init, calls of weave.op() decorated functions will be logged to the specified project. 



**Args:**
 
 - <b>`project_name`</b>:  The name of the Weights & Biases project to log to. 
 - <b>`settings`</b>:  Configuration for the Weave client generally. 
 - <b>`autopatch_settings`</b>:  Configuration for autopatch integrations, e.g. openai 
 - <b>`global_postprocess_inputs`</b>:  A function that will be applied to all inputs of all ops. 
 - <b>`global_postprocess_output`</b>:  A function that will be applied to all outputs of all ops. 
 - <b>`global_attributes`</b>:  A dictionary of attributes that will be applied to all traces. 

NOTE: Global postprocessing settings are applied to all ops after each op's own postprocessing.  The order is always: 1. Op-specific postprocessing 2. Global postprocessing 



**Returns:**
 A Weave client. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L116"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L170"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L201"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `get`

```python
get(uri: 'str | ObjectRef') → Any
```

A convenience function for getting an object from a URI. 

Many objects logged by Weave are automatically registered with the Weave server. This function allows you to retrieve those objects by their URI. 



**Args:**
 
 - <b>`uri`</b>:  A fully-qualified weave ref URI. 



**Returns:**
 The object. 



**Example:**
 

```python
weave.init("weave_get_example")
dataset = weave.Dataset(rows=[{"a": 1, "b": 2}])
ref = weave.publish(dataset)

dataset2 = weave.get(ref)  # same as dataset!
``` 

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

If you have the Call's id, perhaps from the UI, you can use the `get_call` method on the `WeaveClient` returned from `weave.init` to retrieve the Call object. 

```python
client = weave.init("<project>")
mycall = client.get_call("<call_id>")
``` 

Alternately, after defining your Op you can use its `call` method. For example: 

```python
@weave.op
def add(a: int, b: int) -> int:
     return a + b

result, call = add.call(1, 2)
print(call.id)
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/api.py#L264"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `finish`

```python
finish() → None
```

Stops logging to weave. 

Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L1191"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `op`

```python
op(
    func: 'Callable[P, R] | None' = None,
    name: 'str | None' = None,
    call_display_name: 'str | CallDisplayNameFunc | None' = None,
    postprocess_inputs: 'PostprocessInputsFunc | None' = None,
    postprocess_output: 'PostprocessOutputFunc | None' = None,
    tracing_sample_rate: 'float' = 1.0,
    enable_code_capture: 'bool' = True,
    accumulator: 'Callable[[Any | None, Any], Any] | None' = None
) → Callable[[Callable[P, R]], Op[P, R]] | Op[P, R]
```

A decorator to weave op-ify a function or method. Works for both sync and async. Automatically detects iterator functions and applies appropriate behavior. 

---

<a href="https://github.com/wandb/weave/blob/master/../../../../../../develop/core/services/weave-python/weave-public/docs/weave/trace/api/attributes#L242"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `attributes`

```python
attributes(attributes: 'dict[str, Any]') → Iterator
```

Context manager for setting attributes on a call.

Attributes become immutable once a call begins execution. Use this
context manager to provide metadata before the call starts.



**Example:**
 

```python
with weave.attributes({'env': 'production'}):
     print(my_function.call("World"))
``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/obj.py#L42"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Object`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/obj.py#L59"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_uri`

```python
from_uri(uri: str, objectify: bool = True) → Self
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/obj.py#L69"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `handle_relocatable_object`

```python
handle_relocatable_object(
    v: Any,
    handler: ValidatorFunctionWrapHandler,
    info: ValidationInfo
) → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L23"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `rows`: `typing.Union[trace.table.Table, trace.vals.WeaveTable]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L78"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_rows`

```python
add_rows(rows: Iterable[dict]) → Dataset
```

Create a new dataset version by appending rows to the existing dataset. 

This is useful for adding examples to large datasets without having to load the entire dataset into memory. 



**Args:**
 
 - <b>`rows`</b>:  The rows to add to the dataset. 



**Returns:**
 The updated dataset. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L120"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `convert_to_table`

```python
convert_to_table(rows: Any) → Union[Table, WeaveTable]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L60"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_calls`

```python
from_calls(calls: Iterable[Call]) → Self
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L51"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: WeaveObject) → Self
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L65"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_pandas`

```python
from_pandas(df: 'DataFrame') → Self
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L167"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `select`

```python
select(indices: Iterable[int]) → Self
```

Select rows from the dataset based on the provided indices. 



**Args:**
 
 - <b>`indices`</b>:  An iterable of integer indices specifying which rows to select. 



**Returns:**
 A new Dataset object containing only the selected rows. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/dataset.py#L70"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `to_pandas`

```python
to_pandas() → DataFrame
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/model.py#L23"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/model.py#L51"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_infer_method`

```python
get_infer_method() → Callable
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L77"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Prompt`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L78"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L82"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StringPrompt`




<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L86"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(content: str)
```






**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `content`: `<class 'str'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L90"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → str
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L93"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: WeaveObject) → Self
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L102"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `MessagesPrompt`




<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L106"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(messages: list[dict])
```






**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `messages`: `list[dict]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L119"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format`

```python
format(**kwargs: Any) → list
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L110"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `format_message`

```python
format_message(message: dict, **kwargs: Any) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/prompt/prompt.py#L122"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: WeaveObject) → Self
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval.py#L56"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `dataset`: `<class 'flow.dataset.Dataset'>`
- `scorers`: `typing.Optional[list[typing.Annotated[typing.Union[trace.op.Op, flow.scorer.Scorer], BeforeValidator(func=<function cast_to_scorer at 0x10dcb5260>)]]]`
- `preprocess_model_input`: `typing.Optional[typing.Callable[[dict], dict]]`
- `trials`: `<class 'int'>`
- `evaluation_name`: `typing.Union[str, typing.Callable[[trace.weave_client.Call], str], NoneType]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L237"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `evaluate`

```python
evaluate(model: Union[Op, Model]) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval.py#L114"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: WeaveObject) → Self
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval.py#L195"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_eval_results`

```python
get_eval_results(model: Union[Op, Model]) → EvaluationResults
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L140"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `predict_and_score`

```python
predict_and_score(model: Union[Op, Model], example: dict) → dict
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L172"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `summarize`

```python
summarize(eval_table: EvaluationResults) → dict
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval_imperative.py#L306"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EvaluationLogger`
This class provides an imperative interface for logging evaluations. 

An evaluation is started automatically when the first prediction is logged using the `log_prediction` method, and finished when the `log_summary` method is called. 

Each time you log a prediction, you will get back a `ScoreLogger` object. You can use this object to log scores and metadata for that specific prediction. For more information, see the `ScoreLogger` class. 



**Example:**
 ```python
     ev = EvaluationLogger()
     pred = ev.log_prediction(inputs, output)
     pred.log_score(scorer_name, score)
     ev.log_summary(summary)
    ``` 


**Pydantic Fields:**

- `name`: `str | None`
- `model`: `flow.model.Model | dict | str`
- `dataset`: `flow.dataset.Dataset | list[dict] | str`
---

#### <kbd>property</kbd> ui_url







---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval_imperative.py#L567"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `finish`

```python
finish() → None
```

Clean up the evaluation resources explicitly without logging a summary. 

Ensures all prediction calls and the main evaluation call are finalized. This is automatically called if the logger is used as a context manager. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval_imperative.py#L490"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `log_prediction`

```python
log_prediction(inputs: 'dict', output: 'Any') → ScoreLogger
```

Log a prediction to the Evaluation, and return a reference. 

The reference can be used to log scores which are attached to the specific prediction instance. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/eval_imperative.py#L521"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `log_summary`

```python
log_summary(summary: 'dict | None' = None, auto_summarize: 'bool' = True) → None
```

Log a summary dict to the Evaluation. 

This will calculate the summary, call the summarize op, and then finalize the evaluation, meaning no more predictions or scores can be logged. 


---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/scorer.py#L19"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Scorer`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `column_map`: `typing.Optional[dict[str, str]]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/scorer.py#L25"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `model_post_init`

```python
model_post_init(_Scorer__context: Any) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L29"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `score`

```python
score(output: Any, **kwargs: Any) → Any
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L33"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `summarize`

```python
summarize(score_rows: list) → Optional[dict]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/builtin_object_classes/annotation_spec.py#L12"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `AnnotationSpec`





**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `field_schema`: `dict[str, typing.Any]`
- `unique_among_creators`: `<class 'bool'>`
- `op_scope`: `typing.Optional[list[str]]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/builtin_object_classes/annotation_spec.py#L47"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `preprocess_field_schema`

```python
preprocess_field_schema(data: dict[str, Any]) → dict[str, Any]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/builtin_object_classes/annotation_spec.py#L92"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `validate_field_schema`

```python
validate_field_schema(schema: dict[str, Any]) → dict[str, Any]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/builtin_object_classes/annotation_spec.py#L103"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `value_is_valid`

```python
value_is_valid(payload: Any) → bool
```

Validates a payload against this annotation spec's schema. 



**Args:**
 
 - <b>`payload`</b>:  The data to validate against the schema 



**Returns:**
 
 - <b>`bool`</b>:  True if validation succeeds, False otherwise 


---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/File/file.py#L20"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `File`
A class representing a file with path, mimetype, and size information. 

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/File/file.py#L23"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(path: 'str | Path', mimetype: 'str | None' = None)
```

Initialize a File object. 



**Args:**
 
 - <b>`path`</b>:  Path to the file (string or pathlib.Path) 
 - <b>`mimetype`</b>:  Optional MIME type of the file - will be inferred from extension if not provided 


---

#### <kbd>property</kbd> filename

Get the filename of the file. 



**Returns:**
 
 - <b>`str`</b>:  The name of the file without the directory path. 



---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/File/file.py#L49"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `open`

```python
open() → bool
```

Open the file using the operating system's default application. 

This method uses the platform-specific mechanism to open the file with the default application associated with the file's type. 



**Returns:**
 
 - <b>`bool`</b>:  True if the file was successfully opened, False otherwise. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/File/file.py#L70"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `save`

```python
save(dest: 'str | Path') → None
```

Copy the file to the specified destination path. 



**Args:**
 
 - <b>`dest`</b>:  Destination path where the file will be copied to (string or pathlib.Path)  The destination path can be a file or a directory. 


---

<a href="https://github.com/wandb/weave/blob/master/rich/markdown.py#L519"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Markdown`
A Markdown renderable. 



**Args:**
 
 - <b>`markup`</b> (str):  A string containing markdown. 
 - <b>`code_theme`</b> (str, optional):  Pygments theme for code blocks. Defaults to "monokai". 
 - <b>`justify`</b> (JustifyMethod, optional):  Justify value for paragraphs. Defaults to None. 
 - <b>`style`</b> (Union[str, Style], optional):  Optional style to apply to markdown. 
 - <b>`hyperlinks`</b> (bool, optional):  Enable hyperlinks. Defaults to ``True``. 
 - <b>`inline_code_lexer`</b>:  (str, optional): Lexer to use if inline code highlighting is  enabled. Defaults to None. 
 - <b>`inline_code_theme`</b>:  (Optional[str], optional): Pygments theme for inline code  highlighting, or None for no highlighting. Defaults to None. 

<a href="https://github.com/wandb/weave/blob/master/rich/markdown.py#L555"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    markup: 'str',
    code_theme: 'str' = 'monokai',
    justify: 'Optional[JustifyMethod]' = None,
    style: 'Union[str, Style]' = 'none',
    hyperlinks: 'bool' = True,
    inline_code_lexer: 'Optional[str]' = None,
    inline_code_theme: 'Optional[str]' = None
) → None
```









---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/monitor.py#L14"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Monitor`
Sets up a monitor to score incoming calls automatically. 



**Examples:**
 

```python
import weave
from weave.scorers import ValidJSONScorer

json_scorer = ValidJSONScorer()

my_monitor = weave.Monitor(
     name="my-monitor",
     description="This is a test monitor",
     sampling_rate=0.5,
     op_names=["my_op"],
     query={
         "$expr": {
             "$gt": [
                 {
                         "$getField": "started_at"
                     },
                     {
                         "$literal": 1742540400
                     }
                 ]
             }
         }
     },
     scorers=[json_scorer],
)

my_monitor.activate()
``` 


**Pydantic Fields:**

- `name`: `typing.Optional[str]`
- `description`: `typing.Optional[str]`
- `ref`: `typing.Optional[trace.refs.ObjectRef]`
- `sampling_rate`: `<class 'float'>`
- `scorers`: `list[flow.scorer.Scorer]`
- `op_names`: `list[str]`
- `query`: `typing.Optional[trace_server.interface.query.Query]`
- `active`: `<class 'bool'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/monitor.py#L58"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `activate`

```python
activate() → ObjectRef
```

Activates the monitor. 



**Returns:**
  The ref to the monitor. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/monitor.py#L68"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `deactivate`

```python
deactivate() → ObjectRef
```

Deactivates the monitor. 



**Returns:**
  The ref to the monitor. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/monitor.py#L78"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_obj`

```python
from_obj(obj: WeaveObject) → Self
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L493"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SavedView`
A fluent-style class for working with SavedView objects. 

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L499"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(view_type: 'str' = 'traces', label: 'str' = 'SavedView') → None
```






---

#### <kbd>property</kbd> entity





---

#### <kbd>property</kbd> label





---

#### <kbd>property</kbd> project





---

#### <kbd>property</kbd> view_type







---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L623"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_column`

```python
add_column(path: 'str | ObjectPath', label: 'str | None' = None) → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L632"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_columns`

```python
add_columns(*columns: 'str') → SavedView
```

Convenience method for adding multiple columns to the grid. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L524"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_filter`

```python
add_filter(
    field: 'str',
    operator: 'str',
    value: 'Any | None' = None
) → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L598"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_sort`

```python
add_sort(field: 'str', direction: 'SortDirection') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L663"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `column_index`

```python
column_index(path: 'int | str | ObjectPath') → int
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L578"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `filter_op`

```python
filter_op(op_name: 'str | None') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L847"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_calls`

```python
get_calls(
    limit: 'int | None' = None,
    offset: 'int | None' = None,
    include_costs: 'bool' = False,
    include_feedback: 'bool' = False,
    all_columns: 'bool' = False
) → CallsIter
```

Get calls matching this saved view's filters and settings. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L905"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_known_columns`

```python
get_known_columns(num_calls_to_query: 'int | None' = None) → list[str]
```

Get the set of columns that are known to exist. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L915"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_table_columns`

```python
get_table_columns() → list[TableColumn]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L617"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `hide_column`

```python
hide_column(col_name: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L638"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `insert_column`

```python
insert_column(
    idx: 'int',
    path: 'str | ObjectPath',
    label: 'str | None' = None
) → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L972"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `load`

```python
load(ref: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L741"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `page_size`

```python
page_size(page_size: 'int') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L711"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `pin_column_left`

```python
pin_column_left(col_name: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L721"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `pin_column_right`

```python
pin_column_right(col_name: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L683"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_column`

```python
remove_column(path: 'int | str | ObjectPath') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L702"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_columns`

```python
remove_columns(*columns: 'str') → SavedView
```

Remove columns from the saved view. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L547"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_filter`

```python
remove_filter(index_or_field: 'int | str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L562"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_filters`

```python
remove_filters() → SavedView
```

Remove all filters from the saved view. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L520"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `rename`

```python
rename(label: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L677"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `rename_column`

```python
rename_column(path: 'int | str | ObjectPath', label: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L832"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `save`

```python
save() → SavedView
```

Publish the saved view to the server. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L657"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_columns`

```python
set_columns(*columns: 'str') → SavedView
```

Set the columns to be displayed in the grid. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L611"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `show_column`

```python
show_column(col_name: 'str') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L605"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `sort_by`

```python
sort_by(field: 'str', direction: 'SortDirection') → SavedView
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L888"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `to_grid`

```python
to_grid(limit: 'int | None' = None) → Grid
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L769"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `to_rich_table_str`

```python
to_rich_table_str() → str
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L753"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ui_url`

```python
ui_url() → str | None
```

URL to show this saved view in the UI. 

Note this is the "result" page with traces etc, not the URL for the view object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/flow/saved_view.py#L731"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `unpin_column`

```python
unpin_column(col_name: 'str') → SavedView
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/Audio/audio.py#L83"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Audio`
A class representing audio data in a supported format (wav or mp3). 

This class handles audio data storage and provides methods for loading from different sources and exporting to files. 



**Attributes:**
 
 - <b>`format`</b>:  The audio format (currently supports 'wav' or 'mp3') 
 - <b>`data`</b>:  The raw audio data as bytes 



**Args:**
 
 - <b>`data`</b>:  The audio data (bytes or base64 encoded string) 
 - <b>`format`</b>:  The audio format ('wav' or 'mp3') 
 - <b>`validate_base64`</b>:  Whether to attempt base64 decoding of the input data 



**Raises:**
 
 - <b>`ValueError`</b>:  If audio data is empty or format is not supported 

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/Audio/audio.py#L108"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    data: 'bytes',
    format: 'SUPPORTED_FORMATS_TYPE',
    validate_base64: 'bool' = True
) → None
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/Audio/audio.py#L176"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `export`

```python
export(path: 'str | bytes | Path | PathLike') → None
```

Export audio data to a file. 



**Args:**
 
 - <b>`path`</b>:  Path where the audio file should be written 

---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/Audio/audio.py#L123"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_data`

```python
from_data(data: 'str | bytes', format: 'str') → Audio
```

Create an Audio object from raw data and specified format. 



**Args:**
 
 - <b>`data`</b>:  Audio data as bytes or base64 encoded string 
 - <b>`format`</b>:  Audio format ('wav' or 'mp3') 



**Returns:**
 
 - <b>`Audio`</b>:  A new Audio instance 



**Raises:**
 
 - <b>`ValueError`</b>:  If format is not supported 

---

<a href="https://github.com/wandb/weave/blob/master/weave/type_handlers/Audio/audio.py#L148"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_path`

```python
from_path(path: 'str | bytes | Path | PathLike') → Audio
```

Create an Audio object from a file path. 



**Args:**
 
 - <b>`path`</b>:  Path to an audio file (must have .wav or .mp3 extension) 



**Returns:**
 
 - <b>`Audio`</b>:  A new Audio instance loaded from the file 



**Raises:**
 
 - <b>`ValueError`</b>:  If file doesn't exist or has unsupported extension 

