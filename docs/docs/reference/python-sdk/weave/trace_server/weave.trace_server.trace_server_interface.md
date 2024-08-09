---
sidebar_label: trace_server_interface
---
    

# weave.trace_server.trace_server_interface



---


# API Overview



## Classes

- [`trace_server_interface.CallEndReq`](#class-callendreq)
- [`trace_server_interface.CallEndRes`](#class-callendres)
- [`trace_server_interface.CallReadReq`](#class-callreadreq)
- [`trace_server_interface.CallReadRes`](#class-callreadres)
- [`trace_server_interface.CallSchema`](#class-callschema)
- [`trace_server_interface.CallStartReq`](#class-callstartreq)
- [`trace_server_interface.CallStartRes`](#class-callstartres)
- [`trace_server_interface.CallUpdateReq`](#class-callupdatereq)
- [`trace_server_interface.CallUpdateReq`](#class-callupdatereq)
- [`trace_server_interface.CallUpdateRes`](#class-callupdateres)
- [`trace_server_interface.CallsDeleteReq`](#class-callsdeletereq)
- [`trace_server_interface.CallsDeleteReq`](#class-callsdeletereq)
- [`trace_server_interface.CallsDeleteRes`](#class-callsdeleteres)
- [`trace_server_interface.CallsQueryReq`](#class-callsqueryreq)
- [`trace_server_interface.CallsQueryRes`](#class-callsqueryres)
- [`trace_server_interface.CallsQueryStatsReq`](#class-callsquerystatsreq)
- [`trace_server_interface.CallsQueryStatsRes`](#class-callsquerystatsres)
- [`trace_server_interface.EndedCallSchemaForInsert`](#class-endedcallschemaforinsert)
- [`trace_server_interface.Feedback`](#class-feedback)
- [`trace_server_interface.FeedbackCreateReq`](#class-feedbackcreatereq)
- [`trace_server_interface.FeedbackCreateReq`](#class-feedbackcreatereq)
- [`trace_server_interface.FeedbackCreateRes`](#class-feedbackcreateres)
- [`trace_server_interface.FeedbackPayloadNoteReq`](#class-feedbackpayloadnotereq)
- [`trace_server_interface.FeedbackPayloadReactionReq`](#class-feedbackpayloadreactionreq)
- [`trace_server_interface.FeedbackPurgeReq`](#class-feedbackpurgereq)
- [`trace_server_interface.FeedbackPurgeRes`](#class-feedbackpurgeres)
- [`trace_server_interface.FeedbackQueryReq`](#class-feedbackqueryreq)
- [`trace_server_interface.FeedbackQueryRes`](#class-feedbackqueryres)
- [`trace_server_interface.FileContentReadReq`](#class-filecontentreadreq)
- [`trace_server_interface.FileContentReadRes`](#class-filecontentreadres)
- [`trace_server_interface.FileCreateReq`](#class-filecreatereq)
- [`trace_server_interface.FileCreateRes`](#class-filecreateres)
- [`trace_server_interface.ObjCreateReq`](#class-objcreatereq)
- [`trace_server_interface.ObjCreateRes`](#class-objcreateres)
- [`trace_server_interface.ObjQueryReq`](#class-objqueryreq)
- [`trace_server_interface.ObjQueryRes`](#class-objqueryres)
- [`trace_server_interface.ObjReadReq`](#class-objreadreq)
- [`trace_server_interface.ObjReadRes`](#class-objreadres)
- [`trace_server_interface.ObjSchema`](#class-objschema)
- [`trace_server_interface.ObjSchemaForInsert`](#class-objschemaforinsert)
- [`trace_server_interface.OpCreateReq`](#class-opcreatereq)
- [`trace_server_interface.OpCreateRes`](#class-opcreateres)
- [`trace_server_interface.OpQueryReq`](#class-opqueryreq)
- [`trace_server_interface.OpQueryRes`](#class-opqueryres)
- [`trace_server_interface.OpReadReq`](#class-opreadreq)
- [`trace_server_interface.OpReadRes`](#class-opreadres)
- [`trace_server_interface.RefsReadBatchReq`](#class-refsreadbatchreq)
- [`trace_server_interface.RefsReadBatchRes`](#class-refsreadbatchres)
- [`trace_server_interface.StartedCallSchemaForInsert`](#class-startedcallschemaforinsert)
- [`trace_server_interface.TableAppendSpec`](#class-tableappendspec)
- [`trace_server_interface.TableAppendSpecPayload`](#class-tableappendspecpayload)
- [`trace_server_interface.TableCreateReq`](#class-tablecreatereq)
- [`trace_server_interface.TableCreateRes`](#class-tablecreateres)
- [`trace_server_interface.TableInsertSpec`](#class-tableinsertspec)
- [`trace_server_interface.TableInsertSpecPayload`](#class-tableinsertspecpayload)
- [`trace_server_interface.TablePopSpec`](#class-tablepopspec)
- [`trace_server_interface.TablePopSpecPayload`](#class-tablepopspecpayload)
- [`trace_server_interface.TableQueryReq`](#class-tablequeryreq)
- [`trace_server_interface.TableQueryRes`](#class-tablequeryres)
- [`trace_server_interface.TableRowSchema`](#class-tablerowschema)
- [`trace_server_interface.TableSchemaForInsert`](#class-tableschemaforinsert)
- [`trace_server_interface.TableUpdateReq`](#class-tableupdatereq)
- [`trace_server_interface.TableUpdateRes`](#class-tableupdateres)
- [`trace_server_interface.TraceServerInterface`](#class-traceserverinterface)




---

## <kbd>class</kbd> `CallEndReq`
            
```python
class CallEndReq(BaseModel):
    end: EndedCallSchemaForInsert

```
            
---
## <kbd>class</kbd> `CallEndRes`
            
```python
class CallEndRes(BaseModel):
    pass

```
            
---
## <kbd>class</kbd> `CallReadReq`
            
```python
class CallReadReq(BaseModel):
    project_id: str
    id: str

```
            
---
## <kbd>class</kbd> `CallReadRes`
            
```python
class CallReadRes(BaseModel):
    call: typing.Optional[CallSchema]

```
            
---
## <kbd>class</kbd> `CallSchema`
            
```python
class CallSchema(BaseModel):
    id: str
    project_id: str

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: typing.Optional[str] = None

    ## Trace ID
    trace_id: str
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    started_at: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    ## End time is required if finished
    ended_at: typing.Optional[datetime.datetime] = None

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    output: typing.Optional[typing.Any] = None

    ## Summary: a summary of the call
    summary: typing.Optional[typing.Dict[str, typing.Any]] = None

    # WB Metadata
    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None

    deleted_at: typing.Optional[datetime.datetime] = None

```
            
---
## <kbd>class</kbd> `CallStartReq`
            
```python
class CallStartReq(BaseModel):
    start: StartedCallSchemaForInsert

```
            
---
## <kbd>class</kbd> `CallStartRes`
            
```python
class CallStartRes(BaseModel):
    id: str
    trace_id: str

```
            
---
## <kbd>class</kbd> `CallUpdateReq`
            
```python
class CallUpdateReq(BaseModel):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: typing.Optional[str] = None

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `CallUpdateReq`
            
```python
class CallUpdateReq(BaseModel):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: typing.Optional[str] = None

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `CallUpdateRes`
            
```python
class CallUpdateRes(BaseModel):
    pass

```
            
---
## <kbd>class</kbd> `CallsDeleteReq`
            
```python
class CallsDeleteReq(BaseModel):
    project_id: str
    call_ids: typing.List[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `CallsDeleteReq`
            
```python
class CallsDeleteReq(BaseModel):
    project_id: str
    call_ids: typing.List[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `CallsDeleteRes`
            
```python
class CallsDeleteRes(BaseModel):
    pass

```
            
---
## <kbd>class</kbd> `CallsQueryReq`
            
```python
class CallsQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[CallsFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None
    # Sort by multiple fields
    sort_by: typing.Optional[typing.List[SortBy]] = None
    query: typing.Optional[Query] = None

    # TODO: type this with call schema columns, following the same rules as
    # SortBy and thus GetFieldOperator.get_field_ (without direction)
    columns: typing.Optional[typing.List[str]] = None

```
            
---
## <kbd>class</kbd> `CallsQueryRes`
            
```python
class CallsQueryRes(BaseModel):
    calls: typing.List[CallSchema]

```
            
---
## <kbd>class</kbd> `CallsQueryStatsReq`
            
```python
class CallsQueryStatsReq(BaseModel):
    project_id: str
    filter: typing.Optional[CallsFilter] = None
    query: typing.Optional[Query] = None

```
            
---
## <kbd>class</kbd> `CallsQueryStatsRes`
            
```python
class CallsQueryStatsRes(BaseModel):
    count: int

```
            
---
## <kbd>class</kbd> `EndedCallSchemaForInsert`
            
```python
class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str

    ## End time is required
    ended_at: datetime.datetime

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    output: typing.Optional[typing.Any] = None

    ## Summary: a summary of the call
    summary: typing.Dict[str, typing.Any]

```
            
---

## <kbd>class</kbd> `Feedback`





---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 




---
## <kbd>class</kbd> `FeedbackCreateReq`
            
```python
class FeedbackCreateReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: typing.Optional[str] = Field(default=None, examples=["Jane Smith"])
    feedback_type: str = Field(examples=["custom"])
    payload: typing.Dict[str, typing.Any] = Field(
        examples=[
            {
                "key": "value",
            }
        ]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `FeedbackCreateReq`
            
```python
class FeedbackCreateReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: typing.Optional[str] = Field(default=None, examples=["Jane Smith"])
    feedback_type: str = Field(examples=["custom"])
    payload: typing.Dict[str, typing.Any] = Field(
        examples=[
            {
                "key": "value",
            }
        ]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

```
            
---
## <kbd>class</kbd> `FeedbackCreateRes`
            
```python
class FeedbackCreateRes(BaseModel):
    id: str
    created_at: datetime.datetime
    wb_user_id: str
    payload: typing.Dict[str, typing.Any]  # If not empty, replace payload

```
            
---
## <kbd>class</kbd> `FeedbackPayloadNoteReq`
            
```python
class FeedbackPayloadNoteReq(BaseModel):
    note: str = Field(min_length=1, max_length=1024)

```
            
---
## <kbd>class</kbd> `FeedbackPayloadReactionReq`
            
```python
class FeedbackPayloadReactionReq(BaseModel):
    emoji: str

```
            
---
## <kbd>class</kbd> `FeedbackPurgeReq`
            
```python
class FeedbackPurgeReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    query: Query

```
            
---
## <kbd>class</kbd> `FeedbackPurgeRes`
            
```python
class FeedbackPurgeRes(BaseModel):
    pass

```
            
---
## <kbd>class</kbd> `FeedbackQueryReq`
            
```python
class FeedbackQueryReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    fields: typing.Optional[list[str]] = Field(
        default=None, examples=[["id", "feedback_type", "payload.note"]]
    )
    query: typing.Optional[Query] = None
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    # TODO: I think SortBy shouldn't have leading underscore
    sort_by: typing.Optional[typing.List[SortBy]] = None
    limit: typing.Optional[int] = Field(default=None, examples=[10])
    offset: typing.Optional[int] = Field(default=None, examples=[0])

```
            
---
## <kbd>class</kbd> `FeedbackQueryRes`
            
```python
class FeedbackQueryRes(BaseModel):
    # Note: this is not a list of Feedback because user can request any fields.
    result: list[dict[str, typing.Any]]

```
            
---
## <kbd>class</kbd> `FileContentReadReq`
            
```python
class FileContentReadReq(BaseModel):
    project_id: str
    digest: str

```
            
---
## <kbd>class</kbd> `FileContentReadRes`
            
```python
class FileContentReadRes(BaseModel):
    content: bytes

```
            
---
## <kbd>class</kbd> `FileCreateReq`
            
```python
class FileCreateReq(BaseModel):
    project_id: str
    name: str
    content: bytes

```
            
---
## <kbd>class</kbd> `FileCreateRes`
            
```python
class FileCreateRes(BaseModel):
    digest: str

```
            
---
## <kbd>class</kbd> `ObjCreateReq`
            
```python
class ObjCreateReq(BaseModel):
    obj: ObjSchemaForInsert

```
            
---
## <kbd>class</kbd> `ObjCreateRes`
            
```python
class ObjCreateRes(BaseModel):
    digest: str  #

```
            
---
## <kbd>class</kbd> `ObjQueryReq`
            
```python
class ObjQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[ObjectVersionFilter] = None

```
            
---
## <kbd>class</kbd> `ObjQueryRes`
            
```python
class ObjQueryRes(BaseModel):
    objs: typing.List[ObjSchema]

```
            
---
## <kbd>class</kbd> `ObjReadReq`
            
```python
class ObjReadReq(BaseModel):
    project_id: str
    object_id: str
    digest: str

```
            
---
## <kbd>class</kbd> `ObjReadRes`
            
```python
class ObjReadRes(BaseModel):
    obj: ObjSchema

```
            
---
## <kbd>class</kbd> `ObjSchema`
            
```python
class ObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    deleted_at: typing.Optional[datetime.datetime] = None
    digest: str
    version_index: int
    is_latest: int
    kind: str
    base_object_class: typing.Optional[str]
    val: typing.Any

```
            
---
## <kbd>class</kbd> `ObjSchemaForInsert`
            
```python
class ObjSchemaForInsert(BaseModel):
    project_id: str
    object_id: str
    val: typing.Any

```
            
---
## <kbd>class</kbd> `OpCreateReq`
            
```python
class OpCreateReq(BaseModel):
    op_obj: ObjSchemaForInsert

```
            
---
## <kbd>class</kbd> `OpCreateRes`
            
```python
class OpCreateRes(BaseModel):
    digest: str

```
            
---
## <kbd>class</kbd> `OpQueryReq`
            
```python
class OpQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[OpVersionFilter] = None

```
            
---
## <kbd>class</kbd> `OpQueryRes`
            
```python
class OpQueryRes(BaseModel):
    op_objs: typing.List[ObjSchema]

```
            
---
## <kbd>class</kbd> `OpReadReq`
            
```python
class OpReadReq(BaseModel):
    project_id: str
    name: str
    digest: str

```
            
---
## <kbd>class</kbd> `OpReadRes`
            
```python
class OpReadRes(BaseModel):
    op_obj: ObjSchema

```
            
---
## <kbd>class</kbd> `RefsReadBatchReq`
            
```python
class RefsReadBatchReq(BaseModel):
    refs: typing.List[str]

```
            
---
## <kbd>class</kbd> `RefsReadBatchRes`
            
```python
class RefsReadBatchRes(BaseModel):
    vals: typing.List[typing.Any]

```
            
---
## <kbd>class</kbd> `StartedCallSchemaForInsert`
            
```python
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: typing.Optional[str] = None  # Will be generated if not provided

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: typing.Optional[str] = None

    ## Trace ID
    trace_id: typing.Optional[str] = None  # Will be generated if not provided
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    started_at: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    # WB Metadata
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    wb_run_id: typing.Optional[str] = None

```
            
---
## <kbd>class</kbd> `TableAppendSpec`
            
```python
class TableAppendSpec(BaseModel):
    append: TableAppendSpecPayload

```
            
---
## <kbd>class</kbd> `TableAppendSpecPayload`
            
```python
class TableAppendSpecPayload(BaseModel):
    row: dict[str, typing.Any]

```
            
---
## <kbd>class</kbd> `TableCreateReq`
            
```python
class TableCreateReq(BaseModel):
    table: TableSchemaForInsert

```
            
---
## <kbd>class</kbd> `TableCreateRes`
            
```python
class TableCreateRes(BaseModel):
    digest: str

```
            
---
## <kbd>class</kbd> `TableInsertSpec`
            
```python
class TableInsertSpec(BaseModel):
    insert: TableInsertSpecPayload

```
            
---
## <kbd>class</kbd> `TableInsertSpecPayload`
            
```python
class TableInsertSpecPayload(BaseModel):
    index: int
    row: dict[str, typing.Any]

```
            
---
## <kbd>class</kbd> `TablePopSpec`
            
```python
class TablePopSpec(BaseModel):
    pop: TablePopSpecPayload

```
            
---
## <kbd>class</kbd> `TablePopSpecPayload`
            
```python
class TablePopSpecPayload(BaseModel):
    index: int

```
            
---
## <kbd>class</kbd> `TableQueryReq`
            
```python
class TableQueryReq(BaseModel):
    project_id: str
    digest: str
    filter: typing.Optional[TableRowFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None

```
            
---
## <kbd>class</kbd> `TableQueryRes`
            
```python
class TableQueryRes(BaseModel):
    rows: typing.List[TableRowSchema]

```
            
---
## <kbd>class</kbd> `TableRowSchema`
            
```python
class TableRowSchema(BaseModel):
    digest: str
    val: typing.Any

```
            
---
## <kbd>class</kbd> `TableSchemaForInsert`
            
```python
class TableSchemaForInsert(BaseModel):
    project_id: str
    rows: list[dict[str, typing.Any]]

```
            
---
## <kbd>class</kbd> `TableUpdateReq`
            
```python
class TableUpdateReq(BaseModel):
    project_id: str
    base_digest: str
    updates: list[TableUpdateSpec]

```
            
---
## <kbd>class</kbd> `TableUpdateRes`
            
```python
class TableUpdateRes(BaseModel):
    digest: str

```
            
---

## <kbd>class</kbd> `TraceServerInterface`







---

### <kbd>method</kbd> `call_end`

```python
call_end(req: CallEndReq) → CallEndRes
```





---

### <kbd>method</kbd> `call_read`

```python
call_read(req: CallReadReq) → CallReadRes
```





---

### <kbd>method</kbd> `call_start`

```python
call_start(req: CallStartReq) → CallStartRes
```





---

### <kbd>method</kbd> `call_update`

```python
call_update(req: CallUpdateReq) → CallUpdateRes
```





---

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: CallsDeleteReq) → CallsDeleteRes
```





---

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: CallsQueryReq) → CallsQueryRes
```





---

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(req: CallsQueryStatsReq) → CallsQueryStatsRes
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
feedback_create(req: FeedbackCreateReq) → FeedbackCreateRes
```





---

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: FeedbackPurgeReq) → FeedbackPurgeRes
```





---

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: FeedbackQueryReq) → FeedbackQueryRes
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

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: ObjCreateReq) → ObjCreateRes
```





---

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: ObjReadReq) → ObjReadRes
```





---

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: ObjQueryReq) → ObjQueryRes
```





---

### <kbd>method</kbd> `op_create`

```python
op_create(req: OpCreateReq) → OpCreateRes
```





---

### <kbd>method</kbd> `op_read`

```python
op_read(req: OpReadReq) → OpReadRes
```





---

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: OpQueryReq) → OpQueryRes
```





---

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: RefsReadBatchReq) → RefsReadBatchRes
```





---

### <kbd>method</kbd> `table_create`

```python
table_create(req: TableCreateReq) → TableCreateRes
```





---

### <kbd>method</kbd> `table_query`

```python
table_query(req: TableQueryReq) → TableQueryRes
```





---

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```





