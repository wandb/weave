---
sidebar_label: trace_server_interface
---
    

# weave.trace_server.trace_server_interface



---


# API Overview



## Classes

- [`trace_server_interface.ActionsExecuteBatchReq`](#class-actionsexecutebatchreq)
- [`trace_server_interface.ActionsExecuteBatchRes`](#class-actionsexecutebatchres)
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
- [`trace_server_interface.LLMCostSchema`](#class-llmcostschema)
- [`trace_server_interface.LLMUsageSchema`](#class-llmusageschema)
- [`trace_server_interface.ObjCreateReq`](#class-objcreatereq)
- [`trace_server_interface.ObjCreateRes`](#class-objcreateres)
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
- [`trace_server_interface.TableQueryStatsReq`](#class-tablequerystatsreq)
- [`trace_server_interface.TableQueryStatsRes`](#class-tablequerystatsres)
- [`trace_server_interface.TableRowFilter`](#class-tablerowfilter)
- [`trace_server_interface.TableRowSchema`](#class-tablerowschema)
- [`trace_server_interface.TableSchemaForInsert`](#class-tableschemaforinsert)
- [`trace_server_interface.TableUpdateReq`](#class-tableupdatereq)
- [`trace_server_interface.TableUpdateRes`](#class-tableupdateres)
- [`trace_server_interface.TraceServerInterface`](#class-traceserverinterface)
- [`trace_server_interface.TraceStatus`](#class-tracestatus): An enumeration.
- [`trace_server_interface.WeaveSummarySchema`](#class-weavesummaryschema)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L868"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ActionsExecuteBatchReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `action_ref`: `<class 'str'>`
- `call_ids`: `list[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L875"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ActionsExecuteBatchRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L220"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallEndReq`





**Pydantic Fields:**

- `end`: `<class 'EndedCallSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L224"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallEndRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L228"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `id`: `<class 'str'>`
- `include_costs`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L234"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallReadRes`





**Pydantic Fields:**

- `call`: `typing.Optional[CallSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L81"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L121"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `serialize_typed_dicts`

```python
serialize_typed_dicts(v: dict[str, Any]) → dict[str, Any]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L211"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallStartReq`





**Pydantic Fields:**

- `start`: `<class 'StartedCallSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L215"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallStartRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `trace_id`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L359"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallUpdateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `call_id`: `<class 'str'>`
- `display_name`: `typing.Optional[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L371"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallUpdateRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L238"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsDeleteReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `call_ids`: `list[str]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L246"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsDeleteRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L294"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L315"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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
- `columns`: `typing.Optional[list[str]]`
- `expand_columns`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L345"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryRes`





**Pydantic Fields:**

- `calls`: `list[CallSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L349"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[CallsFilter]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L355"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CallsQueryStatsRes`





**Pydantic Fields:**

- `count`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L280"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CompletionsCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `inputs`: `<class 'CompletionsCreateRequestInputs'>`
- `wb_user_id`: `typing.Optional[str]`
- `track_llm_call`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L250"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L289"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CompletionsCreateRes`





**Pydantic Fields:**

- `response`: `dict[str, typing.Any]`
- `weave_call_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L786"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateInput`





**Pydantic Fields:**

- `prompt_token_cost`: `<class 'float'>`
- `completion_token_cost`: `<class 'float'>`
- `prompt_token_cost_unit`: `typing.Optional[str]`
- `completion_token_cost_unit`: `typing.Optional[str]`
- `effective_date`: `typing.Optional[datetime.datetime]`
- `provider_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L805"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `costs`: `dict[str, CostCreateInput]`
- `wb_user_id`: `typing.Optional[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L812"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostCreateRes`





**Pydantic Fields:**

- `ids`: `list[tuple[str, str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L859"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostPurgeReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `query`: `<class 'weave.trace_server.interface.query.Query'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L864"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostPurgeRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L842"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L816"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `fields`: `typing.Optional[list[str]]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L855"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `CostQueryRes`





**Pydantic Fields:**

- `results`: `list[CostQueryOutput]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L156"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EndedCallSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `id`: `<class 'str'>`
- `ended_at`: `<class 'datetime.datetime'>`
- `exception`: `typing.Optional[str]`
- `output`: `typing.Optional[typing.Any]`
- `summary`: `<class 'SummaryInsertMap'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L172"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `serialize_typed_dicts`

```python
serialize_typed_dicts(v: dict[str, Any]) → dict[str, Any]
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L782"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EnsureProjectExistsRes`





**Pydantic Fields:**

- `project_name`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L16"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ExtraKeysTypedDict`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L723"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L683"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L716"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackCreateRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`
- `wb_user_id`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L48"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackDict`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L746"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackPurgeReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `query`: `<class 'weave.trace_server.interface.query.Query'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L751"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackPurgeRes`






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L728"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `fields`: `typing.Optional[list[str]]`
- `query`: `typing.Optional[weave.trace_server.interface.query.Query]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L741"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackQueryRes`





**Pydantic Fields:**

- `result`: `list[dict[str, typing.Any]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L755"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L759"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackReplaceRes`





**Pydantic Fields:**

- `id`: `<class 'str'>`
- `created_at`: `<class 'datetime.datetime'>`
- `wb_user_id`: `<class 'str'>`
- `payload`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L773"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileContentReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L778"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileContentReadRes`





**Pydantic Fields:**

- `content`: `<class 'bytes'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L763"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileCreateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `name`: `<class 'str'>`
- `content`: `<class 'bytes'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L769"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FileCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L33"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LLMCostSchema`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L24"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LLMUsageSchema`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L407"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjCreateReq`





**Pydantic Fields:**

- `obj`: `<class 'ObjSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L411"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L448"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[ObjectVersionFilter]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`
- `sort_by`: `typing.Optional[list[SortBy]]`
- `metadata_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L479"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjQueryRes`





**Pydantic Fields:**

- `objs`: `list[ObjSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L415"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L421"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjReadRes`





**Pydantic Fields:**

- `obj`: `<class 'ObjSchema'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L177"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L190"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `object_id`: `<class 'str'>`
- `val`: `typing.Any`
- `builtin_object_class`: `typing.Optional[str]`
- `set_base_object_class`: `typing.Optional[str]`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L200"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `model_post_init`

```python
model_post_init(_ObjSchemaForInsert__context: Any) → None
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L425"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ObjectVersionFilter`





**Pydantic Fields:**

- `base_object_classes`: `typing.Optional[list[str]]`
- `object_ids`: `typing.Optional[list[str]]`
- `is_op`: `typing.Optional[bool]`
- `latest_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L375"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpCreateReq`





**Pydantic Fields:**

- `op_obj`: `<class 'ObjSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L379"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L398"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `filter`: `typing.Optional[OpVersionFilter]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L403"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpQueryRes`





**Pydantic Fields:**

- `op_objs`: `list[ObjSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L383"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpReadReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `name`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L389"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpReadRes`





**Pydantic Fields:**

- `op_obj`: `<class 'ObjSchema'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L393"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OpVersionFilter`





**Pydantic Fields:**

- `op_names`: `typing.Optional[list[str]]`
- `latest_only`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L675"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RefsReadBatchReq`





**Pydantic Fields:**

- `refs`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L679"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RefsReadBatchRes`





**Pydantic Fields:**

- `vals`: `list[typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L306"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SortBy`





**Pydantic Fields:**

- `field`: `<class 'str'>`
- `direction`: `typing.Literal['asc', 'desc']`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L129"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

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

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L73"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SummaryInsertMap`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L77"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `SummaryMap`








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L542"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableAppendSpec`





**Pydantic Fields:**

- `append`: `<class 'TableAppendSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L538"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableAppendSpecPayload`





**Pydantic Fields:**

- `row`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L483"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableCreateReq`





**Pydantic Fields:**

- `table`: `<class 'TableSchemaForInsert'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L593"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableCreateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `row_digests`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L559"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableInsertSpec`





**Pydantic Fields:**

- `insert`: `<class 'TableInsertSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L554"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableInsertSpecPayload`





**Pydantic Fields:**

- `index`: `<class 'int'>`
- `row`: `dict[str, typing.Any]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L550"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TablePopSpec`





**Pydantic Fields:**

- `pop`: `<class 'TablePopSpecPayload'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L546"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TablePopSpecPayload`





**Pydantic Fields:**

- `index`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L622"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`
- `filter`: `typing.Optional[TableRowFilter]`
- `limit`: `typing.Optional[int]`
- `offset`: `typing.Optional[int]`
- `sort_by`: `typing.Optional[list[SortBy]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L657"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryRes`





**Pydantic Fields:**

- `rows`: `list[TableRowSchema]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L661"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `digest`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L671"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableQueryStatsRes`





**Pydantic Fields:**

- `count`: `<class 'int'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L609"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableRowFilter`





**Pydantic Fields:**

- `row_digests`: `typing.Optional[list[str]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L588"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableRowSchema`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `val`: `typing.Any`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L206"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableSchemaForInsert`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `rows`: `list[dict[str, typing.Any]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L566"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableUpdateReq`





**Pydantic Fields:**

- `project_id`: `<class 'str'>`
- `base_digest`: `<class 'str'>`
- `updates`: `list[typing.Union[TableAppendSpec, TablePopSpec, TableInsertSpec]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L572"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TableUpdateRes`





**Pydantic Fields:**

- `digest`: `<class 'str'>`
- `updated_row_digests`: `list[str]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L879"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TraceServerInterface`







---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L923"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `actions_execute_batch`

```python
actions_execute_batch(req: ActionsExecuteBatchReq) → ActionsExecuteBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L887"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_end`

```python
call_end(req: CallEndReq) → CallEndRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L888"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_read`

```python
call_read(req: CallReadReq) → CallReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L886"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_start`

```python
call_start(req: CallStartReq) → CallStartRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L893"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `call_update`

```python
call_update(req: CallUpdateReq) → CallUpdateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L891"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_delete`

```python
calls_delete(req: CallsDeleteReq) → CallsDeleteRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L889"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query`

```python
calls_query(req: CallsQueryReq) → CallsQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L892"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stats`

```python
calls_query_stats(req: CallsQueryStatsReq) → CallsQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L890"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `calls_query_stream`

```python
calls_query_stream(req: CallsQueryReq) → Iterator[CallSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L928"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `completions_create`

```python
completions_create(req: CompletionsCreateReq) → CompletionsCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L901"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_create`

```python
cost_create(req: CostCreateReq) → CostCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L903"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_purge`

```python
cost_purge(req: CostPurgeReq) → CostPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L902"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `cost_query`

```python
cost_query(req: CostQueryReq) → CostQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L880"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ensure_project_exists`

```python
ensure_project_exists(entity: str, project: str) → EnsureProjectExistsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L917"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_create`

```python
feedback_create(req: FeedbackCreateReq) → FeedbackCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L919"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_purge`

```python
feedback_purge(req: FeedbackPurgeReq) → FeedbackPurgeRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L918"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_query`

```python
feedback_query(req: FeedbackQueryReq) → FeedbackQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L920"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `feedback_replace`

```python
feedback_replace(req: FeedbackReplaceReq) → FeedbackReplaceRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L916"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_content_read`

```python
file_content_read(req: FileContentReadReq) → FileContentReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L915"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `file_create`

```python
file_create(req: FileCreateReq) → FileCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L906"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_create`

```python
obj_create(req: ObjCreateReq) → ObjCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L907"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `obj_read`

```python
obj_read(req: ObjReadReq) → ObjReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L908"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `objs_query`

```python
objs_query(req: ObjQueryReq) → ObjQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L896"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_create`

```python
op_create(req: OpCreateReq) → OpCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L897"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `op_read`

```python
op_read(req: OpReadReq) → OpReadRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L898"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `ops_query`

```python
ops_query(req: OpQueryReq) → OpQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L914"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs_read_batch`

```python
refs_read_batch(req: RefsReadBatchReq) → RefsReadBatchRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L909"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_create`

```python
table_create(req: TableCreateReq) → TableCreateRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L911"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query`

```python
table_query(req: TableQueryReq) → TableQueryRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L913"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stats`

```python
table_query_stats(req: TableQueryStatsReq) → TableQueryStatsRes
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L912"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_query_stream`

```python
table_query_stream(req: TableQueryReq) → Iterator[TableRowSchema]
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L910"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `table_update`

```python
table_update(req: TableUpdateReq) → TableUpdateRes
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L58"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `TraceStatus`
An enumeration. 





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/trace_server_interface.py#L64"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `WeaveSummarySchema`







