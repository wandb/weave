

# API Overview

## Modules

- No modules

## Classes

- [`obj.Object`](./weave.flow.obj.md#class-object)
- [`dataset.Dataset`](./weave.flow.dataset.md#class-dataset): Dataset object with easy saving and automatic versioning
- [`model.Model`](./weave.flow.model.md#class-model): Intended to capture a combination of code and data the operates on an input.
- [`eval.Evaluation`](./weave.flow.eval.md#class-evaluation): Sets up an evaluation which includes a set of scorers and a dataset.
- [`scorer.Scorer`](./weave.flow.scorer.md#class-scorer)

## Functions

- [`trace_api.init`](./weave.trace_api.md#function-init): Initialize weave tracking, logging to a wandb project.
- [`trace_api.publish`](./weave.trace_api.md#function-publish): Save and version a python object.
- [`trace_api.ref`](./weave.trace_api.md#function-ref): Construct a Ref to a Weave object.
- [`call_context.get_current_call`](./weave.call_context.md#function-get_current_call): Get the Call object for the currently executing Op, within that Op.
- [`trace_api.finish`](./weave.trace_api.md#function-finish): Stops logging to weave.
- [`op.op`](./weave.trace.op.md#function-op): A decorator to weave op-ify a function or method.  Works for both sync and async.

---

---

### <kbd>function</kbd> `init`

```python
init(
    project_name: str,
    settings: Optional[weave.trace.settings.UserSettings, dict[str, Any]] = None
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
op(
    *args: Any,
    **kwargs: Any
) → Union[Callable[[Any], weave.trace.op.Op], weave.trace.op.Op]
```

A decorator to weave op-ify a function or method.  Works for both sync and async. 

Decorated functions and methods can be called as normal, but will also automatically track calls in the Weave UI. 

If you don't call `weave.init` then the function will behave as if it were not decorated. 



Example usage: ```
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
            
```python
class Dataset(Object):
    """
    Dataset object with easy saving and automatic versioning

    Examples:
        ```
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
    """

    rows: weave.Table

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            table_ref = getattr(rows, "table_ref", None)
            if isinstance(rows, WeaveTable):
                rows = list(rows)
            rows = weave.Table(rows)
            if table_ref:
                rows.table_ref = table_ref
        if len(rows.rows) == 0:
            raise ValueError("Attempted to construct a Dataset with an empty list.")
        for row in rows.rows:
            if not isinstance(row, dict):
                raise ValueError(
                    "Attempted to construct a Dataset with a non-dict object. Found type: "
                    + str(type(row))
                    + " of row: "
                    + short_str(row)
                )
            if len(row) == 0:
                raise ValueError(
                    "Attempted to construct a Dataset row with an empty dict."
                )
        return rows

```
            
---
## <kbd>class</kbd> `Model`
            
```python
class Model(Object):
    """
    Intended to capture a combination of code and data the operates on an input.
    For example it might call an LLM with a prompt to make a prediction or generate
    text.

    When you change the attributes or the code that defines your model, these changes
    will be logged and the version will be updated. This ensures that you can compare
    the predictions across different versions of your model. Use this to iterate on
    prompts or to try the latest LLM and compare predictions across different settings

    Examples:
    ```
        class YourModel(Model):
            attribute1: str
            attribute2: int

            @weave.op()
            def predict(self, input_data: str) -> dict:
                # Model logic goes here
                prediction = self.attribute1 + ' ' + input_data
                return {'pred': prediction}
    ```
    """

    # TODO: should be infer: Callable

    def get_infer_method(self) -> Callable:
        for infer_method_names in ("predict", "infer", "forward"):
            infer_method = getattr(self, infer_method_names, None)
            if infer_method:
                return infer_method
        raise ValueError(
            f"Model {self} does not have a predict, infer, or forward method."
        )

```
            
---
## <kbd>class</kbd> `Evaluation`
            
```python
class Evaluation(Object):
    """
    Sets up an evaluation which includes a set of scorers and a dataset.

    Calling evaluation.evaluate(model) will pass in rows from a dataset into a model matching
        the names of the columns of the dataset to the argument names in model.predict.

    Then it will call all of the scorers and save the results in weave.

    If you want to preprocess the rows from the dataset you can pass in a function
    to preprocess_model_input.

    Examples:

    ```
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
    """

    dataset: Union[Dataset, list]
    scorers: Optional[list[Union[Callable, Op, Scorer]]] = None
    preprocess_model_input: Optional[Callable] = None
    trials: int = 1

    def model_post_init(self, __context: Any) -> None:
        scorers: list[Union[Callable, Scorer, Op]] = []
        for scorer in self.scorers or []:
            if isinstance(scorer, Scorer):
                pass
            elif isinstance(scorer, type):
                raise ValueError(
                    f"Scorer {scorer.__name__} must be an instance, not a class. Did you forget to instantiate?"
                )
            elif callable(scorer) and not isinstance(scorer, Op):
                scorer = weave.op()(scorer)
            elif isinstance(scorer, Op):
                pass
            else:
                raise ValueError(f"Invalid scorer: {scorer}")
            scorers.append(scorer)
        self.scorers = scorers

        if isinstance(self.dataset, list):
            self.dataset = Dataset(rows=self.dataset)

        if self.name is None and self.dataset.name is not None:
            self.name = self.dataset.name + "-evaluation"  # type: ignore

    @weave.op()
    async def predict_and_score(
        self, model: Union[Callable, Model], example: dict
    ) -> dict:
        if self.preprocess_model_input is None:
            model_input = example
        else:
            model_input = self.preprocess_model_input(example)  # type: ignore

        if callable(model):
            model_predict = model
        else:
            model_predict = get_infer_method(model)

        model_predict_fn_name = (
            model_predict.name
            if isinstance(model_predict, Op)
            else model_predict.__name__
        )

        if isinstance(model_predict, Op):
            predict_signature = model_predict.signature
        else:
            predict_signature = inspect.signature(model_predict)
        model_predict_arg_names = list(predict_signature.parameters.keys())

        if isinstance(model_input, dict):
            model_predict_args = {
                k: v for k, v in model_input.items() if k in model_predict_arg_names
            }
        else:
            if len(model_predict_arg_names) == 1:
                model_predict_args = {model_predict_arg_names[0]: model_input}
            else:
                raise ValueError(
                    f"{model_predict} expects arguments: {model_predict_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                )
        try:
            model_start_time = time.time()
            model_output = await async_call(model_predict, **model_predict_args)
        except OpCallError as e:
            dataset_column_names = list(example.keys())
            dataset_column_names_str = ", ".join(dataset_column_names[:3])
            if len(dataset_column_names) > 3:
                dataset_column_names_str += ", ..."
            required_arg_names = [
                param.name
                for param in predict_signature.parameters.values()
                if param.default == inspect.Parameter.empty
            ]

            message = textwrap.dedent(
                f"""
                Call error: {e}

                Options for resolving:
                a. change {model_predict_fn_name} argument names to match a subset of dataset column names: {dataset_column_names_str}
                b. change dataset column names to match expected {model_predict_fn_name} argument names: {required_arg_names}
                c. construct Evaluation with a preprocess_model_input function that accepts a dataset example and returns a dict with keys expected by {model_predict_fn_name}
                """
            )
            raise OpCallError(message)
        except Exception as e:
            print("model_output failed")
            traceback.print_exc()
            model_output = None
        model_latency = time.time() - model_start_time

        scores = {}
        scorers = typing.cast(list[Union[Op, Scorer]], self.scorers or [])
        for scorer in scorers:
            scorer_name, score_fn, _ = get_scorer_attributes(scorer)
            if isinstance(score_fn, Op):
                score_signature = score_fn.signature
            else:
                score_signature = inspect.signature(score_fn)
            score_arg_names = list(score_signature.parameters.keys())

            if "model_output" not in score_arg_names:
                raise OpCallError(
                    f"Scorer {scorer_name} must have a 'model_output' argument, to receive the output of the model function."
                )

            if isinstance(example, dict):
                score_args = {k: v for k, v in example.items() if k in score_arg_names}
            else:
                if len(score_arg_names) == 2:
                    score_args = {score_arg_names[0]: example}
                else:
                    raise ValueError(
                        f"{score_fn} expects arguments: {score_arg_names}, provide a preprocess_model_input function that returns a dict with those keys."
                    )
            score_args["model_output"] = model_output

            try:
                result = await async_call(score_fn, **score_args)
            except OpCallError as e:
                dataset_column_names = list(example.keys())
                dataset_column_names_str = ", ".join(dataset_column_names[:3])
                if len(dataset_column_names) > 3:
                    dataset_column_names_str += ", ..."
                required_arg_names = [
                    param.name
                    for param in score_signature.parameters.values()
                    if param.default == inspect.Parameter.empty
                ]
                required_arg_names.remove("model_output")

                message = textwrap.dedent(
                    f"""
                    Call error: {e}

                    Options for resolving:
                    a. change {scorer_name} argument names to match a subset of dataset column names ({dataset_column_names_str})
                    b. change dataset column names to match expected {scorer_name} argument names: {required_arg_names}
                    """
                )
                raise OpCallError(message)
            scores[scorer_name] = result

        return {
            "model_output": model_output,
            "scores": scores,
            "model_latency": model_latency,
        }

    @weave.op()
    async def summarize(self, eval_table: EvaluationResults) -> dict:
        eval_table_rows = list(eval_table.rows)
        cols = transpose(eval_table_rows)
        summary = {}

        for name, vals in cols.items():
            if name == "scores":
                scorers = self.scorers or []
                for scorer in scorers:
                    scorer_name, _, summarize_fn = get_scorer_attributes(scorer)
                    scorer_stats = transpose(vals)
                    score_table = scorer_stats[scorer_name]
                    scored = summarize_fn(score_table)
                    summary[scorer_name] = scored
            else:
                model_output_summary = auto_summarize(vals)
                if model_output_summary:
                    summary[name] = model_output_summary

        return summary

    @weave.op()
    async def evaluate(self, model: Union[Callable, Model]) -> dict:
        if not is_valid_model(model):
            raise ValueError(INVALID_MODEL_ERROR)
        eval_rows = []

        start_time = time.time()

        async def eval_example(example: dict) -> dict:
            try:
                eval_row = await self.predict_and_score(model, example)
            except OpCallError as e:
                raise e
            except Exception as e:
                print("Predict and score failed")
                traceback.print_exc()
                return {"model_output": None, "scores": {}}
            return eval_row

        n_complete = 0
        # with console.status("Evaluating...") as status:
        dataset = typing.cast(Dataset, self.dataset)
        _rows = dataset.rows
        trial_rows = list(_rows) * self.trials
        async for example, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            n_complete += 1
            duration = time.time() - start_time
            print(f"Evaluated {n_complete} of {len(trial_rows)} examples")
            # status.update(
            #     f"Evaluating... {duration:.2f}s [{n_complete} / {len(self.dataset.rows)} complete]"  # type:ignore
            # )
            if eval_row is None:
                eval_row = {"model_output": None, "scores": {}}
            else:
                eval_row["scores"] = eval_row.get("scores", {})
            for scorer in self.scorers or []:
                scorer_name, _, _ = get_scorer_attributes(scorer)
                if scorer_name not in eval_row["scores"]:
                    eval_row["scores"][scorer_name] = {}
            eval_rows.append(eval_row)

        # The need for this pattern is quite unfortunate and highlights a gap in our
        # data model. As a user, I just want to pass a list of data `eval_rows` to
        # summarize. Under the hood, Weave should choose the appropriate storage
        # format (in this case `Table`) and serialize it that way. Right now, it is
        # just a huge list of dicts. The fact that "as a user" I need to construct
        # `weave.Table` at all is a leaky abstraction. Moreover, the need to
        # construct `EvaluationResults` just so that tracing and the UI works is
        # also bad. In the near-term, this will at least solve the problem of
        # breaking summarization with big datasets, but this is not the correct
        # long-term solution.
        eval_results = EvaluationResults(rows=weave.Table(eval_rows))
        summary = await self.summarize(eval_results)

        print("Evaluation summary", summary)

        return summary

```
            
---
## <kbd>class</kbd> `Scorer`
            
```python
class Scorer(Object):
    def score(self, target: Any, model_output: Any) -> Any:
        raise NotImplementedError

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        return auto_summarize(score_rows)

```
            