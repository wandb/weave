---
sidebar_position: 0
sidebar_label: remote_http_trace_server
---
    

# weave.trace_server.remote_http_trace_server



---


# API Overview

## Modules

- No modules

## Classes

- [`remote_http_trace_server.RemoteHTTPTraceServer`](./weave.trace_server.remote_http_trace_server.md#class-remotehttptraceserver)
- [`remote_http_trace_server.ServerInfoRes`](./weave.trace_server.remote_http_trace_server.md#class-serverinfores)
- [`remote_http_trace_server.StartBatchItem`](./weave.trace_server.remote_http_trace_server.md#class-startbatchitem)
- [`remote_http_trace_server.EndBatchItem`](./weave.trace_server.remote_http_trace_server.md#class-endbatchitem)
- [`remote_http_trace_server.Batch`](./weave.trace_server.remote_http_trace_server.md#class-batch)

## Functions

- No functions


---


## <kbd>class</kbd> `RemoteHTTPTraceServer`




### <kbd>method</kbd> `__init__`

```python
__init__(
    trace_server_url: str,
    should_batch: bool = False,
    remote_request_bytes_limit: int = 32505856
)
```








---

### <kbd>method</kbd> `call_end`

```python
call_end(req: Union[CallEndReq, Dict[str, Any]]) → CallEndRes
```





---

### <kbd>method</kbd> `call_read`

```python
call_read(req: Union[CallReadReq, Dict[str, Any]]) → CallReadRes
```





---

### <kbd>method</kbd> `call_start`

```python
call_start(req: Union[CallStartReq, Dict[str, Any]]) → CallStartRes
```





---

### <kbd>method</kbd> `call_update`

```python
call_update(req: Union[CallUpdateReq, Dict[str, Any]]) → CallUpdateRes
```





---

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: Union[CallsDeleteReq, Dict[str, Any]]) → CallsDeleteRes
```





---

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: Union[CallsQueryReq, Dict[str, Any]]) → CallsQueryRes
```





---

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(
    req: Union[CallsQueryStatsReq, Dict[str, Any]]
) → CallsQueryStatsRes
```





---

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(req: CallsQueryReq) → Iterator[CallSchema]
```





---

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → None
```





---

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(
    req: Union[FeedbackCreateReq, Dict[str, Any]]
) → FeedbackCreateRes
```





---

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: Union[FeedbackPurgeReq, Dict[str, Any]]) → FeedbackPurgeRes
```





---

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: Union[FeedbackQueryReq, Dict[str, Any]]) → FeedbackQueryRes
```





---

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

### <kbd>classmethod</kbd> `from_env`

```python
from_env(should_batch: bool = False) → RemoteHTTPTraceServer
```





---

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: Union[ObjCreateReq, Dict[str, Any]]) → ObjCreateRes
```





---

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: Union[ObjReadReq, Dict[str, Any]]) → ObjReadRes
```





---

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: Union[ObjQueryReq, Dict[str, Any]]) → ObjQueryRes
```





---

### <kbd>method</kbd> `op_create`

```python
op_create(req: Union[OpCreateReq, Dict[str, Any]]) → OpCreateRes
```





---

### <kbd>method</kbd> `op_read`

```python
op_read(req: Union[OpReadReq, Dict[str, Any]]) → OpReadRes
```





---

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: Union[OpQueryReq, Dict[str, Any]]) → OpQueryRes
```





---

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: Union[RefsReadBatchReq, Dict[str, Any]]) → RefsReadBatchRes
```





---

### <kbd>method</kbd> `server_info`

```python
server_info() → ServerInfoRes
```





---

### <kbd>method</kbd> `set_auth`

```python
set_auth(auth: Tuple[str, str]) → None
```





---

### <kbd>method</kbd> `table_create`

```python
table_create(req: Union[TableCreateReq, Dict[str, Any]]) → TableCreateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table creation can be decomposed into a series of updates. This is useful when the table creation size is too big to be sent in a single request. We can create an empty table first, then update the table with the rows. 

---

### <kbd>method</kbd> `table_query`

```python
table_query(req: Union[TableQueryReq, Dict[str, Any]]) → TableQueryRes
```





---

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table updates can be decomposed into a series of updates. 


---
## <kbd>class</kbd> `ServerInfoRes`
            
```python
class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str

```
            
---
## <kbd>class</kbd> `StartBatchItem`
            
```python
class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq

```
            
---
## <kbd>class</kbd> `EndBatchItem`
            
```python
class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq

```
            
---
## <kbd>class</kbd> `Batch`
            
```python
class Batch(BaseModel):
    batch: t.List[t.Union[StartBatchItem, EndBatchItem]]

```
            