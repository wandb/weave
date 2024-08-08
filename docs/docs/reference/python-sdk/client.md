

# API Overview

## Modules

- No modules

## Classes

- [`weave_client.WeaveClient`](./weave.weave_client.md#class-weaveclient)
- [`weave_client.Call`](./weave.weave_client.md#class-call): Call(op_name: str, trace_id: str, project_id: str, parent_id: Optional[str], inputs: dict, id: Optional[str] = None, output: Any = None, exception: Optional[str] = None, summary: Optional[dict] = None, display_name: Optional[str] = None, attributes: Optional[dict] = None, _children: list['Call'] = [], _feedback: Optional[weave.feedback.RefFeedbackQuery] = None)
- [`weave_client.CallsIter`](./weave.weave_client.md#class-callsiter)

## Functions

- No functions

---

---

## <kbd>class</kbd> `WeaveClient`




### <kbd>method</kbd> `WeaveClient.__init__`

```python
__init__(
    entity: str,
    project: str,
    server: weave.trace_server.trace_server_interface.TraceServerInterface,
    ensure_project_exists: bool = True
)
```








---

### <kbd>method</kbd> `WeaveClient.call`

```python
call(call_id: str) → WeaveObject
```





---

### <kbd>method</kbd> `WeaveClient.calls`

```python
calls(
    filter: Optional[weave.trace_server.trace_server_interface._CallsFilter] = None
) → CallsIter
```





---

### <kbd>method</kbd> `WeaveClient.create_call`

```python
create_call(
    op: Union[str, weave.trace.op.Op],
    inputs: dict,
    parent: Optional[weave.weave_client.Call] = None,
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

### <kbd>method</kbd> `WeaveClient.delete_call`

```python
delete_call(call: weave.weave_client.Call) → None
```





---

### <kbd>method</kbd> `WeaveClient.fail_call`

```python
fail_call(call: weave.weave_client.Call, exception: BaseException) → None
```

Fail a call with an exception. This is a convenience method for finish_call. 

---

### <kbd>method</kbd> `WeaveClient.feedback`

```python
feedback(
    query: Optional[weave.trace_server.interface.query.Query, str] = None,
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

### <kbd>method</kbd> `WeaveClient.finish_call`

```python
finish_call(
    call: weave.weave_client.Call,
    output: Any = None,
    exception: Optional[BaseException] = None
) → None
```





---

### <kbd>method</kbd> `WeaveClient.get`

```python
get(ref: weave.trace.refs.ObjectRef) → Any
```





---

### <kbd>method</kbd> `WeaveClient.save`

```python
save(val: Any, name: str, branch: str = 'latest') → Any
```






---

## <kbd>class</kbd> `Call`
Call(op_name: str, trace_id: str, project_id: str, parent_id: Optional[str], inputs: dict, id: Optional[str] = None, output: Any = None, exception: Optional[str] = None, summary: Optional[dict] = None, display_name: Optional[str] = None, attributes: Optional[dict] = None, _children: list['Call'] = [], _feedback: Optional[weave.feedback.RefFeedbackQuery] = None) 

### <kbd>method</kbd> `Call.__init__`

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
    _children: list['Call'] = [],
    _feedback: Optional[weave.feedback.RefFeedbackQuery] = None
) → None
```






---

#### <kbd>property</kbd> Call.feedback





---

#### <kbd>property</kbd> Call.ui_url







---

### <kbd>method</kbd> `Call.children`

```python
children() → CallsIter
```





---

### <kbd>method</kbd> `Call.delete`

```python
delete() → bool
```





---

### <kbd>method</kbd> `Call.remove_display_name`

```python
remove_display_name() → None
```





---

### <kbd>method</kbd> `Call.set_display_name`

```python
set_display_name(name: Optional[str]) → None
```






---

## <kbd>class</kbd> `CallsIter`




### <kbd>method</kbd> `CallsIter.__init__`

```python
__init__(
    server: weave.trace_server.trace_server_interface.TraceServerInterface,
    project_id: str,
    filter: weave.trace_server.trace_server_interface._CallsFilter
) → None
```








