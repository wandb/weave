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
- [`eval.Evaluation`](#class-evaluation): Sets up an evaluation which includes a set of scorers and a dataset.
- [`scorer.Scorer`](#class-scorer)

## Functions

- [`trace_api.init`](#function-init): Initialize weave tracking, logging to a wandb project.
- [`trace_api.publish`](#function-publish): Save and version a python object.
- [`trace_api.ref`](#function-ref): Construct a Ref to a Weave object.
- [`call_context.get_current_call`](#function-get_current_call): Get the Call object for the currently executing Op, within that Op.
- [`trace_api.finish`](#function-finish): Stops logging to weave.
- [`op.op`](#function-op): A decorator to weave op-ify a function or method.  Works for both sync and async.


---


### <kbd>function</kbd> `init`

```python
init(
    project_name: str,
    settings: Optional[UserSettings, dict[str, Any]] = None
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

### <kbd>function</kbd> `publish`

```python
publish(obj: Any, name: Optional[str] = None) → ObjectRef
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

### <kbd>function</kbd> `ref`

```python
ref(location: str) → ObjectRef
```

Construct a Ref to a Weave object. 

TODO: what happens if obj does not exist 



**Args:**
 
 - <b>`location`</b>:  A fully-qualified weave ref URI, or if weave.init() has been called, "name:version" or just "name" ("latest" will be used for version in this case). 





**Returns:**
 A weave Ref to the object. 

---

### <kbd>function</kbd> `get_current_call`

```python
get_current_call() → Optional[ForwardRef('Call')]
```

Get the Call object for the currently executing Op, within that Op. 

This allows you to access attributes of the Call such as its id or feedback while it is running. 

```python
@weave.op
def hello(name: str) -> None:
     print(f"Hello {name}!")
     current_call = weave.get_current_call()
     print(current_call.id)
``` 

It is also possible to access a Call after the Op has returned. 

If you have the Call's id, perhaps from the UI, you can use the `call` method on the `WeaveClient` returned from `weave.init` to retrieve the Call object. 

```python
client = weave.init("<project>")
mycall = client.call("<call_id>")
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
  The Call object for the currently executing Op, or  None if tracking has not been initialized or this method is  invoked outside an Op. 

---

### <kbd>function</kbd> `finish`

```python
finish() → None
```

Stops logging to weave. 

Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging. 

---

### <kbd>function</kbd> `op`

```python
op(*args: Any, **kwargs: Any) → Union[Callable[[Any], Op], Op]
```

A decorator to weave op-ify a function or method.  Works for both sync and async. 

Decorated functions and methods can be called as normal, but will also automatically track calls in the Weave UI. 

If you don't call `weave.init` then the function will behave as if it were not decorated. 



Example usage: 

```python
import weave
weave.init("my-project")

@weave.op
async def extract():
     return await client.chat.completions.create(
         model="gpt-4-turbo",
         messages=[
             {"role": "user", "content": "Create a user as JSON"},
         ],
     )

await extract()  # calls the function and tracks the call in the Weave UI
``` 

---
## <kbd>class</kbd> `Object`
            
```python
class Object(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    # Allow Op attributes
    model_config = ConfigDict(
        ignored_types=(Op,),
        arbitrary_types_allowed=True,
        protected_namespaces=(),
        extra="forbid",
    )

    __str__ = BaseModel.__repr__

    # This is a "wrap" validator meaning we can run our own logic before
    # and after the standard pydantic validation.
    @model_validator(mode="wrap")
    @classmethod
    def handle_relocatable_object(
        cls, v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> Any:
        if isinstance(v, ObjectRef):
            return v.get()
        if isinstance(v, WeaveObject):
            # This is a relocated object, so destructure it into a dictionary
            # so pydantic can validate it.
            keys = v._val.__dict__.keys()
            fields = {}
            for k in keys:
                if k.startswith("_"):
                    continue
                val = getattr(v, k)
                fields[k] = val

            # pydantic validation will construct a new pydantic object
            def is_ignored_type(v: type) -> bool:
                return isinstance(v, cls.model_config["ignored_types"])

            allowed_fields = {k: v for k, v in fields.items() if not is_ignored_type(v)}
            new_obj = handler(allowed_fields)
            for k, kv in fields.items():
                if is_ignored_type(kv):
                    new_obj.__dict__[k] = kv

            # transfer ref to new object
            # We can't attach a ref directly to pydantic objects yet.
            # TODO: fix this. I think dedupe may make it so the user data ends up
            #    working fine, but not setting a ref here will cause the client
            #    to do extra work.
            if isinstance(v, WeaveObject):
                ref = get_ref(v)
                new_obj.__dict__["ref"] = ref
            # return new_obj

            return new_obj
        return handler(v)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)

        # This binds the call "method" to the Op instance
        # - before:  obj.method.call(obj, ...)
        # - after:   obj.method.call(...)
        for k in dir(self):
            if not k.startswith("__") and isinstance(getattr(self, k), Op):
                op = getattr(self, k)
                op.__dict__["call"] = partial(call, op, self)

```
            
---

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


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

### <kbd>classmethod</kbd> `convert_to_table`

```python
convert_to_table(rows: Any) → Table
```






---

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


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

### <kbd>method</kbd> `get_infer_method`

```python
get_infer_method() → Callable
```






---

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


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

### <kbd>method</kbd> `evaluate`

```python
evaluate(model: Union[Callable, Model]) → dict
```





---

### <kbd>method</kbd> `model_post_init`

```python
model_post_init(_Evaluation__context: Any) → None
```





---

### <kbd>method</kbd> `predict_and_score`

```python
predict_and_score(model: Union[Callable, Model], example: dict) → dict
```





---

### <kbd>method</kbd> `summarize`

```python
summarize(eval_table: EvaluationResults) → dict
```






---

## <kbd>class</kbd> `Scorer`





---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

### <kbd>method</kbd> `score`

```python
score(target: Any, model_output: Any) → Any
```





---

### <kbd>method</kbd> `summarize`

```python
summarize(score_rows: list) → Optional[dict]
```





