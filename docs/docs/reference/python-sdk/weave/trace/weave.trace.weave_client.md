---
sidebar_label: weave_client
---
    

# weave.trace.weave_client



---


# API Overview



## Classes

- [`weave_client.WeaveClient`](#class-weaveclient)
- [`weave_client.Call`](#class-call): A Call represents a single operation that was executed as part of a trace.

## Functions

- [`weave_client.PaginatedIterator`](#function-paginatediterator)


---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L862"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `WeaveClient`




<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L887"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    entity: 'str',
    project: 'str',
    server: 'TraceServerInterface',
    ensure_project_exists: 'bool' = True
)
```






---

#### <kbd>property</kbd> num_outstanding_jobs

Returns the total number of pending jobs across all executors and the server. 

This property can be used to check the progress of background tasks without blocking the main thread. 



**Returns:**
 
 - <b>`int`</b>:  The total number of pending jobs 



---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L1533"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_cost`

```python
add_cost(
    llm_id: 'str',
    prompt_token_cost: 'float',
    completion_token_cost: 'float',
    effective_date: 'datetime | None' = datetime.datetime(2025, 5, 30, 18, 48, 51, 884703, tzinfo=datetime.timezone.utc),
    prompt_token_cost_unit: 'str | None' = 'USD',
    completion_token_cost_unit: 'str | None' = 'USD',
    provider_id: 'str | None' = 'default'
) → CostCreateRes
```

Add a cost to the current project. 



**Examples:**
 

```python
     client.add_cost(llm_id="my_expensive_custom_model", prompt_token_cost=1, completion_token_cost=2)
     client.add_cost(llm_id="my_expensive_custom_model", prompt_token_cost=500, completion_token_cost=1000, effective_date=datetime(1998, 10, 3))
    ``` 



**Args:**
 
 - <b>`llm_id`</b>:  The ID of the LLM. eg "gpt-4o-mini-2024-07-18" 
 - <b>`prompt_token_cost`</b>:  The cost per prompt token. eg .0005 
 - <b>`completion_token_cost`</b>:  The cost per completion token. eg .0015 
 - <b>`effective_date`</b>:  Defaults to the current date. A datetime.datetime object. 
 - <b>`provider_id`</b>:  The provider of the LLM. Defaults to "default". eg "openai" 
 - <b>`prompt_token_cost_unit`</b>:  The unit of the cost for the prompt tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time") 
 - <b>`completion_token_cost_unit`</b>:  The unit of the cost for the completion tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time") 



**Returns:**
 A CostCreateRes object. Which has one field called a list of tuples called ids. Each tuple contains the llm_id and the id of the created cost object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L1121"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call`

```python
call(call_id: 'str', include_costs: 'bool' = False) → WeaveObject
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L1075"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls`

```python
calls(
    filter: 'CallsFilter | None' = None,
    include_costs: 'bool' = False
) → CallsIter
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1129"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `create_call`

```python
create_call(
    op: 'str | Op',
    inputs: 'dict',
    parent: 'Call | None' = None,
    attributes: 'dict | None' = None,
    display_name: 'str | Callable[[Call], str] | None' = None,
    use_stack: 'bool' = True
) → Call
```

Create, log, and push a call onto the runtime stack. 



**Args:**
 
 - <b>`op`</b>:  The operation producing the call, or the name of an anonymous operation. 
 - <b>`inputs`</b>:  The inputs to the operation. 
 - <b>`parent`</b>:  The parent call. If parent is not provided, the current run is used as the parent. 
 - <b>`display_name`</b>:  The display name for the call. Defaults to None. 
 - <b>`attributes`</b>:  The attributes for the call. Defaults to None. 
 - <b>`use_stack`</b>:  Whether to push the call onto the runtime stack. Defaults to True. 



**Returns:**
 The created Call object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1400"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete_call`

```python
delete_call(call: 'Call') → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1409"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete_calls`

```python
delete_calls(call_ids: 'list[str]') → None
```

Delete calls by their IDs. 

Deleting a call will also delete all of its children. 



**Args:**
 
 - <b>`call_ids`</b>:  A list of call IDs to delete. Ex: ["2F0193e107-8fcf-7630-b576-977cc3062e2e"] 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1425"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete_object_version`

```python
delete_object_version(object: 'ObjectRef') → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1435"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete_op_version`

```python
delete_op_version(op: 'OpRef') → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1395"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `fail_call`

```python
fail_call(call: 'Call', exception: 'BaseException') → None
```

Fail a call with an exception. This is a convenience method for finish_call. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L1520"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback`

```python
feedback(
    query: 'Query | str | None' = None,
    reaction: 'str | None' = None,
    offset: 'int' = 0,
    limit: 'int' = 100
) → FeedbackQuery
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L2127"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `finish`

```python
finish(
    use_progress_bar: 'bool' = True,
    callback: 'Callable[[FlushStatus], None] | None' = None
) → None
```

Flushes all background tasks to ensure they are processed. 

This method blocks until all currently enqueued jobs are processed, displaying a progress bar to show the status of the pending tasks. It ensures parallel processing during main thread execution and can improve performance when user code completes before data has been uploaded to the server. 



**Args:**
 
 - <b>`use_progress_bar`</b>:  Whether to display a progress bar during flush.  Set to False for environments where a progress bar  would not render well (e.g., CI environments). 
 - <b>`callback`</b>:  Optional callback function that receives status updates.  Overrides use_progress_bar. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1282"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `finish_call`

```python
finish_call(
    call: 'Call',
    output: 'Any' = None,
    exception: 'BaseException | None' = None,
    op: 'Op | None' = None
) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L2158"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `flush`

```python
flush() → None
```

Flushes background asynchronous tasks, safe to call multiple times. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L947"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get`

```python
get(ref: 'ObjectRef', objectify: 'bool' = True) → Any
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1083"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_call`

```python
get_call(
    call_id: 'str',
    include_costs: 'bool' = False,
    include_feedback: 'bool' = False,
    columns: 'list[str] | None' = None
) → WeaveObject
```

Get a single call by its ID. 



**Args:**
 
 - <b>`call_id`</b>:  The ID of the call to get. 
 - <b>`include_costs`</b>:  If true, cost info is included at summary.weave 
 - <b>`include_feedback`</b>:  If true, feedback info is included at summary.weave.feedback 
 - <b>`columns`</b>:  A list of columns to include in the response. If None,  all columns are included. Specifying fewer columns may be more performant. 
 - <b>`Some columns are always included`</b>:  id, project_id, trace_id, op_name, started_at 



**Returns:**
 A call object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L1005"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_calls`

```python
get_calls(
    filter: 'CallsFilter | None' = None,
    limit: 'int | None' = None,
    offset: 'int | None' = None,
    sort_by: 'list[SortBy] | None' = None,
    query: 'Query | None' = None,
    include_costs: 'bool' = False,
    include_feedback: 'bool' = False,
    columns: 'list[str] | None' = None,
    scored_by: 'str | list[str] | None' = None,
    page_size: 'int' = 1000
) → CallsIter
```

Retrieve a list of traced calls (operations) for this project. 

This method provides a powerful and flexible interface for querying trace data. It supports pagination, filtering, sorting, field projection, and scoring metadata, and can be used to power custom trace UIs or analysis tools. 

Performance Tip: Specify `columns` and use `filter` or `query` to reduce result size. 



**Args:**
 
 - <b>``filter``</b>:  High-level filter for narrowing results by fields like `op_name`, `parent_ids`, etc. 
 - <b>``limit``</b>:  Maximum number of calls to return. 
 - <b>``offset``</b>:  Number of calls to skip before returning results (used for pagination). 
 - <b>``sort_by``</b>:  List of fields to sort the results by (e.g., `started_at desc`). 
 - <b>``query``</b>:  A mongo-like expression for advanced filtering. Not all Mongo operators are supported. 
 - <b>``include_costs``</b>:  If True, includes token/cost info in `summary.weave`. 
 - <b>``include_feedback``</b>:  If True, includes feedback in `summary.weave.feedback`. 
 - <b>``columns``</b>:  List of fields to return per call. Reducing this can significantly improve performance.  (Some fields like `id`, `trace_id`, `op_name`, and `started_at` are always included.) 
 - <b>``scored_by``</b>:  Filter by one or more scorers (name or ref URI). Multiple scorers are ANDed. 
 - <b>``page_size``</b>:  Number of calls fetched per page. Tune this for performance in large queries. 



**Returns:**
 
 - <b>``CallsIter``</b>:  An iterator over `Call` objects. Supports slicing, iteration, and `.to_pandas()`. 



**Example:**
 ```python
    calls = client.get_calls(
         filter=CallsFilter(op_names=["my_op"]),
         columns=["inputs", "output", "summary"],
         limit=100,
    )
    for call in calls:
         print(call.inputs, call.output)
    ``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L1445"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_feedback`

```python
get_feedback(
    query: 'Query | str | None' = None,
    reaction: 'str | None' = None,
    offset: 'int' = 0,
    limit: 'int' = 100
) → FeedbackQuery
```

Query project for feedback. 



**Examples:**
 ```python
     # Fetch a specific feedback object.
     # Note that this still returns a collection, which is expected
     # to contain zero or one item(s).
     client.get_feedback("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

     # Find all feedback objects with a specific reaction.
     client.get_feedback(reaction="👍", limit=10)
    ``` 



**Args:**
 
 - <b>`query`</b>:  A mongo-style query expression. For convenience, also accepts a feedback UUID string. 
 - <b>`reaction`</b>:  For convenience, filter by a particular reaction emoji. 
 - <b>`offset`</b>:  The offset to start fetching feedback objects from. 
 - <b>`limit`</b>:  The maximum number of feedback objects to fetch. 



**Returns:**
 A FeedbackQuery object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L1580"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `purge_costs`

```python
purge_costs(ids: 'list[str] | str') → None
```

Purge costs from the current project. 



**Examples:**
 

```python
     client.purge_costs([ids])
     client.purge_costs(ids)
    ``` 



**Args:**
 
 - <b>`ids`</b>:  The cost IDs to purge. Can be a single ID or a list of IDs. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L1605"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `query_costs`

```python
query_costs(
    query: 'Query | str | None' = None,
    llm_ids: 'list[str] | None' = None,
    offset: 'int' = 0,
    limit: 'int' = 100
) → list[CostQueryOutput]
```

Query project for costs. 



**Examples:**
 

```python
     # Fetch a specific cost object.
     # Note that this still returns a collection, which is expected
     # to contain zero or one item(s).
     client.query_costs("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

     # Find all cost objects with a specific reaction.
     client.query_costs(llm_ids=["gpt-4o-mini-2024-07-18"], limit=10)
    ``` 



**Args:**
 
 - <b>`query`</b>:  A mongo-style query expression. For convenience, also accepts a cost UUID string. 
 - <b>`llm_ids`</b>:  For convenience, filter for a set of llm_ids. 
 - <b>`offset`</b>:  The offset to start fetching cost objects from. 
 - <b>`limit`</b>:  The maximum number of cost objects to fetch. 



**Returns:**
 A CostQuery object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L918"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `save`

```python
save(val: 'Any', name: 'str', branch: 'str' = 'latest') → Any
```

Do not call directly, use weave.publish() instead. 



**Args:**
 
 - <b>`val`</b>:  The object to save. 
 - <b>`name`</b>:  The name to save the object under. 
 - <b>`branch`</b>:  The branch to save the object under. Defaults to "latest". 



**Returns:**
 A deserialized version of the saved object. 


---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L494"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Call`
A Call represents a single operation that was executed as part of a trace. 

<a href="https://github.com/wandb/weave/blob/master/../../../../../../develop/core/services/weave-python/weave-public/docs/weave/trace/weave_client/__init__"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    _op_name: 'str | Future[str]',
    trace_id: 'str',
    project_id: 'str',
    parent_id: 'str | None',
    inputs: 'dict',
    id: 'str | None' = None,
    output: 'Any' = None,
    exception: 'str | None' = None,
    summary: 'dict | None' = None,
    _display_name: 'str | Callable[[Call], str] | None' = None,
    attributes: 'dict | None' = None,
    started_at: 'datetime | None' = None,
    ended_at: 'datetime | None' = None,
    deleted_at: 'datetime | None' = None,
    _children: 'list[Call]' = &lt;factory&gt;,
    _feedback: 'RefFeedbackQuery | None' = None
) → None
```






---

#### <kbd>property</kbd> display_name





---

#### <kbd>property</kbd> feedback





---

#### <kbd>property</kbd> func_name

The decorated function's name that produced this call. 

This is different from `op_name` which is usually the ref of the op. 

---

#### <kbd>property</kbd> op_name





---

#### <kbd>property</kbd> ref





---

#### <kbd>property</kbd> ui_url







---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L647"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `apply_scorer`

```python
apply_scorer(
    scorer: 'Op | Scorer',
    additional_scorer_kwargs: 'dict | None' = None
) → ApplyScorerResult
```

`apply_scorer` is a method that applies a Scorer to a Call. This is useful for guarding application logic with a scorer and/or monitoring the quality of critical ops. Scorers are automatically logged to Weave as Feedback and can be used in queries & analysis. 



**Args:**
 
 - <b>`scorer`</b>:  The Scorer to apply. 
 - <b>`additional_scorer_kwargs`</b>:  Additional kwargs to pass to the scorer. This is  useful for passing in additional context that is not part of the call  inputs.useful for passing in additional context that is not part of the call  inputs. 



**Returns:**
 The result of the scorer application in the form of an `ApplyScorerResult`. 

```python
class ApplyScorerSuccess:

 - <b>`    result`</b>:  Any

 - <b>`    score_call`</b>:  Call
``` 

Example usage: 

```python
my_scorer = ... # construct a scorer
prediction, prediction_call = my_op.call(input_data)
result, score_call = prediction.apply_scorer(my_scorer)
``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L590"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `children`

```python
children(page_size: 'int' = 1000) → CallsIter
```

Get the children of the call. 



**Args:**
 
 - <b>`page_size`</b>:  Tune performance by changing the number of calls fetched at a time. 



**Returns:**
 An iterator of calls. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L614"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete`

```python
delete() → bool
```

Delete the call. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L644"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_display_name`

```python
remove_display_name() → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L620"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_display_name`

```python
set_display_name(name: 'str | None') → None
```

Set the display name for the call. 



**Args:**
 
 - <b>`name`</b>:  The display name to set for the call. 



**Example:**
 

```python
result, call = my_function.call("World")
call.set_display_name("My Custom Display Name")
``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L701"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `to_dict`

```python
to_dict() → CallDict
```






---

### <kbd>function</kbd> `PaginatedIterator`

```python
PaginatedIterator(*args, **kwargs)
```




