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


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L71"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RemoteHTTPTraceServer`




<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L75"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    trace_server_url: str,
    should_batch: bool = False,
    remote_request_bytes_limit: int = 32505856
)
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L573"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `actions_execute_batch`

```python
actions_execute_batch(
    req: Union[ActionsExecuteBatchReq, dict[str, Any]]
) → ActionsExecuteBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L310"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_end`

```python
call_end(req: Union[CallEndReq, dict[str, Any]]) → CallEndRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L323"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_read`

```python
call_read(req: Union[CallReadReq, dict[str, Any]]) → CallReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L282"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start`

```python
call_start(req: Union[CallStartReq, dict[str, Any]]) → CallStartRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L305"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start_batch`

```python
call_start_batch(req: CallCreateBatchReq) → CallCreateBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L355"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_update`

```python
call_update(req: Union[CallUpdateReq, dict[str, Any]]) → CallUpdateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L348"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: Union[CallsDeleteReq, dict[str, Any]]) → CallsDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L328"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: Union[CallsQueryReq, dict[str, Any]]) → CallsQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L341"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(
    req: Union[CallsQueryStatsReq, dict[str, Any]]
) → CallsQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L334"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(
    req: Union[CallsQueryReq, dict[str, Any]]
) → Iterator[CallSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L605"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `completions_create`

```python
completions_create(req: CompletionsCreateReq) → CompletionsCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L615"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `completions_create_stream`

```python
completions_create_stream(req: CompletionsCreateReq) → Iterator[dict[str, Any]]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L591"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_create`

```python
cost_create(req: Union[CostCreateReq, dict[str, Any]]) → CostCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L598"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_purge`

```python
cost_purge(req: Union[CostPurgeReq, dict[str, Any]]) → CostPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L584"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_query`

```python
cost_query(req: Union[CostQueryReq, dict[str, Any]]) → CostQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L95"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → EnsureProjectExistsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L545"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(
    req: Union[FeedbackCreateReq, dict[str, Any]]
) → FeedbackCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L559"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: Union[FeedbackPurgeReq, dict[str, Any]]) → FeedbackPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L552"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: Union[FeedbackQueryReq, dict[str, Any]]) → FeedbackQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L566"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_replace`

```python
feedback_replace(
    req: Union[FeedbackReplaceReq, dict[str, Any]]
) → FeedbackReplaceRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/utils/retry.py#L525"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/utils/retry.py#L513"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L540"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `files_stats`

```python
files_stats(req: FilesStatsReq) → FilesStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L104"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env(should_batch: bool = False) → RemoteHTTPTraceServer
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L203"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `get_call_processor`

```python
get_call_processor() → Optional[AsyncBatchProcessor]
```

Custom method not defined on the formal TraceServerInterface to expose the underlying call processor. Should be formalized in a client-side interface. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L377"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: Union[ObjCreateReq, dict[str, Any]]) → ObjCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L394"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_delete`

```python
obj_delete(req: ObjDeleteReq) → ObjDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L384"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: Union[ObjReadReq, dict[str, Any]]) → ObjReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L387"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: Union[ObjQueryReq, dict[str, Any]]) → ObjQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L364"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_create`

```python
op_create(req: Union[OpCreateReq, dict[str, Any]]) → OpCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L369"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_read`

```python
op_read(req: Union[OpReadReq, dict[str, Any]]) → OpReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L372"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: Union[OpQueryReq, dict[str, Any]]) → OpQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L277"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `otel_export`

```python
otel_export(req: OtelExportReq) → OtelExportRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L623"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `project_stats`

```python
project_stats(req: ProjectStatsReq) → ProjectStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L506"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: Union[RefsReadBatchReq, dict[str, Any]]) → RefsReadBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/utils/retry.py#L268"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `server_info`

```python
server_info() → ServerInfoRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L110"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `set_auth`

```python
set_auth(auth: tuple[str, str]) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L399"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_create`

```python
table_create(req: Union[TableCreateReq, dict[str, Any]]) → TableCreateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table creation can be decomposed into a series of updates. This is useful when the table creation size is too big to be sent in a single request. We can create an empty table first, then update the table with the rows. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L475"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query`

```python
table_query(req: Union[TableQueryReq, dict[str, Any]]) → TableQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L489"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats`

```python
table_query_stats(
    req: Union[TableQueryStatsReq, dict[str, Any]]
) → TableQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L496"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats_batch`

```python
table_query_stats_batch(
    req: Union[TableQueryStatsReq, dict[str, Any]]
) → TableQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L482"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stream`

```python
table_query_stream(req: TableQueryReq) → Iterator[TableRowSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L440"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```

Similar to `calls/batch_upsert`, we can dynamically adjust the payload size due to the property that table updates can be decomposed into a series of updates. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L628"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `threads_query_stream`

```python
threads_query_stream(req: ThreadsQueryReq) → Iterator[ThreadSchema]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L39"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ServerInfoRes`





**Pydantic Fields:**

- `min_required_weave_python_version`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L25"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StartBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallStartReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L30"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EndBatchItem`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'weave.trace_server.trace_server_interface.CallEndReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server_bindings/remote_http_trace_server.py#L35"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Batch`





**Pydantic Fields:**

- `batch`: `list[typing.Union[StartBatchItem, EndBatchItem]]`
