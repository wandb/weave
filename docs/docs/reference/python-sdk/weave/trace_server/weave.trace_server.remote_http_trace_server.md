---
sidebar_label: remote_http_trace_server
---
    

# weave.trace_server.remote_http_trace_server



---


# API Overview



## Classes

- [`remote_http_trace_server.RemoteHTTPTraceServer`](#class-remotehttptraceserver)
- [`remote_http_trace_server.ServerInfoRes`](#class-serverinfores)
- [`remote_http_trace_server.StartBatchItem`](#class-startbatchitem)
- [`remote_http_trace_server.EndBatchItem`](#class-endbatchitem)
- [`remote_http_trace_server.Batch`](#class-batch)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L92"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RemoteHTTPTraceServer`




<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L96"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    trace_server_url: str,
    should_batch: bool = False,
    remote_request_bytes_limit: int = 32505856
)
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L271"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_end`

```python
call_end(req: Union[CallEndReq, Dict[str, Any]]) → CallEndRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L284"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_read`

```python
call_read(req: Union[CallReadReq, Dict[str, Any]]) → CallReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L250"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start`

```python
call_start(req: Union[CallStartReq, Dict[str, Any]]) → CallStartRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L317"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_update`

```python
call_update(req: Union[CallUpdateReq, Dict[str, Any]]) → CallUpdateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L310"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: Union[CallsDeleteReq, Dict[str, Any]]) → CallsDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L291"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: Union[CallsQueryReq, Dict[str, Any]]) → CallsQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L303"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(
    req: Union[CallsQueryStatsReq, Dict[str, Any]]
) → CallsQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L298"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(req: CallsQueryReq) → Iterator[CallSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L111"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L488"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(
    req: Union[FeedbackCreateReq, Dict[str, Any]]
) → FeedbackCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L502"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: Union[FeedbackPurgeReq, Dict[str, Any]]) → FeedbackPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L495"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: Union[FeedbackQueryReq, Dict[str, Any]]) → FeedbackQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server/remote_http_trace_server/file_content_read#L465"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server/remote_http_trace_server/file_create#L445"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L116"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env(should_batch: bool = False) → RemoteHTTPTraceServer
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L343"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: Union[ObjCreateReq, Dict[str, Any]]) → ObjCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L350"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: Union[ObjReadReq, Dict[str, Any]]) → ObjReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L355"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: Union[ObjQueryReq, Dict[str, Any]]) → ObjQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L326"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_create`

```python
op_create(req: Union[OpCreateReq, Dict[str, Any]]) → OpCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L333"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_read`

```python
op_read(req: Union[OpReadReq, Dict[str, Any]]) → OpReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L336"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: Union[OpQueryReq, Dict[str, Any]]) → OpQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L438"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: Union[RefsReadBatchReq, Dict[str, Any]]) → RefsReadBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server/remote_http_trace_server/server_info#L234"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `server_info`

```python
server_info() → ServerInfoRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L120"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_auth`

```python
set_auth(auth: Tuple[str, str]) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L362"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_create`

```python
table_create(req: Union[TableCreateReq, Dict[str, Any]]) → TableCreateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table creation can be decomposed into a series of updates. This is useful when the table creation size is too big to be sent in a single request. We can create an empty table first, then update the table with the rows. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L431"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query`

```python
table_query(req: Union[TableQueryReq, Dict[str, Any]]) → TableQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L401"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table updates can be decomposed into a series of updates. 


---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L33"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ServerInfoRes`





**Pydantic Fields:**

- `min_required_weave_python_version`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L19"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StartBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallStartReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L24"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EndBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallEndReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/remote_http_trace_server.py#L29"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Batch`





**Pydantic Fields:**

- `batch`: `typing.List[typing.Union[StartBatchItem, EndBatchItem]]`
