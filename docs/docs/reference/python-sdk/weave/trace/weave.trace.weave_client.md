---
sidebar_label: weave_client
---
    

# weave.trace.weave_client



---


# API Overview



## Classes

- [`weave_client.WeaveClient`](#class-weaveclient)
- [`weave_client.Call`](#class-call): A Call represents a single operation that was executed as part of a trace.
- [`weave_client.CallsIter`](#class-callsiter)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L403"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `WeaveClient`




<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L417"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    entity: str,
    project: str,
    server: TraceServerInterface,
    ensure_project_exists: bool = True
)
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L824"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_cost`

```python
add_cost(
    llm_id: str,
    prompt_token_cost: float,
    completion_token_cost: float,
    effective_date: Optional[datetime] = datetime.datetime(2024, 9, 14, 0, 24, 20, 700322, tzinfo=datetime.timezone.utc),
    prompt_token_cost_unit: Optional[str] = 'USD',
    completion_token_cost_unit: Optional[str] = 'USD',
    provider_id: Optional[str] = 'default'
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
 - <b>`prompt_token_cost`</b>:  The cost of the prompt tokens. eg .0005 
 - <b>`completion_token_cost`</b>:  The cost of the completion tokens. eg .0015 
 - <b>`effective_date`</b>:  Defaults to the current date. A datetime.datetime object. 
 - <b>`provider_id`</b>:  The provider of the LLM. Defaults to "default". eg "openai" 
 - <b>`prompt_token_cost_unit`</b>:  The unit of the cost for the prompt tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time") 
 - <b>`completion_token_cost_unit`</b>:  The unit of the cost for the completion tokens. Defaults to "USD". (Currently unused, will be used in the future to specify the currency type for the cost eg "tokens" or "time") 



**Returns:**
 A CostCreateRes object. Which has one field called a list of tuples called ids. Each tuple contains the llm_id and the id of the created cost object. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L536"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call`

```python
call(call_id: str, include_costs: Optional[bool] = False) → WeaveObject
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L512"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls`

```python
calls(
    filter: Optional[CallsFilter] = None,
    include_costs: Optional[bool] = False
) → CallsIter
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L540"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `create_call`

```python
create_call(
    op: Union[str, Op],
    inputs: dict,
    parent: Optional[Call] = None,
    attributes: Optional[dict] = None,
    display_name: Optional[str, Callable[[Call], str]] = None,
    use_stack: bool = True
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L727"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete_call`

```python
delete_call(call: Call) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L722"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `fail_call`

```python
fail_call(call: Call, exception: BaseException) → None
```

Fail a call with an exception. This is a convenience method for finish_call. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L811"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback`

```python
feedback(
    query: Optional[Query, str] = None,
    reaction: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
) → FeedbackQuery
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L649"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `finish_call`

```python
finish_call(
    call: Call,
    output: Any = None,
    exception: Optional[BaseException] = None,
    postprocess_output: Optional[Callable[, Any]] = None
) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L450"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get`

```python
get(ref: ObjectRef) → Any
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L520"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_call`

```python
get_call(call_id: str, include_costs: Optional[bool] = False) → WeaveObject
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L499"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_calls`

```python
get_calls(
    filter: Optional[CallsFilter] = None,
    include_costs: Optional[bool] = False
) → CallsIter
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L736"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_feedback`

```python
get_feedback(
    query: Optional[Query, str] = None,
    reaction: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L871"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `purge_costs`

```python
purge_costs(ids: Union[list[str], str]) → None
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L896"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `query_costs`

```python
query_costs(
    query: Optional[Query, str] = None,
    llm_ids: Optional[list[str]] = None,
    offset: int = 0,
    limit: int = 100
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/trace_sentry.py#L443"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `save`

```python
save(val: Any, name: str, branch: str = 'latest') → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L145"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Call`
A Call represents a single operation that was executed as part of a trace. 

<a href="https://github.com/wandb/weave/blob/master/../../../../../../wandb/core/services/weave-python/weave-public/docs/weave/trace/weave_client/__init__"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    op_name: str,
    trace_id: str,
    project_id: str,
    parent_id: Optional[str],
    inputs: dict,
    id: Optional[str] = None,
    output: Any = None,
    exception: Optional[str] = None,
    summary: Optional[dict] = None,
    display_name: Optional[str, Callable[[ForwardRef('Call')], str]] = None,
    attributes: Optional[dict] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    deleted_at: Optional[datetime] = None,
    _children: list['Call'] = &lt;factory&gt;,
    _feedback: Optional[RefFeedbackQuery] = None
) → None
```






---

#### <kbd>property</kbd> feedback





---

#### <kbd>property</kbd> func_name

The decorated function's name that produced this call. 

This is different from `op_name` which is usually the ref of the op. 

---

#### <kbd>property</kbd> ui_url







---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L205"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `children`

```python
children() → CallsIter
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L215"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `delete`

```python
delete() → bool
```

Delete the call. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L244"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `remove_display_name`

```python
remove_display_name() → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L220"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_display_name`

```python
set_display_name(name: Optional[str]) → None
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

<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L248"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsIter`




<a href="https://github.com/wandb/weave/blob/master/weave/trace/weave_client.py#L253"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    server: TraceServerInterface,
    project_id: str,
    filter: CallsFilter,
    include_costs: bool = False
) → None
```








