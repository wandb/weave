---
sidebar_label: remote_http_trace_server
---
    

# weave.trace_server_bindings.remote_http_trace_server



---


# API Overview



## Classes

- [`remote_http_trace_server.RemoteHTTPTraceServer`](#class-remotehttptraceserver)
- [`remote_http_trace_server.ServerInfoRes`](#class-serverinfores)
- [`remote_http_trace_server.StartBatchItem`](#class-startbatchitem)
- [`remote_http_trace_server.EndBatchItem`](#class-endbatchitem)
- [`remote_http_trace_server.Batch`](#class-batch)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L91"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RemoteHTTPTraceServer`




<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L95"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    trace_server_url: str,
    should_batch: bool = False,
    remote_request_bytes_limit: int = 32505856
)
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L278"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_end`

```python
call_end(req: Union[CallEndReq, dict[str, Any]]) → CallEndRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L289"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_read`

```python
call_read(req: Union[CallReadReq, dict[str, Any]]) → CallReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L257"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start`

```python
call_start(req: Union[CallStartReq, dict[str, Any]]) → CallStartRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L320"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_update`

```python
call_update(req: Union[CallUpdateReq, dict[str, Any]]) → CallUpdateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L313"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: Union[CallsDeleteReq, dict[str, Any]]) → CallsDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L294"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: Union[CallsQueryReq, dict[str, Any]]) → CallsQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L306"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(
    req: Union[CallsQueryStatsReq, dict[str, Any]]
) → CallsQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L301"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(req: CallsQueryReq) → Iterator[CallSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L528"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_create`

```python
cost_create(req: Union[CostCreateReq, dict[str, Any]]) → CostCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L535"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_purge`

```python
cost_purge(req: Union[CostPurgeReq, dict[str, Any]]) → CostPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L521"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_query`

```python
cost_query(req: Union[CostQueryReq, dict[str, Any]]) → CostQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L110"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → EnsureProjectExistsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L499"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(
    req: Union[FeedbackCreateReq, dict[str, Any]]
) → FeedbackCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L513"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: Union[FeedbackPurgeReq, dict[str, Any]]) → FeedbackPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L506"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: Union[FeedbackQueryReq, dict[str, Any]]) → FeedbackQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server_bindings/remote_http_trace_server/file_content_read#L476"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server_bindings/remote_http_trace_server/file_create#L456"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L119"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env(should_batch: bool = False) → RemoteHTTPTraceServer
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L342"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: Union[ObjCreateReq, dict[str, Any]]) → ObjCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L349"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: Union[ObjReadReq, dict[str, Any]]) → ObjReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L352"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: Union[ObjQueryReq, dict[str, Any]]) → ObjQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L329"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_create`

```python
op_create(req: Union[OpCreateReq, dict[str, Any]]) → OpCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L334"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_read`

```python
op_read(req: Union[OpReadReq, dict[str, Any]]) → OpReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L337"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: Union[OpQueryReq, dict[str, Any]]) → OpQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L449"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: Union[RefsReadBatchReq, dict[str, Any]]) → RefsReadBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/docs/weave/trace_server_bindings/remote_http_trace_server/server_info#L241"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `server_info`

```python
server_info() → ServerInfoRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L123"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_auth`

```python
set_auth(auth: Tuple[str, str]) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L359"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_create`

```python
table_create(req: Union[TableCreateReq, dict[str, Any]]) → TableCreateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table creation can be decomposed into a series of updates. This is useful when the table creation size is too big to be sent in a single request. We can create an empty table first, then update the table with the rows. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L435"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query`

```python
table_query(req: Union[TableQueryReq, dict[str, Any]]) → TableQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L442"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats`

```python
table_query_stats(
    req: Union[TableQueryStatsReq, dict[str, Any]]
) → TableQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L400"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table updates can be decomposed into a series of updates. 


---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L32"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ServerInfoRes`





**Pydantic Fields:**

- `min_required_weave_python_version`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L18"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StartBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallStartReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L23"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EndBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallEndReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L28"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Batch`





**Pydantic Fields:**

- `batch`: `list[typing.Union[StartBatchItem, EndBatchItem]]`
