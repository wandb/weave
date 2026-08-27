/**
 * Weave-owned copies of the swagger-form types that were previously
 * re-exported from the generated swagger client. Public WeaveClient /
 * package signatures keep these shapes; the Stainless models are not
 * re-exported.
 */

export type AgentChatAgentHandoff = object;

export interface AgentChatAgentStart {
  model?: string | null;
  system_instructions?: string | null;
  tool_definitions?: string | null;
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
}

export interface AgentChatAssistantMessage {
  text: string;
  model?: string | null;
  reasoning_content?: string | null;
  reasoning_tokens?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  input_cost_usd?: number | null;
  output_cost_usd?: number | null;
  total_cost_usd?: number | null;
  duration_ms?: number | null;
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
  content_refs?: string[];
}

export interface AgentChatContextCompacted {
  compaction_summary?: string | null;
  compaction_items_before?: number | null;
  compaction_items_after?: number | null;
}

export interface AgentChatToolCall {
  tool_name?: string | null;
  tool_arguments?: string | null;
  tool_result?: string | null;
  duration_ms?: number | null;
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
  content_refs?: string[];
}

export interface AgentChatUserMessage {
  text: string;
  content_refs?: string[];
}

export interface AgentChatMessage {
  type:
    | 'user_message'
    | 'assistant_message'
    | 'tool_call'
    | 'agent_handoff'
    | 'agent_start'
    | 'context_compacted';
  span_id?: string | null;
  agent_name?: string | null;
  agent_version?: string | null;
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  started_at?: string | null;
  user_message?: AgentChatUserMessage | null;
  assistant_message?: AgentChatAssistantMessage | null;
  tool_call?: AgentChatToolCall | null;
  agent_start?: AgentChatAgentStart | null;
  agent_handoff?: AgentChatAgentHandoff | null;
  context_compacted?: AgentChatContextCompacted | null;
  feedback?: Record<string, any>[] | null;
}

export interface AgentCustomAttrSchemaItem {
  source:
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  key: string;
  value_type: 'string' | 'int' | 'float' | 'bool';
  span_count: number;
}

export interface AgentGroupByRef {
  source?:
    | 'field'
    | 'column'
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  key: string;
  alias?: string | null;
}

export interface AgentSchema {
  project_id: string;
  agent_name: string;
  invocation_count: number;
  span_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_duration_ms: number;
  error_count: number;
  first_seen: string | null;
  last_seen: string | null;
  total_cost_usd?: number | null;
}

export interface AgentSearchMatchedMessage {
  span_id: string;
  trace_id: string;
  role:
    | ''
    | 'user'
    | 'assistant'
    | 'system'
    | 'tool'
    | 'tool_call'
    | 'tool_result'
    | string;
  content_preview: string;
  content_digest: string;
  started_at: string;
}

export interface AgentSearchConversationResult {
  conversation_id: string;
  conversation_name: string;
  agent_name: string;
  matched_messages: AgentSearchMatchedMessage[];
  last_activity: string;
}

export interface AgentSpanStatsColumn {
  name: string;
  role: 'time' | 'bucket' | 'group' | 'metric';
  value_type: 'datetime' | 'number' | 'boolean' | 'string';
  metric?: string | null;
  aggregation?: string | null;
}

export interface AgentSpanValueRef {
  source?:
    | 'field'
    | 'derived'
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  key: string;
}

export interface AgentSpanStatsMetricSpec {
  alias: string;
  value_type: 'datetime' | 'number' | 'boolean' | 'string';
  aggregations?: (
    | 'sum'
    | 'avg'
    | 'min'
    | 'max'
    | 'count'
    | 'count_distinct'
    | 'count_true'
    | 'count_false'
  )[];
  percentiles?: number[];
  value: AgentSpanValueRef;
}

export interface NormalizedMessage {
  role?: string;
  content: string;
  finish_reason?: string;
}

export interface AgentSpanSchema {
  project_id: string;
  trace_id: string;
  span_id: string;
  parent_span_id?: string | null;
  span_name?: string | null;
  span_kind?:
    | 'UNSPECIFIED'
    | 'INTERNAL'
    | 'SERVER'
    | 'CLIENT'
    | 'PRODUCER'
    | 'CONSUMER'
    | null;
  started_at?: string | null;
  ended_at?: string | null;
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  status_message?: string | null;
  operation_name?: string | null;
  provider_name?: string | null;
  agent_name?: string | null;
  agent_id?: string | null;
  agent_description?: string | null;
  agent_version?: string | null;
  eval_run_id?: string | null;
  eval_predict_and_score_call_id?: string | null;
  eval_kind?: string | null;
  eval_row_digest?: string | null;
  eval_example_id?: string | null;
  eval_trial_index?: number | null;
  eval_evaluation_name?: string | null;
  parent_call_id?: string | null;
  parent_call_trace_id?: string | null;
  request_model?: string | null;
  response_model?: string | null;
  response_id?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  cache_creation_input_tokens?: number | null;
  cache_read_input_tokens?: number | null;
  input_cost_usd?: number | null;
  output_cost_usd?: number | null;
  cache_read_cost_usd?: number | null;
  cache_creation_cost_usd?: number | null;
  total_cost_usd?: number | null;
  reasoning_content?: string | null;
  conversation_id?: string | null;
  conversation_name?: string | null;
  tool_name?: string | null;
  tool_type?: string | null;
  tool_call_id?: string | null;
  tool_description?: string | null;
  tool_definitions?: string | null;
  finish_reasons?: string[];
  error_type?: string | null;
  request_temperature?: number | null;
  request_max_tokens?: number | null;
  request_top_p?: number | null;
  request_frequency_penalty?: number | null;
  request_presence_penalty?: number | null;
  request_seed?: number | null;
  request_stop_sequences?: string[];
  request_choice_count?: number | null;
  output_type?: string | null;
  input_messages?: NormalizedMessage[];
  output_messages?: NormalizedMessage[];
  system_instructions?: string[];
  tool_call_arguments?: string | null;
  tool_call_result?: string | null;
  compaction_summary?: string | null;
  compaction_items_before?: number | null;
  compaction_items_after?: number | null;
  content_refs?: string[];
  artifact_refs?: string[];
  object_refs?: string[];
  custom_attrs_string?: Record<string, string>;
  custom_attrs_int?: Record<string, number>;
  custom_attrs_float?: Record<string, number>;
  custom_attrs_bool?: Record<string, boolean>;
  server_address?: string | null;
  server_port?: number | null;
  wb_user_id?: string | null;
  wb_run_id?: string | null;
  wb_run_step?: number | null;
  wb_run_step_end?: number | null;
  raw_span_dump?: string | null;
}

