

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

---

## <kbd>class</kbd> `RemoteHTTPTraceServer`




### <kbd>method</kbd> `RemoteHTTPTraceServer.__init__`

```python
__init__(
    trace_server_url: str,
    should_batch: bool = False,
    remote_request_bytes_limit: int = 32505856
)
```








---

### <kbd>method</kbd> `RemoteHTTPTraceServer.call_end`

```python
call_end(
    req: Union[weave.trace_server.trace_server_interface.CallEndReq, Dict[str, Any]]
) → CallEndRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.call_read`

```python
call_read(
    req: Union[weave.trace_server.trace_server_interface.CallReadReq, Dict[str, Any]]
) → CallReadRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.call_start`

```python
call_start(
    req: Union[weave.trace_server.trace_server_interface.CallStartReq, Dict[str, Any]]
) → CallStartRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.call_update`

```python
call_update(
    req: Union[weave.trace_server.trace_server_interface.CallUpdateReq, Dict[str, Any]]
) → CallUpdateRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.calls_delete`

```python
calls_delete(
    req: Union[weave.trace_server.trace_server_interface.CallsDeleteReq, Dict[str, Any]]
) → CallsDeleteRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.calls_query`

```python
calls_query(
    req: Union[weave.trace_server.trace_server_interface.CallsQueryReq, Dict[str, Any]]
) → CallsQueryRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.calls_query_stats`

```python
calls_query_stats(
    req: Union[weave.trace_server.trace_server_interface.CallsQueryStatsReq, Dict[str, Any]]
) → CallsQueryStatsRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.calls_query_stream`

```python
calls_query_stream(
    req: weave.trace_server.trace_server_interface.CallsQueryReq
) → Iterator[weave.trace_server.trace_server_interface.CallSchema]
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → None
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.feedback_create`

```python
feedback_create(
    req: Union[weave.trace_server.trace_server_interface.FeedbackCreateReq, Dict[str, Any]]
) → FeedbackCreateRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.feedback_purge`

```python
feedback_purge(
    req: Union[weave.trace_server.trace_server_interface.FeedbackPurgeReq, Dict[str, Any]]
) → FeedbackPurgeRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.feedback_query`

```python
feedback_query(
    req: Union[weave.trace_server.trace_server_interface.FeedbackQueryReq, Dict[str, Any]]
) → FeedbackQueryRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.file_content_read`

```python
file_content_read(
    req: weave.trace_server.trace_server_interface.FileContentReadReq
) → FileContentReadRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.file_create`

```python
file_create(
    req: weave.trace_server.trace_server_interface.FileCreateReq
) → FileCreateRes
```





---

### <kbd>classmethod</kbd> `RemoteHTTPTraceServer.from_env`

```python
from_env(should_batch: bool = False) → RemoteHTTPTraceServer
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.obj_create`

```python
obj_create(
    req: Union[weave.trace_server.trace_server_interface.ObjCreateReq, Dict[str, Any]]
) → ObjCreateRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.obj_read`

```python
obj_read(
    req: Union[weave.trace_server.trace_server_interface.ObjReadReq, Dict[str, Any]]
) → ObjReadRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.objs_query`

```python
objs_query(
    req: Union[weave.trace_server.trace_server_interface.ObjQueryReq, Dict[str, Any]]
) → ObjQueryRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.op_create`

```python
op_create(
    req: Union[weave.trace_server.trace_server_interface.OpCreateReq, Dict[str, Any]]
) → OpCreateRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.op_read`

```python
op_read(
    req: Union[weave.trace_server.trace_server_interface.OpReadReq, Dict[str, Any]]
) → OpReadRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.ops_query`

```python
ops_query(
    req: Union[weave.trace_server.trace_server_interface.OpQueryReq, Dict[str, Any]]
) → OpQueryRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.refs_read_batch`

```python
refs_read_batch(
    req: Union[weave.trace_server.trace_server_interface.RefsReadBatchReq, Dict[str, Any]]
) → RefsReadBatchRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.server_info`

```python
server_info() → ServerInfoRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.set_auth`

```python
set_auth(auth: Tuple[str, str]) → None
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.table_create`

```python
table_create(
    req: Union[weave.trace_server.trace_server_interface.TableCreateReq, Dict[str, Any]]
) → TableCreateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table creation can be decomposed into a series of updates. This is useful when the table creation size is too big to be sent in a single request. We can create an empty table first, then update the table with the rows. 

---

### <kbd>method</kbd> `RemoteHTTPTraceServer.table_query`

```python
table_query(
    req: Union[weave.trace_server.trace_server_interface.TableQueryReq, Dict[str, Any]]
) → TableQueryRes
```





---

### <kbd>method</kbd> `RemoteHTTPTraceServer.table_update`

```python
table_update(
    req: weave.trace_server.trace_server_interface.TableUpdateReq
) → TableUpdateRes
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
            