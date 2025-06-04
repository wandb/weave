---
sidebar_label: trace_server_interface
---
    

# weave.trace_server.trace_server_interface



---


# API Overview



## Classes

- [`trace_server_interface.ActionsExecuteBatchReq`](#class-actionsexecutebatchreq)
- [`trace_server_interface.ActionsExecuteBatchRes`](#class-actionsexecutebatchres)
- [`trace_server_interface.CallBatchEndMode`](#class-callbatchendmode)
- [`trace_server_interface.CallBatchStartMode`](#class-callbatchstartmode)
- [`trace_server_interface.CallCreateBatchReq`](#class-callcreatebatchreq)
- [`trace_server_interface.CallCreateBatchRes`](#class-callcreatebatchres)
- [`trace_server_interface.CallEndReq`](#class-callendreq)
- [`trace_server_interface.CallEndRes`](#class-callendres)
- [`trace_server_interface.CallReadReq`](#class-callreadreq)
- [`trace_server_interface.CallReadRes`](#class-callreadres)
- [`trace_server_interface.CallSchema`](#class-callschema)
- [`trace_server_interface.CallStartReq`](#class-callstartreq)
- [`trace_server_interface.CallStartRes`](#class-callstartres)
- [`trace_server_interface.CallUpdateReq`](#class-callupdatereq)
- [`trace_server_interface.CallUpdateRes`](#class-callupdateres)
- [`trace_server_interface.CallsDeleteReq`](#class-callsdeletereq)
- [`trace_server_interface.CallsDeleteRes`](#class-callsdeleteres)
- [`trace_server_interface.CallsFilter`](#class-callsfilter)
- [`trace_server_interface.CallsQueryReq`](#class-callsqueryreq)
- [`trace_server_interface.CallsQueryRes`](#class-callsqueryres)
- [`trace_server_interface.CallsQueryStatsReq`](#class-callsquerystatsreq)
- [`trace_server_interface.CallsQueryStatsRes`](#class-callsquerystatsres)
- [`trace_server_interface.CompletionsCreateReq`](#class-completionscreatereq)
- [`trace_server_interface.CompletionsCreateRequestInputs`](#class-completionscreaterequestinputs)
- [`trace_server_interface.CompletionsCreateRes`](#class-completionscreateres)
- [`trace_server_interface.CostCreateInput`](#class-costcreateinput)
- [`trace_server_interface.CostCreateReq`](#class-costcreatereq)
- [`trace_server_interface.CostCreateRes`](#class-costcreateres)
- [`trace_server_interface.CostPurgeReq`](#class-costpurgereq)
- [`trace_server_interface.CostPurgeRes`](#class-costpurgeres)
- [`trace_server_interface.CostQueryOutput`](#class-costqueryoutput)
- [`trace_server_interface.CostQueryReq`](#class-costqueryreq)
- [`trace_server_interface.CostQueryRes`](#class-costqueryres)
- [`trace_server_interface.EndedCallSchemaForInsert`](#class-endedcallschemaforinsert)
- [`trace_server_interface.EnsureProjectExistsRes`](#class-ensureprojectexistsres)
- [`trace_server_interface.ExportTracePartialSuccess`](#class-exporttracepartialsuccess)
- [`trace_server_interface.ExtraKeysTypedDict`](#class-extrakeystypeddict)
- [`trace_server_interface.Feedback`](#class-feedback)
- [`trace_server_interface.FeedbackCreateReq`](#class-feedbackcreatereq)
- [`trace_server_interface.FeedbackCreateRes`](#class-feedbackcreateres)
- [`trace_server_interface.FeedbackDict`](#class-feedbackdict)
- [`trace_server_interface.FeedbackPurgeReq`](#class-feedbackpurgereq)
- [`trace_server_interface.FeedbackPurgeRes`](#class-feedbackpurgeres)
- [`trace_server_interface.FeedbackQueryReq`](#class-feedbackqueryreq)
- [`trace_server_interface.FeedbackQueryRes`](#class-feedbackqueryres)
- [`trace_server_interface.FeedbackReplaceReq`](#class-feedbackreplacereq)
- [`trace_server_interface.FeedbackReplaceRes`](#class-feedbackreplaceres)
- [`trace_server_interface.FileContentReadReq`](#class-filecontentreadreq)
- [`trace_server_interface.FileContentReadRes`](#class-filecontentreadres)
- [`trace_server_interface.FileCreateReq`](#class-filecreatereq)
- [`trace_server_interface.FileCreateRes`](#class-filecreateres)
- [`trace_server_interface.FilesStatsReq`](#class-filesstatsreq)
- [`trace_server_interface.FilesStatsRes`](#class-filesstatsres)
- [`trace_server_interface.LLMCostSchema`](#class-llmcostschema)
- [`trace_server_interface.LLMUsageSchema`](#class-llmusageschema)
- [`trace_server_interface.ObjCreateReq`](#class-objcreatereq)
- [`trace_server_interface.ObjCreateRes`](#class-objcreateres)
- [`trace_server_interface.ObjDeleteReq`](#class-objdeletereq)
- [`trace_server_interface.ObjDeleteRes`](#class-objdeleteres)
- [`trace_server_interface.ObjQueryReq`](#class-objqueryreq)
- [`trace_server_interface.ObjQueryRes`](#class-objqueryres)
- [`trace_server_interface.ObjReadReq`](#class-objreadreq)
- [`trace_server_interface.ObjReadRes`](#class-objreadres)
- [`trace_server_interface.ObjSchema`](#class-objschema)
- [`trace_server_interface.ObjSchemaForInsert`](#class-objschemaforinsert)
- [`trace_server_interface.ObjectVersionFilter`](#class-objectversionfilter)
- [`trace_server_interface.OpCreateReq`](#class-opcreatereq)
- [`trace_server_interface.OpCreateRes`](#class-opcreateres)
- [`trace_server_interface.OpQueryReq`](#class-opqueryreq)
- [`trace_server_interface.OpQueryRes`](#class-opqueryres)
- [`trace_server_interface.OpReadReq`](#class-opreadreq)
- [`trace_server_interface.OpReadRes`](#class-opreadres)
- [`trace_server_interface.OpVersionFilter`](#class-opversionfilter)
- [`trace_server_interface.OtelExportReq`](#class-otelexportreq)
- [`trace_server_interface.OtelExportRes`](#class-otelexportres)
- [`trace_server_interface.ProjectStatsReq`](#class-projectstatsreq)
- [`trace_server_interface.ProjectStatsRes`](#class-projectstatsres)
- [`trace_server_interface.RefsReadBatchReq`](#class-refsreadbatchreq)
- [`trace_server_interface.RefsReadBatchRes`](#class-refsreadbatchres)
- [`trace_server_interface.SortBy`](#class-sortby)
- [`trace_server_interface.StartedCallSchemaForInsert`](#class-startedcallschemaforinsert)
- [`trace_server_interface.SummaryInsertMap`](#class-summaryinsertmap)
- [`trace_server_interface.SummaryMap`](#class-summarymap)
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
- [`trace_server_interface.TableQueryStatsBatchReq`](#class-tablequerystatsbatchreq)
- [`trace_server_interface.TableQueryStatsBatchRes`](#class-tablequerystatsbatchres)
- [`trace_server_interface.TableQueryStatsReq`](#class-tablequerystatsreq)
- [`trace_server_interface.TableQueryStatsRes`](#class-tablequerystatsres)
- [`trace_server_interface.TableRowFilter`](#class-tablerowfilter)
- [`trace_server_interface.TableRowSchema`](#class-tablerowschema)
- [`trace_server_interface.TableSchemaForInsert`](#class-tableschemaforinsert)
- [`trace_server_interface.TableStatsRow`](#class-tablestatsrow)
- [`trace_server_interface.TableUpdateReq`](#class-tableupdatereq)
- [`trace_server_interface.TableUpdateRes`](#class-tableupdateres)
- [`trace_server_interface.TraceServerInterface`](#class-traceserverinterface)
- [`trace_server_interface.TraceStatus`](#class-tracestatus)
- [`trace_server_interface.WeaveSummarySchema`](#class-weavesummaryschema)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1001"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ActionsExecuteBatchReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `action_ref`: `<class 'str'>`
- `call_ids`: `list[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1008"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ActionsExecuteBatchRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L273"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallBatchEndMode`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'CallEndReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L268"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallBatchStartMode`





**Pydantic Fields:**

- `mode`: `<class 'str'>`
- `req`: `<class 'CallStartReq'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L278"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallCreateBatchReq`





**Pydantic Fields:**

- `batch`: `list[typing.Union[CallBatchStartMode, CallBatchEndMode]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L282"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallCreateBatchRes`





**Pydantic Fields:**

- `res`: `list[typing.Union[CallStartRes, CallEndRes]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L260"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallEndReq`





**Pydantic Fields:**

- `end`: `<class 'EndedCallSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L264"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallEndRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L286"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `id`: `<class 'str'>`
- `include_costs`: `typing.Optional[bool]`
- `include_storage_size`: `typing.Optional[bool]`
- `include_total_storage_size`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L294"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallReadRes`





**Pydantic Fields:**

- `call`: `typing.Optional[CallSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L88"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallSchema`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `project_id`: `<class 'str'>`
- `op_name`: `<class 'str'>`
- `display_name`: `typing.Optional[str]`
- `trace_id`: `<class 'str'>`
- `parent_id`: `typing.Optional[str]`
- `started_at`: `<class 'datetime.datetime'>`
- `attributes`: `dict[str, typing.Any]`
- `inputs`: `dict[str, typing.Any]`
- `ended_at`: `typing.Optional[datetime.datetime]`
- `exception`: `typing.Optional[str]`
- `output`: `typing.Optional[typing.Any]`
- `summary`: `typing.Optional[SummaryMap]`
- `wb_user_id`: `typing.Optional[str]`
- `wb_run_id`: `typing.Optional[str]`
- `deleted_at`: `typing.Optional[datetime.datetime]`
- `storage_size_bytes`: `typing.Optional[int]`
- `total_storage_size_bytes`: `typing.Optional[int]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L134"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `serialize_typed_dicts`

```python
serialize_typed_dicts(v: dict[str, Any]) → dict[str, Any]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L251"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallStartReq`





**Pydantic Fields:**

- `start`: `<class 'StartedCallSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L255"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallStartRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `trace_id`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L432"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallUpdateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `call_id`: `<class 'str'>`
- `display_name`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L444"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallUpdateRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L298"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsDeleteReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `call_ids`: `list[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L306"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsDeleteRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L354"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsFilter`





**Pydantic Fields:**

- `op_names`: `typing.Optional[list[str]]`
- `input_refs`: `typing.Optional[list[str]]`
- `output_refs`: `typing.Optional[list[str]]`
- `parent_ids`: `typing.Optional[list[str]]`
- `trace_ids`: `typing.Optional[list[str]]`
- `call_ids`: `typing.Optional[list[str]]`
- `trace_roots_only`: `typing.Optional[bool]`
- `wb_user_ids`: `typing.Optional[list[str]]`
- `wb_run_ids`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L375"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[CallsFilter]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `include_costs`: `typing.Optional[bool]`
- `include_feedback`: `typing.Optional[bool]`
- `include_storage_size`: `typing.Optional[bool]`
- `include_total_storage_size`: `typing.Optional[bool]`
- `columns`: `typing.Optional[list[str]]`
- `expand_columns`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L415"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryRes`





**Pydantic Fields:**

- `calls`: `list[CallSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L419"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[CallsFilter]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `limit`: `typing.Optional[int]`
- `include_total_storage_size`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L427"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryStatsRes`





**Pydantic Fields:**

- `count`: `<class 'int'>`
- `total_storage_size_bytes`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L340"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CompletionsCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `inputs`: `<class 'CompletionsCreateRequestInputs'>`
- `wb_user_id`: `typing.Optional[str]`
- `track_llm_call`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L310"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CompletionsCreateRequestInputs`





**Pydantic Fields:**

- `model`: `<class 'str'>`
- `messages`: `<class 'list'>`
- `timeout`: `typing.Union[float, str, NoneType]`
- `temperature`: `typing.Optional[float]`
- `top_p`: `typing.Optional[float]`
- `n`: `typing.Optional[int]`
- `stop`: `typing.Union[str, list, NoneType]`
- `max_completion_tokens`: `typing.Optional[int]`
- `max_tokens`: `typing.Optional[int]`
- `modalities`: `typing.Optional[list]`
- `presence_penalty`: `typing.Optional[float]`
- `frequency_penalty`: `typing.Optional[float]`
- `logit_bias`: `typing.Optional[dict]`
- `user`: `typing.Optional[str]`
- `response_format`: `typing.Union[dict, type[pydantic.main.BaseModel], NoneType]`
- `seed`: `typing.Optional[int]`
- `tools`: `typing.Optional[list]`
- `tool_choice`: `typing.Union[str, dict, NoneType]`
- `logprobs`: `typing.Optional[bool]`
- `top_logprobs`: `typing.Optional[int]`
- `parallel_tool_calls`: `typing.Optional[bool]`
- `extra_headers`: `typing.Optional[dict]`
- `functions`: `typing.Optional[list]`
- `function_call`: `typing.Optional[str]`
- `api_version`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L349"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CompletionsCreateRes`





**Pydantic Fields:**

- `response`: `dict[str, typing.Any]`
- `weave_call_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L919"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateInput`





**Pydantic Fields:**

- `prompt_token_cost`: `<class 'float'>`
- `completion_token_cost`: `<class 'float'>`
- `prompt_token_cost_unit`: `typing.Optional[str]`
- `completion_token_cost_unit`: `typing.Optional[str]`
- `effective_date`: `typing.Optional[datetime.datetime]`
- `provider_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L938"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `costs`: `dict[str, CostCreateInput]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L945"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateRes`





**Pydantic Fields:**

- `ids`: `list[tuple[str, str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L992"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostPurgeReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `query`: `<class 'weave.trace_server.interface.query.Query'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L997"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostPurgeRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L975"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostQueryOutput`





**Pydantic Fields:**

- `id`: `typing.Optional[str]`
- `llm_id`: `typing.Optional[str]`
- `prompt_token_cost`: `typing.Optional[float]`
- `completion_token_cost`: `typing.Optional[float]`
- `prompt_token_cost_unit`: `typing.Optional[str]`
- `completion_token_cost_unit`: `typing.Optional[str]`
- `effective_date`: `typing.Optional[datetime.datetime]`
- `provider_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L949"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `fields`: `typing.Optional[list[str]]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L988"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostQueryRes`





**Pydantic Fields:**

- `results`: `list[CostQueryOutput]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L169"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EndedCallSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `id`: `<class 'str'>`
- `ended_at`: `<class 'datetime.datetime'>`
- `exception`: `typing.Optional[str]`
- `output`: `typing.Optional[typing.Any]`
- `summary`: `<class 'SummaryInsertMap'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L185"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `serialize_typed_dicts`

```python
serialize_typed_dicts(v: dict[str, Any]) → dict[str, Any]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L915"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EnsureProjectExistsRes`





**Pydantic Fields:**

- `project_name`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L237"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ExportTracePartialSuccess`





**Pydantic Fields:**

- `rejected_spans`: `<class 'int'>`
- `error_message`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L21"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ExtraKeysTypedDict`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L848"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Feedback`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `weave_ref`: `<class 'str'>`
- `creator`: `typing.Optional[str]`
- `feedback_type`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`
- `annotation_ref`: `typing.Optional[str]`
- `runnable_ref`: `typing.Optional[str]`
- `call_ref`: `typing.Optional[str]`
- `trigger_ref`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`
- `id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L808"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `weave_ref`: `<class 'str'>`
- `creator`: `typing.Optional[str]`
- `feedback_type`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`
- `annotation_ref`: `typing.Optional[str]`
- `runnable_ref`: `typing.Optional[str]`
- `call_ref`: `typing.Optional[str]`
- `trigger_ref`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L841"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackCreateRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`
- `wb_user_id`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L53"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackDict`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L871"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackPurgeReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `query`: `<class 'weave.trace_server.interface.query.Query'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L876"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackPurgeRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L853"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `fields`: `typing.Optional[list[str]]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L866"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackQueryRes`





**Pydantic Fields:**

- `result`: `list[dict[str, typing.Any]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L880"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackReplaceReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `weave_ref`: `<class 'str'>`
- `creator`: `typing.Optional[str]`
- `feedback_type`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`
- `annotation_ref`: `typing.Optional[str]`
- `runnable_ref`: `typing.Optional[str]`
- `call_ref`: `typing.Optional[str]`
- `trigger_ref`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`
- `feedback_id`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L884"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackReplaceRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`
- `wb_user_id`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L898"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileContentReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L907"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileContentReadRes`





**Pydantic Fields:**

- `content`: `<class 'bytes'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L888"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `name`: `<class 'str'>`
- `content`: `<class 'bytes'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L894"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L903"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FilesStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L911"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FilesStatsRes`





**Pydantic Fields:**

- `total_size_bytes`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L38"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LLMCostSchema`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L29"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LLMUsageSchema`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L480"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjCreateReq`





**Pydantic Fields:**

- `obj`: `<class 'ObjSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L484"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L562"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjDeleteReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `digests`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L571"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjDeleteRes`





**Pydantic Fields:**

- `num_deleted`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L527"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[ObjectVersionFilter]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `metadata_only`: `typing.Optional[bool]`
- `include_storage_size`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L575"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjQueryRes`





**Pydantic Fields:**

- `objs`: `list[ObjSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L488"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `digest`: `<class 'str'>`
- `metadata_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L500"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjReadRes`





**Pydantic Fields:**

- `obj`: `<class 'ObjSchema'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L190"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjSchema`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`
- `deleted_at`: `typing.Optional[datetime.datetime]`
- `digest`: `<class 'str'>`
- `version_index`: `<class 'int'>`
- `is_latest`: `<class 'int'>`
- `kind`: `<class 'str'>`
- `base_object_class`: `typing.Optional[str]`
- `val`: `typing.Any`
- `wb_user_id`: `typing.Optional[str]`
- `size_bytes`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L206"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `val`: `typing.Any`
- `builtin_object_class`: `typing.Optional[str]`
- `set_base_object_class`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L218"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `model_post_init`

```python
model_post_init(_ObjSchemaForInsert__context: Any) → None
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L504"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjectVersionFilter`





**Pydantic Fields:**

- `base_object_classes`: `typing.Optional[list[str]]`
- `object_ids`: `typing.Optional[list[str]]`
- `is_op`: `typing.Optional[bool]`
- `latest_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L448"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpCreateReq`





**Pydantic Fields:**

- `op_obj`: `<class 'ObjSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L452"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L471"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[OpVersionFilter]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L476"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpQueryRes`





**Pydantic Fields:**

- `op_objs`: `list[ObjSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L456"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `name`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L462"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpReadRes`





**Pydantic Fields:**

- `op_obj`: `<class 'ObjSchema'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L466"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpVersionFilter`





**Pydantic Fields:**

- `op_names`: `typing.Optional[list[str]]`
- `latest_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L229"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OtelExportReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `traces`: `typing.Any`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L244"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OtelExportRes`





**Pydantic Fields:**

- `partial_success`: `typing.Optional[ExportTracePartialSuccess]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1012"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ProjectStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `include_trace_storage_size`: `typing.Optional[bool]`
- `include_object_storage_size`: `typing.Optional[bool]`
- `include_table_storage_size`: `typing.Optional[bool]`
- `include_file_storage_size`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1020"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ProjectStatsRes`





**Pydantic Fields:**

- `trace_storage_size_bytes`: `<class 'int'>`
- `objects_storage_size_bytes`: `<class 'int'>`
- `tables_storage_size_bytes`: `<class 'int'>`
- `files_storage_size_bytes`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L800"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RefsReadBatchReq`





**Pydantic Fields:**

- `refs`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L804"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RefsReadBatchRes`





**Pydantic Fields:**

- `vals`: `list[typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L366"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SortBy`





**Pydantic Fields:**

- `field`: `<class 'str'>`
- `direction`: `typing.Literal['asc', 'desc']`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L142"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `StartedCallSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `id`: `typing.Optional[str]`
- `op_name`: `<class 'str'>`
- `display_name`: `typing.Optional[str]`
- `trace_id`: `typing.Optional[str]`
- `parent_id`: `typing.Optional[str]`
- `started_at`: `<class 'datetime.datetime'>`
- `attributes`: `dict[str, typing.Any]`
- `inputs`: `dict[str, typing.Any]`
- `wb_user_id`: `typing.Optional[str]`
- `wb_run_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L79"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SummaryInsertMap`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L84"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SummaryMap`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L638"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableAppendSpec`





**Pydantic Fields:**

- `append`: `<class 'TableAppendSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L634"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableAppendSpecPayload`





**Pydantic Fields:**

- `row`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L579"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableCreateReq`





**Pydantic Fields:**

- `table`: `<class 'TableSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L690"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `row_digests`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L655"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableInsertSpec`





**Pydantic Fields:**

- `insert`: `<class 'TableInsertSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L650"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableInsertSpecPayload`





**Pydantic Fields:**

- `index`: `<class 'int'>`
- `row`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L646"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TablePopSpec`





**Pydantic Fields:**

- `pop`: `<class 'TablePopSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L642"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TablePopSpecPayload`





**Pydantic Fields:**

- `index`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L719"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`
- `filter`: `typing.Optional[TableRowFilter]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`
- `sort_by`: `typing.Optional[list[SortBy]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L754"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryRes`





**Pydantic Fields:**

- `rows`: `list[TableRowSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L767"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsBatchReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digests`: `typing.Optional[list[str]]`
- `include_storage_size`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L796"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsBatchRes`





**Pydantic Fields:**

- `tables`: `list[TableStatsRow]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L758"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L786"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsRes`





**Pydantic Fields:**

- `count`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L706"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableRowFilter`





**Pydantic Fields:**

- `row_digests`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L684"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableRowSchema`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `val`: `typing.Any`
- `original_index`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L224"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `rows`: `list[dict[str, typing.Any]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L790"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableStatsRow`





**Pydantic Fields:**

- `count`: `<class 'int'>`
- `digest`: `<class 'str'>`
- `storage_size_bytes`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L662"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableUpdateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `base_digest`: `<class 'str'>`
- `updates`: `list[typing.Union[TableAppendSpec, TablePopSpec, TableInsertSpec]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L668"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableUpdateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `updated_row_digests`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1027"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TraceServerInterface`







---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1088"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `actions_execute_batch`

```python
actions_execute_batch(req: ActionsExecuteBatchReq) → ActionsExecuteBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1038"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_end`

```python
call_end(req: CallEndReq) → CallEndRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1039"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_read`

```python
call_read(req: CallReadReq) → CallReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1037"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start`

```python
call_start(req: CallStartReq) → CallStartRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1045"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start_batch`

```python
call_start_batch(req: CallCreateBatchReq) → CallCreateBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1044"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_update`

```python
call_update(req: CallUpdateReq) → CallUpdateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1042"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: CallsDeleteReq) → CallsDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1040"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: CallsQueryReq) → CallsQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1043"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(req: CallsQueryStatsReq) → CallsQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1041"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(req: CallsQueryReq) → Iterator[CallSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1093"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `completions_create`

```python
completions_create(req: CompletionsCreateReq) → CompletionsCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1053"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_create`

```python
cost_create(req: CostCreateReq) → CostCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1055"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_purge`

```python
cost_purge(req: CostPurgeReq) → CostPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1054"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_query`

```python
cost_query(req: CostQueryReq) → CostQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1028"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → EnsureProjectExistsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1082"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(req: FeedbackCreateReq) → FeedbackCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1084"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: FeedbackPurgeReq) → FeedbackPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1083"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: FeedbackQueryReq) → FeedbackQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1085"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_replace`

```python
feedback_replace(req: FeedbackReplaceReq) → FeedbackReplaceRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1078"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1077"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1079"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `files_stats`

```python
files_stats(req: FilesStatsReq) → FilesStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1058"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: ObjCreateReq) → ObjCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1061"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_delete`

```python
obj_delete(req: ObjDeleteReq) → ObjDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1059"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: ObjReadReq) → ObjReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1060"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: ObjQueryReq) → ObjQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1048"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_create`

```python
op_create(req: OpCreateReq) → OpCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1049"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_read`

```python
op_read(req: OpReadReq) → OpReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1050"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: OpQueryReq) → OpQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1034"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `otel_export`

```python
otel_export(req: OtelExportReq) → OtelExportRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1096"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `project_stats`

```python
project_stats(req: ProjectStatsReq) → ProjectStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1074"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: RefsReadBatchReq) → RefsReadBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1064"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_create`

```python
table_create(req: TableCreateReq) → TableCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1066"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query`

```python
table_query(req: TableQueryReq) → TableQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1068"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats`

```python
table_query_stats(req: TableQueryStatsReq) → TableQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1069"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats_batch`

```python
table_query_stats_batch(req: TableQueryStatsBatchReq) → TableQueryStatsBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1067"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stream`

```python
table_query_stream(req: TableQueryReq) → Iterator[TableRowSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L1065"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L63"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TraceStatus`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L70"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `WeaveSummarySchema`