export interface AgentTraceChatRes {
  trace_id: string;
  root_span_name?: string | null;
  agent_name?: string | null;
  agent_version?: string | null;
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  provider?: string | null;
  total_duration_ms?: number | null;
  total_cost_usd?: number | null;
  messages?: AgentChatMessage[];
  feedback?: Record<string, any>[] | null;
}

export interface AgentVersionSchema {
  project_id: string;
  agent_name: string;
  invocation_count: number;
  span_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_duration_ms: number;
  error_count: number;
  first_seen: string | null;
  last_seen: string | null;
  total_cost_usd?: number | null;
  agent_version: string;
}

export interface CallSchema {
  id: string;
  project_id: string;
  op_name: string;
  display_name?: string | null;
  trace_id: string;
  parent_id?: string | null;
  thread_id?: string | null;
  turn_id?: string | null;
  started_at: string;
  attributes: Record<string, any>;
  inputs: Record<string, any>;
  ended_at?: string | null;
  exception?: string | null;
  output?: null;
  summary?: Record<string, any>;
  wb_user_id?: string | null;
  wb_username?: string | null;
  wb_run_id?: string | null;
  wb_run_step?: number | null;
  wb_run_step_end?: number | null;
  deleted_at?: string | null;
  expire_at?: string | null;
  storage_size_bytes?: number | null;
  total_storage_size_bytes?: number | null;
}

export interface CallsFilter {
  op_names?: string[] | null;
  input_refs?: string[] | null;
  output_refs?: string[] | null;
  parent_ids?: string[] | null;
  trace_ids?: string[] | null;
  call_ids?: string[] | null;
  thread_ids?: string[] | null;
  turn_ids?: string[] | null;
  trace_roots_only?: boolean | null;
  wb_user_ids?: string[] | null;
  wb_run_ids?: string[] | null;
}

export interface EndedCallSchemaForInsert {
  project_id: string;
  id: string;
  trace_id?: string | null;
  is_eval?: boolean | null;
  ended_at: string;
  started_at?: string | null;
  exception?: string | null;
  output?: any;
  summary: Record<string, any>;
  wb_run_step_end?: number | null;
}

export interface StartedCallSchemaForInsert {
  project_id: string;
  id?: string | null;
  op_name: string;
  display_name?: string | null;
  trace_id?: string | null;
  parent_id?: string | null;
  thread_id?: string | null;
  turn_id?: string | null;
  started_at: string;
  attributes: Record<string, any>;
  inputs: Record<string, any>;
  otel_dump?: Record<string, any> | null;
  wb_user_id?: string | null;
  wb_run_id?: string | null;
  wb_run_step?: number | null;
}

export interface SortBy {
  field: string;
  direction: 'asc' | 'desc';
}

export interface LiteralOperation {
  $literal:
    | string
    | number
    | boolean
    | Record<string, LiteralOperation>
    | LiteralOperation[]
    | null;
}

export interface GetFieldOperator {
  $getField: string;
}

export interface ConvertSpec {
  input: QueryOperand;
  to: 'double' | 'string' | 'int' | 'bool' | 'exists';
}

export interface ConvertOperation {
  $convert: ConvertSpec;
}

export interface SizeOperation {
  $size: QueryOperand;
}

export interface AndOperation {
  $and: QueryOperand[];
}

export interface OrOperation {
  $or: QueryOperand[];
}

export interface NotOperation {
  $not: any[];
}

export interface EqOperation {
  $eq: any[];
}

export interface GtOperation {
  $gt: any[];
}

export interface LtOperation {
  $lt: any[];
}

export interface GteOperation {
  $gte: any[];
}

export interface LteOperation {
  $lte: any[];
}

export interface InOperation {
  $in: any[];
}

export interface ContainsSpec {
  input: QueryOperand;
  substr: QueryOperand;
  case_insensitive?: boolean | null;
}

export interface ContainsOperation {
  $contains: ContainsSpec;
}

export type QueryOperand =
  | LiteralOperation
  | GetFieldOperator
  | ConvertOperation
  | SizeOperation
  | AndOperation
  | OrOperation
  | NotOperation
  | EqOperation
  | GtOperation
  | LtOperation
  | GteOperation
  | LteOperation
  | InOperation
  | ContainsOperation;

export interface Query {
  $expr:
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | LtOperation
    | GteOperation
    | LteOperation
    | InOperation
    | ContainsOperation;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface HttpResponse<D = unknown, E = unknown> extends Response {
  data: D;
  error: E;
}

export interface CustomRuntimeIDRes {
  id: string;
  max_tokens?: number;
  playground_id: string;
}

export interface CustomRuntimeApplyRes {
  name: string;
  base_url: string;
  api_key_secret: string | null;
  headers: Record<string, string>;
  runtime_ids: CustomRuntimeIDRes[];
}
