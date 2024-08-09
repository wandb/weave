---
sidebar_label: weave_client
---
    

# weave.weave_client



---


# API Overview



## Classes

- [`weave_client.WeaveClient`](#class-weaveclient)
- [`weave_client.Call`](#class-call): Call(op_name: str, trace_id: str, project_id: str, parent_id: Optional[str], inputs: dict, id: Optional[str] = None, output: Any = None, exception: Optional[str] = None, summary: Optional[dict] = None, display_name: Optional[str] = None, attributes: Optional[dict] = None, _children: list['Call'] = &lt;factory&gt;, _feedback: Optional[weave.feedback.RefFeedbackQuery] = None)
- [`weave_client.CallsIter`](#class-callsiter)




---


## <kbd>class</kbd> `WeaveClient`




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

### <kbd>method</kbd> `call`

```python
call(call_id: str) → WeaveObject
```





---

### <kbd>method</kbd> `calls`

```python
calls(filter: Optional[_CallsFilter] = None) → CallsIter
```





---

### <kbd>method</kbd> `create_call`

```python
create_call(
    op: Union[str, Op],
    inputs: dict,
    parent: Optional[Call] = None,
    attributes: Optional[dict] = None,
    display_name: Optional[str] = None,
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

### <kbd>method</kbd> `delete_call`

```python
delete_call(call: Call) → None
```





---

### <kbd>method</kbd> `fail_call`

```python
fail_call(call: Call, exception: BaseException) → None
```

Fail a call with an exception. This is a convenience method for finish_call. 

---

### <kbd>method</kbd> `feedback`

```python
feedback(
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
     client.feedback("1B4082A3-4EDA-4BEB-BFEB-2D16ED59AA07")

     # Find all feedback objects with a specific reaction.
     client.feedback(reaction="👍", limit=10)
    ``` 



**Args:**
 
 - <b>`query`</b>:  A mongo-style query expression. For convenience, also accepts a feedback UUID string. 
 - <b>`reaction`</b>:  For convenience, filter by a particular reaction emoji. 
 - <b>`offset`</b>:  The offset to start fetching feedback objects from. 
 - <b>`limit`</b>:  The maximum number of feedback objects to fetch. 



**Returns:**
 A FeedbackQuery object. 

---

### <kbd>method</kbd> `finish_call`

```python
finish_call(
    call: Call,
    output: Any = None,
    exception: Optional[BaseException] = None
) → None
```





---

### <kbd>method</kbd> `get`

```python
get(ref: ObjectRef) → Any
```





---

### <kbd>method</kbd> `save`

```python
save(val: Any, name: str, branch: str = 'latest') → Any
```






---

## <kbd>class</kbd> `Call`
Call(op_name: str, trace_id: str, project_id: str, parent_id: Optional[str], inputs: dict, id: Optional[str] = None, output: Any = None, exception: Optional[str] = None, summary: Optional[dict] = None, display_name: Optional[str] = None, attributes: Optional[dict] = None, _children: list['Call'] = &lt;factory&gt;, _feedback: Optional[weave.feedback.RefFeedbackQuery] = None) 

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
    display_name: Optional[str] = None,
    attributes: Optional[dict] = None,
    _children: list['Call'] = &lt;factory&gt;,
    _feedback: Optional[RefFeedbackQuery] = None
) → None
```






---

#### <kbd>property</kbd> feedback





---

#### <kbd>property</kbd> ui_url







---

### <kbd>method</kbd> `children`

```python
children() → CallsIter
```





---

### <kbd>method</kbd> `delete`

```python
delete() → bool
```





---

### <kbd>method</kbd> `remove_display_name`

```python
remove_display_name() → None
```





---

### <kbd>method</kbd> `set_display_name`

```python
set_display_name(name: Optional[str]) → None
```






---

## <kbd>class</kbd> `CallsIter`




### <kbd>method</kbd> `__init__`

```python
__init__(
    server: TraceServerInterface,
    project_id: str,
    filter: _CallsFilter
) → None
```








