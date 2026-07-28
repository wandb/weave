/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/** TraceStatus */
export enum TraceStatus {
  Success = 'success',
  Error = 'error',
  Running = 'running',
  DescendantError = 'descendant_error',
}

/**
 * AggregationType
 * Aggregation functions supported by feedback and call stats metrics.
 */
export enum AggregationType {
  Sum = 'sum',
  Avg = 'avg',
  Min = 'min',
  Max = 'max',
  Count = 'count',
  CountTrue = 'count_true',
  CountFalse = 'count_false',
}

/**
 * AgentChatAgentHandoff
 * Payload for a future agent-to-agent handoff event.
 */
export type AgentChatAgentHandoff = object;

/**
 * AgentChatAgentStart
 * Payload for an agent lifecycle boundary.
 */
export interface AgentChatAgentStart {
  /** Model */
  model?: string | null;
  /** System Instructions */
  system_instructions?: string | null;
  /** Tool Definitions */
  tool_definitions?: string | null;
  /** Status */
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
}

/**
 * AgentChatAssistantMessage
 * Payload for assistant text emitted by an agent or LLM span.
 */
export interface AgentChatAssistantMessage {
  /** Text */
  text: string;
  /** Model */
  model?: string | null;
  /** Reasoning Content */
  reasoning_content?: string | null;
  /** Reasoning Tokens */
  reasoning_tokens?: number | null;
  /** Input Tokens */
  input_tokens?: number | null;
  /** Output Tokens */
  output_tokens?: number | null;
  /** Input Cost Usd */
  input_cost_usd?: number | null;
  /** Output Cost Usd */
  output_cost_usd?: number | null;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Duration Ms */
  duration_ms?: number | null;
  /** Status */
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
  /** Content Refs */
  content_refs?: string[];
}

/**
 * AgentChatContextCompacted
 * Payload for a context-window compaction event.
 */
export interface AgentChatContextCompacted {
  /** Compaction Summary */
  compaction_summary?: string | null;
  /** Compaction Items Before */
  compaction_items_before?: number | null;
  /** Compaction Items After */
  compaction_items_after?: number | null;
}

/**
 * AgentChatMessage
 * A single element in the structured agent trajectory / chat view.
 *
 * Common event fields live at the top level. Type-specific fields are
 * grouped under the payload matching `type`, and exactly one payload must be
 * set. This keeps subtype nullability explicit while preserving a single
 * ordered timeline model for callers.
 */
export interface AgentChatMessage {
  /** Type */
  type:
    | 'user_message'
    | 'assistant_message'
    | 'tool_call'
    | 'agent_handoff'
    | 'agent_start'
    | 'context_compacted';
  /** Span Id */
  span_id?: string | null;
  /** Agent Name */
  agent_name?: string | null;
  /** Agent Version */
  agent_version?: string | null;
  /** Status Code */
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  /** Started At */
  started_at?: string | null;
  user_message?: AgentChatUserMessage | null;
  assistant_message?: AgentChatAssistantMessage | null;
  tool_call?: AgentChatToolCall | null;
  agent_start?: AgentChatAgentStart | null;
  agent_handoff?: AgentChatAgentHandoff | null;
  context_compacted?: AgentChatContextCompacted | null;
  /** Feedback */
  feedback?: Record<string, any>[] | null;
}

/**
 * AgentChatToolCall
 * Payload for a tool call timeline event.
 */
export interface AgentChatToolCall {
  /** Tool Name */
  tool_name?: string | null;
  /** Tool Arguments */
  tool_arguments?: string | null;
  /** Tool Result */
  tool_result?: string | null;
  /** Duration Ms */
  duration_ms?: number | null;
  /** Status */
  status?: 'UNSET' | 'OK' | 'ERROR' | null;
  /** Content Refs */
  content_refs?: string[];
}

/**
 * AgentChatUserMessage
 * Payload for a user prompt in the chat timeline.
 */
export interface AgentChatUserMessage {
  /** Text */
  text: string;
  /** Content Refs */
  content_refs?: string[];
}

/**
 * AgentConversationChatReq
 * Request to get the multi-turn chat view for a conversation.
 */
export interface AgentConversationChatReq {
  /** Project Id */
  project_id: string;
  /** Conversation Id */
  conversation_id: string;
  /**
   * Limit
   * Maximum number of conversation turns to return.
   * @min 0
   * @max 50
   * @default 50
   */
  limit?: number;
  /**
   * Offset
   * Number of most-recent turns to skip. Results are returned in chronological order within the selected page.
   * @min 0
   * @default 0
   */
  offset?: number;
  /**
   * Include Feedback
   * @default false
   */
  include_feedback?: boolean;
}

/**
 * AgentConversationChatRes
 * Multi-turn chat view: an ordered list of per-turn chat responses.
 *
 * Each entry in `turns` corresponds to one trace_id, which Weave treats as
 * one conversation turn. This is not necessarily one `invoke_agent` span:
 * a turn can contain zero, one, or many agent invocations. The frontend can
 * render turn-number dividers between entries and still reuse
 * `AgentTraceChatRes` rendering for each individual turn.
 */
export interface AgentConversationChatRes {
  /** Conversation Id */
  conversation_id: string;
  /** Turns */
  turns?: AgentTraceChatRes[];
  /**
   * Total Turns
   * @default 0
   */
  total_turns?: number;
  /**
   * Has More
   * @default false
   */
  has_more?: boolean;
  /**
   * Limit
   * @default 50
   */
  limit?: number;
  /**
   * Offset
   * @default 0
   */
  offset?: number;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Feedback */
  feedback?: Record<string, any>[] | null;
}

/**
 * AgentConversationMessagePreview
 * A truncated first/last message snippet for a grouped conversation row.
 *
 * `role` is the chat-timeline message type (e.g. "user_message",
 * "assistant_message") so clients can style it consistently with the full
 * chat view; `text` is the trimmed, length-capped preview content.
 */
export interface AgentConversationMessagePreview {
  /** Role */
  role: 'user_message' | 'assistant_message';
  /**
   * Text
   * @default ""
   */
  text?: string;
}

/**
 * AgentConversationSpan
 * One span in a conversation's trace.
 *
 * Returned by `agent_conversation_spans`, which reads span scalar columns
 * only (no message bodies). Spans are ordered by `started_at`, which
 * approximates — but does not exactly match — the detail chat view's
 * parent/child tree-walk order. `operation_name` is the raw OTel value; the
 * client maps it to a display category.
 */
export interface AgentConversationSpan {
  /** Operation Name */
  operation_name: string;
  /** Trace Id */
  trace_id: string;
  /** Span Id */
  span_id: string;
  /** Status */
  status: 'UNSET' | 'OK' | 'ERROR';
  /** Duration Ms */
  duration_ms: number;
}

/**
 * AgentConversationSpanFeedback
 * Tags and ratings applied to a conversation's turn (or the conversation).
 *
 * Positioned client-side by matching `trace_id` (turn) against the spans;
 * `trace_id` is None for conversation-level feedback.
 */
export interface AgentConversationSpanFeedback {
  /**
   * Trace Id
   * The turn this feedback is anchored to; None for conversation-level.
   */
  trace_id: string | null;
  /** Feedback Type */
  feedback_type: 'wandb.agent_user_feedback' | 'wandb.agent_monitor';
  /**
   * Tags
   * Arbitrary descriptive tags applied to this feedback.
   */
  tags?: string[];
  /**
   * Ratings
   * Numeric scorer ratings applied to this feedback.
   */
  ratings?: AgentConversationSpanRating[];
}

/**
 * AgentConversationSpanRating
 * One numeric rating (a scorer score) applied to a turn or conversation.
 */
export interface AgentConversationSpanRating {
  /** Name */
  name: string;
  /** Value */
  value: number;
  /** Reason */
  reason?: string | null;
  /** Confidence */
  confidence?: number | null;
}

/**
 * AgentConversationSpans
 * One conversation's span sequence and its feedback markers.
 */
export interface AgentConversationSpans {
  /** Conversation Id */
  conversation_id: string;
  /** Spans */
  spans?: AgentConversationSpan[];
  /** Spans Feedback */
  spans_feedback?: AgentConversationSpanFeedback[];
}

/**
 * AgentConversationSpansReq
 * Request the span sequences for an explicit set of conversations.
 *
 * Reads span scalar columns only (no message bodies) for the given
 * `conversation_ids`. Powers the conversations-list spans minimap.
 */
export interface AgentConversationSpansReq {
  /** Project Id */
  project_id: string;
  /**
   * Conversation Ids
   * @maxItems 10000
   */
  conversation_ids?: string[];
  /** Started After */
  started_after?: string | null;
  /** Started Before */
  started_before?: string | null;
}

/**
 * AgentConversationSpansRes
 * Span sequences + feedback markers, one entry per requested conversation.
 */
export interface AgentConversationSpansRes {
  /** Conversations */
  conversations?: AgentConversationSpans[];
}

/**
 * AgentCustomAttrSchemaItem
 * One custom attribute key/type observed in the matching spans.
 */
export interface AgentCustomAttrSchemaItem {
  /** Source */
  source:
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  /** Key */
  key: string;
  /** Value Type */
  value_type: 'string' | 'int' | 'float' | 'bool';
  /** Span Count */
  span_count: number;
}

/**
 * AgentCustomAttrsSchemaReq
 * Request to discover typed custom attribute keys for matching spans.
 */
export interface AgentCustomAttrsSchemaReq {
  /** Project Id */
  project_id: string;
  query?: Query | null;
  /** Started After */
  started_after?: string | null;
  /** Started Before */
  started_before?: string | null;
  /**
   * Limit
   * @min 1
   * @max 2000
   * @default 200
   */
  limit?: number;
  /**
   * Offset
   * @min 0
   * @default 0
   */
  offset?: number;
}

/**
 * AgentCustomAttrsSchemaRes
 * Typed custom attribute keys available for spans query/group/stats APIs.
 */
export interface AgentCustomAttrsSchemaRes {
  /** Attributes */
  attributes?: AgentCustomAttrSchemaItem[];
  /**
   * Limit
   * @default 200
   */
  limit?: number;
  /**
   * Offset
   * @default 0
   */
  offset?: number;
  /**
   * Has More
   * @default false
   */
  has_more?: boolean;
}

/**
 * AgentGroupByRef
 * Reference to a field or map-key that spans should be grouped by.
 *
 * `source="field"` targets a semantic span field (`agent.name`) or direct
 * span column (`agent_name`), allowlisted server-side. `source="column"` is
 * accepted for existing callers.
 * The other sources target keys inside the typed custom attribute Map columns,
 * which accept arbitrary user-defined keys.
 */
export interface AgentGroupByRef {
  /**
   * Source
   * @default "field"
   */
  source?:
    | 'field'
    | 'column'
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  /** Key */
  key: string;
  /** Alias */
  alias?: string | null;
}

/**
 * AgentSchema
 * Aggregated per-agent stats from the agents table.
 */
export interface AgentSchema {
  /** Project Id */
  project_id: string;
  /** Agent Name */
  agent_name: string;
  /** Invocation Count */
  invocation_count: number;
  /** Span Count */
  span_count: number;
  /** Total Input Tokens */
  total_input_tokens: number;
  /** Total Output Tokens */
  total_output_tokens: number;
  /** Total Duration Ms */
  total_duration_ms: number;
  /** Error Count */
  error_count: number;
  /** First Seen */
  first_seen: string | null;
  /** Last Seen */
  last_seen: string | null;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
}

/**
 * AgentSearchConversationResult
 * A conversation containing messages that matched the search query.
 */
export interface AgentSearchConversationResult {
  /** Conversation Id */
  conversation_id: string;
  /** Conversation Name */
  conversation_name: string;
  /** Agent Name */
  agent_name: string;
  /** Matched Messages */
  matched_messages: AgentSearchMatchedMessage[];
  /**
   * Last Activity
   * @format date-time
   */
  last_activity: string;
}

/**
 * AgentSearchMatchedMessage
 * A single message that matched the search query.
 */
export interface AgentSearchMatchedMessage {
  /** Span Id */
  span_id: string;
  /** Trace Id */
  trace_id: string;
  /** Role */
  role:
    | ''
    | 'user'
    | 'assistant'
    | 'system'
    | 'tool'
    | 'tool_call'
    | 'tool_result'
    | string;
  /** Content Preview */
  content_preview: string;
  /** Content Digest */
  content_digest: string;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
}

/**
 * AgentSearchReq
 * Query the `messages` table by content and/or span-level filters.
 *
 * Scans the `messages` table (one row per message occurrence, populated by an
 * MV from spans) and returns matching span-level hits. Full-text search sets
 * `query`; structured retrieval (e.g. all messages in a trace) leaves `query`
 * empty and uses the filters below. The caller groups by conversation for the
 * response shape.
 */
export interface AgentSearchReq {
  /** Project Id */
  project_id: string;
  /**
   * Query
   * @default ""
   */
  query?: string;
  /** Trace Id */
  trace_id?: string | null;
  /** Roles */
  roles?:
    | (
        | ''
        | 'user'
        | 'assistant'
        | 'system'
        | 'tool'
        | 'tool_call'
        | 'tool_result'
      )[]
    | null;
  /** Conversation Id */
  conversation_id?: string | null;
  /** Agent Name */
  agent_name?: string | null;
  /** Provider Name */
  provider_name?: string | null;
  /** Request Model */
  request_model?: string | null;
  /**
   * Truncate Content
   * @default true
   */
  truncate_content?: boolean;
  /** Started After */
  started_after?: string | null;
  /** Started Before */
  started_before?: string | null;
  /**
   * Limit
   * @min 0
   * @max 1000
   * @default 20
   */
  limit?: number;
  /**
   * Offset
   * @min 0
   * @default 0
   */
  offset?: number;
}

/**
 * AgentSearchRes
 * Response from a full-text search across agent messages.
 */
export interface AgentSearchRes {
  /** Results */
  results: AgentSearchConversationResult[];
  /**
   * Total Conversations
   * @default 0
   */
  total_conversations?: number;
}

/** AgentSignalFilter */
export interface AgentSignalFilter {
  /** Tags */
  tags?: string[];
  /** Ratings */
  ratings?: RatingCondition[];
}

/**
 * AgentSortBy
 * Sort specification for agent query endpoints.
 */
export interface AgentSortBy {
  /** Field */
  field: string;
  /**
   * Direction
   * @default "desc"
   */
  direction?: 'asc' | 'desc';
}

/**
 * AgentSpanGroupDistributionBin
 * One numeric histogram bin for a custom attribute in a span group.
 */
export interface AgentSpanGroupDistributionBin {
  /** Index */
  index: number;
  /** Min */
  min: number;
  /** Max */
  max: number;
  /** Count */
  count: number;
}

/**
 * AgentSpanGroupDistributionItem
 * Distribution data for one span-group/custom-attribute pair.
 */
export interface AgentSpanGroupDistributionItem {
  /** Alias */
  alias: string;
  /** Source */
  source:
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  /** Key */
  key: string;
  /** Value Type */
  value_type: 'string' | 'int' | 'float' | 'bool';
  /**
   * Total Count
   * @default 0
   */
  total_count?: number;
  /**
   * Present Count
   * @default 0
   */
  present_count?: number;
  /**
   * Missing Count
   * @default 0
   */
  missing_count?: number;
  /**
   * Other Count
   * @default 0
   */
  other_count?: number;
  /** Bins */
  bins?: AgentSpanGroupDistributionBin[];
  /** Values */
  values?: AgentSpanGroupDistributionValue[];
}

/**
 * AgentSpanGroupDistributionSpec
 * One custom attribute distribution to compute per returned span group.
 */
export interface AgentSpanGroupDistributionSpec {
  /**
   * Alias
   * @pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
   */
  alias: string;
  /** Reference to a span field or typed custom attribute map value. */
  value: AgentSpanValueRef;
  /**
   * Bins
   * @min 1
   * @max 50
   * @default 12
   */
  bins?: number;
  /**
   * Top N
   * @min 1
   * @max 20
   * @default 5
   */
  top_n?: number;
}

/**
 * AgentSpanGroupDistributionValue
 * One categorical custom attribute value count in a span group.
 */
export interface AgentSpanGroupDistributionValue {
  /** Value */
  value: string;
  /** Count */
  count: number;
}

/**
 * AgentSpanGroupFilter
 * Range filter over one grouped span measure.
 */
export interface AgentSpanGroupFilter {
  /** Group By */
  group_by?: AgentGroupByRef[];
  /** One aggregate measure computed over spans in a group or bucket. */
  measure: AgentSpanMeasureSpec;
  /** Min */
  min?: number | string | null;
  /** Max */
  max?: number | string | null;
}

/**
 * AgentSpanGroupRow
 * A single row in a grouped spans query response.
 *
 * `group_keys` maps each group_by ref's alias to its value for this row.
 * The remaining fields are a fixed aggregate bundle computed per group.
 */
export interface AgentSpanGroupRow {
  /** Group Keys */
  group_keys?: Record<string, string | number | boolean | null>;
  /**
   * Span Count
   * @default 0
   */
  span_count?: number;
  /**
   * Invocation Count
   * @default 0
   */
  invocation_count?: number;
  /**
   * Conversation Count
   * @default 0
   */
  conversation_count?: number;
  /**
   * Total Input Tokens
   * @default 0
   */
  total_input_tokens?: number;
  /**
   * Total Cache Creation Input Tokens
   * @default 0
   */
  total_cache_creation_input_tokens?: number;
  /**
   * Total Cache Read Input Tokens
   * @default 0
   */
  total_cache_read_input_tokens?: number;
  /**
   * Total Output Tokens
   * @default 0
   */
  total_output_tokens?: number;
  /**
   * Total Reasoning Tokens
   * @default 0
   */
  total_reasoning_tokens?: number;
  /**
   * Total Duration Ms
   * @default 0
   */
  total_duration_ms?: number;
  /**
   * Error Count
   * @default 0
   */
  error_count?: number;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Total Input Cost Usd */
  total_input_cost_usd?: number | null;
  /** Total Output Cost Usd */
  total_output_cost_usd?: number | null;
  /** Agent Names */
  agent_names?: string[];
  /** Agent Versions */
  agent_versions?: string[];
  /** Provider Names */
  provider_names?: string[];
  /** Request Models */
  request_models?: string[];
  /** Conversation Names */
  conversation_names?: string[];
  /** First Seen */
  first_seen?: string | null;
  /** Last Seen */
  last_seen?: string | null;
  first_message?: AgentConversationMessagePreview | null;
  last_message?: AgentConversationMessagePreview | null;
  /** Metrics */
  metrics?: Record<string, string | number | boolean | null>;
  /** Distributions */
  distributions?: Record<string, AgentSpanGroupDistributionItem>;
}

/**
 * AgentSpanMeasureSpec
 * One aggregate measure computed over spans in a group or bucket.
 */
export interface AgentSpanMeasureSpec {
  /**
   * Alias
   * @pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
   */
  alias: string;
  /** Aggregation */
  aggregation:
    | 'sum'
    | 'avg'
    | 'min'
    | 'max'
    | 'count'
    | 'count_distinct'
    | 'count_true'
    | 'count_false';
  value?: AgentSpanValueRef | null;
  /** Value Type */
  value_type?: 'datetime' | 'number' | 'boolean' | 'string' | null;
  filter?: Query | null;
}

/**
 * AgentSpanSchema
 * A normalized agent span returned by query APIs.
 */
export interface AgentSpanSchema {
  /** Project Id */
  project_id: string;
  /** Trace Id */
  trace_id: string;
  /** Span Id */
  span_id: string;
  /** Parent Span Id */
  parent_span_id?: string | null;
  /** Span Name */
  span_name?: string | null;
  /** Span Kind */
  span_kind?:
    | 'UNSPECIFIED'
    | 'INTERNAL'
    | 'SERVER'
    | 'CLIENT'
    | 'PRODUCER'
    | 'CONSUMER'
    | null;
  /** Started At */
  started_at?: string | null;
  /** Ended At */
  ended_at?: string | null;
  /** Status Code */
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  /** Status Message */
  status_message?: string | null;
  /** Operation Name */
  operation_name?: string | null;
  /** Provider Name */
  provider_name?: string | null;
  /** Agent Name */
  agent_name?: string | null;
  /** Agent Id */
  agent_id?: string | null;
  /** Agent Description */
  agent_description?: string | null;
  /** Agent Version */
  agent_version?: string | null;
  /** Eval Run Id */
  eval_run_id?: string | null;
  /** Eval Predict And Score Call Id */
  eval_predict_and_score_call_id?: string | null;
  /** Eval Kind */
  eval_kind?: string | null;
  /** Eval Row Digest */
  eval_row_digest?: string | null;
  /** Eval Example Id */
  eval_example_id?: string | null;
  /** Eval Trial Index */
  eval_trial_index?: number | null;
  /** Eval Evaluation Name */
  eval_evaluation_name?: string | null;
  /** Request Model */
  request_model?: string | null;
  /** Response Model */
  response_model?: string | null;
  /** Response Id */
  response_id?: string | null;
  /** Input Tokens */
  input_tokens?: number | null;
  /** Output Tokens */
  output_tokens?: number | null;
  /** Reasoning Tokens */
  reasoning_tokens?: number | null;
  /** Cache Creation Input Tokens */
  cache_creation_input_tokens?: number | null;
  /** Cache Read Input Tokens */
  cache_read_input_tokens?: number | null;
  /** Input Cost Usd */
  input_cost_usd?: number | null;
  /** Output Cost Usd */
  output_cost_usd?: number | null;
  /** Cache Read Cost Usd */
  cache_read_cost_usd?: number | null;
  /** Cache Creation Cost Usd */
  cache_creation_cost_usd?: number | null;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Reasoning Content */
  reasoning_content?: string | null;
  /** Conversation Id */
  conversation_id?: string | null;
  /** Conversation Name */
  conversation_name?: string | null;
  /** Tool Name */
  tool_name?: string | null;
  /** Tool Type */
  tool_type?: string | null;
  /** Tool Call Id */
  tool_call_id?: string | null;
  /** Tool Description */
  tool_description?: string | null;
  /** Tool Definitions */
  tool_definitions?: string | null;
  /** Finish Reasons */
  finish_reasons?: string[];
  /** Error Type */
  error_type?: string | null;
  /** Request Temperature */
  request_temperature?: number | null;
  /** Request Max Tokens */
  request_max_tokens?: number | null;
  /** Request Top P */
  request_top_p?: number | null;
  /** Request Frequency Penalty */
  request_frequency_penalty?: number | null;
  /** Request Presence Penalty */
  request_presence_penalty?: number | null;
  /** Request Seed */
  request_seed?: number | null;
  /** Request Stop Sequences */
  request_stop_sequences?: string[];
  /** Request Choice Count */
  request_choice_count?: number | null;
  /** Output Type */
  output_type?: string | null;
  /** Input Messages */
  input_messages?: NormalizedMessage[];
  /** Output Messages */
  output_messages?: NormalizedMessage[];
  /** System Instructions */
  system_instructions?: string[];
  /** Tool Call Arguments */
  tool_call_arguments?: string | null;
  /** Tool Call Result */
  tool_call_result?: string | null;
  /** Compaction Summary */
  compaction_summary?: string | null;
  /** Compaction Items Before */
  compaction_items_before?: number | null;
  /** Compaction Items After */
  compaction_items_after?: number | null;
  /** Content Refs */
  content_refs?: string[];
  /** Artifact Refs */
  artifact_refs?: string[];
  /** Object Refs */
  object_refs?: string[];
  /** Custom Attrs String */
  custom_attrs_string?: Record<string, string>;
  /** Custom Attrs Int */
  custom_attrs_int?: Record<string, number>;
  /** Custom Attrs Float */
  custom_attrs_float?: Record<string, number>;
  /** Custom Attrs Bool */
  custom_attrs_bool?: Record<string, boolean>;
  /** Server Address */
  server_address?: string | null;
  /** Server Port */
  server_port?: number | null;
  /** Wb User Id */
  wb_user_id?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
  /** Wb Run Step */
  wb_run_step?: number | null;
  /** Wb Run Step End */
  wb_run_step_end?: number | null;
  /** Raw Span Dump */
  raw_span_dump?: string | null;
}

/**
 * AgentSpanStatsColumn
 * Metadata describing one column in an agent span stats result row.
 */
export interface AgentSpanStatsColumn {
  /** Name */
  name: string;
  /** Role */
  role: 'time' | 'bucket' | 'group' | 'metric';
  /** Value Type */
  value_type: 'datetime' | 'number' | 'boolean' | 'string';
  /** Metric */
  metric?: string | null;
  /** Aggregation */
  aggregation?: string | null;
}

/**
 * AgentSpanStatsMetricSpec
 * Metric to extract from each matching span and aggregate into chart rows.
 */
export interface AgentSpanStatsMetricSpec {
  /**
   * Alias
   * @pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
   */
  alias: string;
  /** Value Type */
  value_type: 'datetime' | 'number' | 'boolean' | 'string';
  /** Aggregations */
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
  /** Percentiles */
  percentiles?: number[];
  /** Reference to a span field or typed custom attribute map value. */
  value: AgentSpanValueRef;
}

/**
 * AgentSpanStatsNumericBucketSpec
 * Bucket stats rows by ranges of one numeric span or grouped value.
 */
export interface AgentSpanStatsNumericBucketSpec {
  /**
   * Type
   * @default "number"
   */
  type?: 'number';
  /**
   * Alias
   * @default "value"
   * @pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
   */
  alias?: string;
  /**
   * Bins
   * @min 1
   * @max 200
   * @default 24
   */
  bins?: number;
  /** Min */
  min?: number | null;
  /** Max */
  max?: number | null;
  value?: AgentSpanValueRef | null;
  /** Group By */
  group_by?: AgentGroupByRef[];
  measure?: AgentSpanMeasureSpec | null;
}

/**
 * AgentSpanStatsReq
 * Request chart-ready aggregations over GenAI agent spans.
 */
export interface AgentSpanStatsReq {
  /** Project Id */
  project_id: string;
  query?: Query | null;
  /**
   * Start
   * @format date-time
   */
  start: string;
  /** End */
  end?: string | null;
  /** Granularity */
  granularity?: number | null;
  /**
   * Timezone
   * @default "UTC"
   */
  timezone?: string;
  /** Group By */
  group_by?: AgentGroupByRef[];
  /** Metrics */
  metrics?: AgentSpanStatsMetricSpec[];
  /**
   * Group Limit
   * @min 1
   * @max 1000
   * @default 50
   */
  group_limit?: number;
  /** Bucket By */
  bucket_by?:
    | (
        | ({
            type: 'number';
          } & AgentSpanStatsNumericBucketSpec)
        | ({
            type: 'time';
          } & AgentSpanStatsTimeBucketSpec)
      )
    | null;
  /** Group Filters */
  group_filters?: AgentSpanGroupFilter[];
  signal_filters?: AgentSignalFilter | null;
}

/**
 * AgentSpanStatsRes
 * Response containing chart-ready agent span stats rows.
 */
export interface AgentSpanStatsRes {
  /**
   * Start
   * @format date-time
   */
  start: string;
  /**
   * End
   * @format date-time
   */
  end: string;
  /** Granularity */
  granularity?: number | null;
  /** Timezone */
  timezone: string;
  /**
   * Bucket Type
   * @default "time"
   */
  bucket_type?: 'time' | 'number';
  /** Columns */
  columns?: AgentSpanStatsColumn[];
  /** Rows */
  rows?: Record<string, string | number | boolean | null>[];
}

/**
 * AgentSpanStatsTimeBucketSpec
 * Bucket stats rows by started_at time intervals.
 */
export interface AgentSpanStatsTimeBucketSpec {
  /**
   * Type
   * @default "time"
   */
  type?: 'time';
}

/**
 * AgentSpanValueRef
 * Reference to a span field or typed custom attribute map value.
 */
export interface AgentSpanValueRef {
  /**
   * Source
   * @default "field"
   */
  source?:
    | 'field'
    | 'derived'
    | 'custom_attrs_string'
    | 'custom_attrs_int'
    | 'custom_attrs_float'
    | 'custom_attrs_bool';
  /** Key */
  key: string;
}

/**
 * AgentSpansQueryReq
 * Request to query agent spans for a project.
 *
 * When `group_by` is empty (or omitted), returns raw span rows in the
 * response's `spans` field. When `group_by` is non-empty, returns
 * aggregate group rows in the response's `groups` field.
 */
export interface AgentSpansQueryReq {
  /** Project Id */
  project_id: string;
  query?: Query | null;
  /** Group By */
  group_by?: AgentGroupByRef[] | null;
  /** Measures */
  measures?: AgentSpanMeasureSpec[];
  /** Group Filters */
  group_filters?: AgentSpanGroupFilter[];
  /**
   * Group Distributions
   * @maxItems 20
   */
  group_distributions?: AgentSpanGroupDistributionSpec[];
  /** Custom Attr Columns */
  custom_attr_columns?: AgentSpanValueRef[];
  /**
   * Include Details
   * @default false
   */
  include_details?: boolean;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean;
  /** Sort By */
  sort_by?: AgentSortBy[] | null;
  /**
   * Limit
   * @min 0
   * @max 10000
   * @default 100
   */
  limit?: number;
  /**
   * Offset
   * @min 0
   * @default 0
   */
  offset?: number;
  /** Started After */
  started_after?: string | null;
  /** Started Before */
  started_before?: string | null;
  signal_filters?: AgentSignalFilter | null;
}

/**
 * AgentSpansQueryRes
 * Response from a spans query.
 *
 * Exactly one of `spans` or `groups` will be populated, based on
 * whether the request specified `group_by`.
 */
export interface AgentSpansQueryRes {
  /** Spans */
  spans?: AgentSpanSchema[];
  /** Groups */
  groups?: AgentSpanGroupRow[];
  /**
   * Total Count
   * @default 0
   */
  total_count?: number;
}

/**
 * AgentTraceChatReq
 * Request to get the structured chat / trajectory view for a trace.
 */
export interface AgentTraceChatReq {
  /** Project Id */
  project_id: string;
  /** Trace Id */
  trace_id: string;
  /**
   * Include Feedback
   * @default false
   */
  include_feedback?: boolean;
}

/**
 * AgentTraceChatRes
 * Structured chat view: a linear sequence of messages representing
 * the agent trajectory for a single trace.
 */
export interface AgentTraceChatRes {
  /** Trace Id */
  trace_id: string;
  /** Root Span Name */
  root_span_name?: string | null;
  /** Agent Name */
  agent_name?: string | null;
  /** Agent Version */
  agent_version?: string | null;
  /** Status Code */
  status_code?: 'UNSET' | 'OK' | 'ERROR' | null;
  /** Provider */
  provider?: string | null;
  /**
   * Total Duration Ms
   * Wall-clock duration of the trace root span in milliseconds. This is not a sum of child span durations.
   */
  total_duration_ms?: number | null;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Messages */
  messages?: AgentChatMessage[];
  /** Feedback */
  feedback?: Record<string, any>[] | null;
}

/**
 * AgentVersionSchema
 * Aggregated per-version stats from the agent_versions AMT.
 */
export interface AgentVersionSchema {
  /** Project Id */
  project_id: string;
  /** Agent Name */
  agent_name: string;
  /** Invocation Count */
  invocation_count: number;
  /** Span Count */
  span_count: number;
  /** Total Input Tokens */
  total_input_tokens: number;
  /** Total Output Tokens */
  total_output_tokens: number;
  /** Total Duration Ms */
  total_duration_ms: number;
  /** Error Count */
  error_count: number;
  /** First Seen */
  first_seen: string | null;
  /** Last Seen */
  last_seen: string | null;
  /** Total Cost Usd */
  total_cost_usd?: number | null;
  /** Agent Version */
  agent_version: string;
}

/**
 * AgentVersionsQueryReq
 * Request to list versions for an agent.
 */
export interface AgentVersionsQueryReq {
  /** Project Id */
  project_id: string;
  /** Agent Name */
  agent_name: string;
  /** Sort By */
  sort_by?: AgentSortBy[] | null;
  /**
   * Limit
   * @min 0
   * @max 10000
   * @default 100
   */
  limit?: number;
  /**
   * Offset
   * @min 0
   * @default 0
   */
  offset?: number;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean;
}

/**
 * AgentVersionsQueryRes
 * Response containing agent version stats.
 */
export interface AgentVersionsQueryRes {
  /** Versions */
  versions: AgentVersionSchema[];
  /**
   * Total Count
   * @default 0
   */
  total_count?: number;
}

/**
 * AgentsQueryFilters
 * Optional filters for querying agents.
 */
export interface AgentsQueryFilters {
  /** Agent Name */
  agent_name?: string | null;
}

/**
 * AgentsQueryReq
 * Request to list agents with aggregated stats for a project.
 */
export interface AgentsQueryReq {
  /** Project Id */
  project_id: string;
  filters?: AgentsQueryFilters | null;
  /** Sort By */
  sort_by?: AgentSortBy[] | null;
  /**
   * Limit
   * @min 0
   * @max 10000
   * @default 100
   */
  limit?: number;
  /**
   * Offset
   * @min 0
   * @default 0
   */
  offset?: number;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean;
}

/**
 * AgentsQueryRes
 * Response containing aggregated agent stats.
 */
export interface AgentsQueryRes {
  /** Agents */
  agents: AgentSchema[];
  /**
   * Total Count
   * @default 0
   */
  total_count?: number;
}

/** AliasesListRes */
export interface AliasesListRes {
  /** Aliases */
  aliases: string[];
}

/**
 * AndOperation
 * Logical AND. All conditions must evaluate to true.
 *
 * Example:
 *     ```
 *     {
 *         "$and": [
 *             {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]},
 *             {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]}
 *         ]
 *     }
 *     ```
 */
export interface AndOperation {
  /** $And */
  $and: (
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
    | ContainsOperation
  )[];
}

/**
 * AnnotationQueueAddCallsBody
 * Request body for adding calls to an annotation queue (queue_id comes from path).
 */
export interface AnnotationQueueAddCallsBody {
  /** Project Id */
  project_id: string;
  /** Call Ids */
  call_ids: string[];
  /**
   * Display Fields
   * JSON paths to display to annotators
   */
  display_fields: string[];
}

/**
 * AnnotationQueueAddCallsRes
 * Response from adding calls to a queue.
 */
export interface AnnotationQueueAddCallsRes {
  /** Added Count */
  added_count: number;
  /** Duplicates */
  duplicates: number;
}

/**
 * AnnotationQueueCreateReq
 * Request to create a new annotation queue.
 */
export interface AnnotationQueueCreateReq {
  /** Project Id */
  project_id: string;
  /** Name */
  name: string;
  /**
   * Description
   * @default ""
   */
  description?: string;
  /** Scorer Refs */
  scorer_refs: string[];
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/**
 * AnnotationQueueCreateRes
 * Response from creating an annotation queue.
 */
export interface AnnotationQueueCreateRes {
  /** Id */
  id: string;
}

/**
 * AnnotationQueueDeleteRes
 * Response from deleting an annotation queue.
 */
export interface AnnotationQueueDeleteRes {
  /** Schema for annotation queue responses. */
  queue: AnnotationQueueSchema;
}

/**
 * AnnotationQueueItemProgressUpdateBody
 * Request body for updating annotation progress (queue_id and item_id come from path).
 *
 * Note: wb_user_id is not included in the body - it's set server-side from the authenticated session.
 */
export interface AnnotationQueueItemProgressUpdateBody {
  /** Project Id */
  project_id: string;
  /**
   * Annotation State
   * New state: 'in_progress', 'completed', or 'skipped'
   */
  annotation_state: string;
}

/**
 * AnnotationQueueItemSchema
 * Schema for annotation queue item responses.
 */
export interface AnnotationQueueItemSchema {
  /** Id */
  id: string;
  /** Project Id */
  project_id: string;
  /** Queue Id */
  queue_id: string;
  /** Call Id */
  call_id: string;
  /**
   * Call Started At
   * @format date-time
   */
  call_started_at: string;
  /** Call Ended At */
  call_ended_at?: string | null;
  /** Call Op Name */
  call_op_name: string;
  /** Call Trace Id */
  call_trace_id: string;
  /** Display Fields */
  display_fields: string[];
  /** Added By */
  added_by?: string | null;
  /** Annotation State */
  annotation_state: 'unstarted' | 'in_progress' | 'completed' | 'skipped';
  /** Annotator User Id */
  annotator_user_id?: string | null;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Created By */
  created_by: string;
  /**
   * Updated At
   * @format date-time
   */
  updated_at: string;
  /** Deleted At */
  deleted_at?: string | null;
  /** Position In Queue */
  position_in_queue?: number | null;
}

/**
 * AnnotationQueueItemsFilter
 * Simple filter for annotation queue items.
 *
 * Supports equality filtering on call metadata fields and IN filtering on annotation state.
 */
export interface AnnotationQueueItemsFilter {
  /**
   * Id
   * Filter by exact queue item ID
   */
  id?: string | null;
  /**
   * Call Id
   * Filter by exact call ID
   */
  call_id?: string | null;
  /**
   * Call Op Name
   * Filter by exact operation name
   */
  call_op_name?: string | null;
  /**
   * Call Trace Id
   * Filter by exact trace ID
   */
  call_trace_id?: string | null;
  /**
   * Added By
   * Filter by W&B user ID who added the call
   */
  added_by?: string | null;
  /**
   * Annotation States
   * Filter by annotation states (unstarted, in_progress, completed, skipped)
   */
  annotation_states?:
    | ('unstarted' | 'in_progress' | 'completed' | 'skipped')[]
    | null;
}

/**
 * AnnotationQueueItemsQueryBody
 * Request body for querying items in an annotation queue (queue_id comes from path).
 */
export interface AnnotationQueueItemsQueryBody {
  /** Project Id */
  project_id: string;
  /** Filter queue items by call metadata and annotation state */
  filter?: AnnotationQueueItemsFilter | null;
  /**
   * Sort By
   * Sort by multiple fields (e.g., created_at, updated_at)
   */
  sort_by?: SortBy[] | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
  /**
   * Include Position
   * Include position_in_queue field (1-based index in full queue)
   * @default false
   */
  include_position?: boolean;
}

/**
 * AnnotationQueueItemsQueryRes
 * Response from querying annotation queue items.
 */
export interface AnnotationQueueItemsQueryRes {
  /** Items */
  items: AnnotationQueueItemSchema[];
}

/**
 * AnnotationQueueReadRes
 * Response from reading an annotation queue.
 */
export interface AnnotationQueueReadRes {
  /** Schema for annotation queue responses. */
  queue: AnnotationQueueSchema;
}

/**
 * AnnotationQueueSchema
 * Schema for annotation queue responses.
 */
export interface AnnotationQueueSchema {
  /** Id */
  id: string;
  /** Project Id */
  project_id: string;
  /** Name */
  name: string;
  /** Description */
  description: string;
  /** Scorer Refs */
  scorer_refs: string[];
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Created By */
  created_by: string;
  /**
   * Updated At
   * @format date-time
   */
  updated_at: string;
  /** Deleted At */
  deleted_at?: string | null;
}

/**
 * AnnotationQueueStatsSchema
 * Statistics for a single annotation queue.
 */
export interface AnnotationQueueStatsSchema {
  /**
   * Queue Id
   * The queue ID
   */
  queue_id: string;
  /**
   * Total Items
   * Total number of items in the queue
   */
  total_items: number;
  /**
   * Completed Items
   * Number of items completed or skipped by at least one annotator
   */
  completed_items: number;
}

/**
 * AnnotationQueueUpdateBody
 * Request body for updating an annotation queue (queue_id comes from path).
 *
 * All fields except project_id are optional - only provided fields will be updated.
 */
export interface AnnotationQueueUpdateBody {
  /** Project Id */
  project_id: string;
  /** Name */
  name?: string | null;
  /** Description */
  description?: string | null;
  /** Scorer Refs */
  scorer_refs?: string[] | null;
}

/**
 * AnnotationQueueUpdateRes
 * Response from updating an annotation queue.
 */
export interface AnnotationQueueUpdateRes {
  /** Schema for annotation queue responses. */
  queue: AnnotationQueueSchema;
}

/**
 * AnnotationQueuesQueryReq
 * Request to query annotation queues for a project.
 */
export interface AnnotationQueuesQueryReq {
  /** Project Id */
  project_id: string;
  /**
   * Name
   * Filter by queue name (case-insensitive partial match)
   */
  name?: string | null;
  /**
   * Sort By
   * Sort by multiple fields (e.g., created_at, updated_at, name)
   */
  sort_by?: SortBy[] | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
}

/**
 * AnnotationQueuesStatsReq
 * Request to get stats for multiple annotation queues.
 */
export interface AnnotationQueuesStatsReq {
  /** Project Id */
  project_id: string;
  /**
   * Queue Ids
   * List of queue IDs to get stats for
   */
  queue_ids: string[];
}

/**
 * AnnotationQueuesStatsRes
 * Response with stats for multiple annotation queues.
 */
export interface AnnotationQueuesStatsRes {
  /** Stats */
  stats: AnnotationQueueStatsSchema[];
}

/**
 * AnnotatorQueueItemsProgressUpdateRes
 * Response from updating annotation state.
 */
export interface AnnotatorQueueItemsProgressUpdateRes {
  /** Schema for annotation queue item responses. */
  item: AnnotationQueueItemSchema;
}

/** Body_file_create_file_create_post */
export interface BodyFileCreateFileCreatePost {
  /** Project Id */
  project_id: string;
  /**
   * File
   * @format binary
   */
  file: File;
  /** Expected Digest */
  expected_digest?: string | null;
}

/** CallBatchEndMode */
export interface CallBatchEndMode {
  /**
   * Mode
   * @default "end"
   */
  mode?: string;
  req: CallEndReq;
}

/** CallBatchStartMode */
export interface CallBatchStartMode {
  /**
   * Mode
   * @default "start"
   */
  mode?: string;
  req: CallStartReq;
}

/** CallCreateBatchReq */
export interface CallCreateBatchReq {
  /** Batch */
  batch: (CallBatchStartMode | CallBatchEndMode)[];
}

/** CallCreateBatchRes */
export interface CallCreateBatchRes {
  /** Res */
  res: (CallStartRes | CallEndRes)[];
}

/** CallEndReq */
export interface CallEndReq {
  end: EndedCallSchemaForInsert;
}

/** CallEndRes */
export type CallEndRes = object;

/**
 * CallMetricSpec
 * Specification for a call-level metric to aggregate (not grouped by model).
 */
export interface CallMetricSpec {
  /**
   * Metric
   * Metric to aggregate.
   */
  metric: 'latency_ms' | 'call_count' | 'error_count';
  /**
   * Aggregations
   * Basic aggregation functions to apply
   * @default ["sum"]
   */
  aggregations?: AggregationType[];
  /**
   * Percentiles
   * Percentile values to compute (0-100). E.g., [50, 95, 99] for p50, p95, p99
   * @default []
   */
  percentiles?: number[];
}

/** CallReadReq */
export interface CallReadReq {
  /** Project Id */
  project_id: string;
  /** Id */
  id: string;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean | null;
  /**
   * Include Storage Size
   * @default false
   */
  include_storage_size?: boolean | null;
  /**
   * Include Total Storage Size
   * @default false
   */
  include_total_storage_size?: boolean | null;
}

/** CallReadRes */
export interface CallReadRes {
  call: CallSchema | null;
}

/** CallSchema */
export interface CallSchema {
  /** Id */
  id: string;
  /** Project Id */
  project_id: string;
  /** Op Name */
  op_name: string;
  /** Display Name */
  display_name?: string | null;
  /** Trace Id */
  trace_id: string;
  /** Parent Id */
  parent_id?: string | null;
  /** Thread Id */
  thread_id?: string | null;
  /** Turn Id */
  turn_id?: string | null;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
  /** Attributes */
  attributes: Record<string, any>;
  /** Inputs */
  inputs: Record<string, any>;
  /** Ended At */
  ended_at?: string | null;
  /** Exception */
  exception?: string | null;
  /** Output */
  output?: null;
  summary?: Record<string, any>;
  /** Wb User Id */
  wb_user_id?: string | null;
  /** Wb Username */
  wb_username?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
  /** Wb Run Step */
  wb_run_step?: number | null;
  /** Wb Run Step End */
  wb_run_step_end?: number | null;
  /** Deleted At */
  deleted_at?: string | null;
  /**
   * Expire At
   * Expiration timestamp for this call. None = no TTL configured for the project (the row will not be expired).
   */
  expire_at?: string | null;
  /** Storage Size Bytes */
  storage_size_bytes?: number | null;
  /** Total Storage Size Bytes */
  total_storage_size_bytes?: number | null;
}

/** CallStartReq */
export interface CallStartReq {
  start: StartedCallSchemaForInsert;
}

/** CallStartRes */
export interface CallStartRes {
  /** Id */
  id: string;
  /** Trace Id */
  trace_id: string;
}

/**
 * CallStatsReq
 * Request for aggregated call statistics over a time range.
 */
export interface CallStatsReq {
  /** Project Id */
  project_id: string;
  /**
   * Start
   * Inclusive start time (UTC, ISO 8601).
   * @format date-time
   */
  start: string;
  /**
   * End
   * Exclusive end time (UTC, ISO 8601). Defaults to now if omitted.
   */
  end?: string | null;
  /**
   * Granularity
   * Bucket size in seconds (e.g., 3600 for 1 hour). If omitted, auto-selected based on time range. Will be adjusted if it would produce more than 10,000 buckets.
   */
  granularity?: number | null;
  /**
   * Usage Metrics
   * Usage metrics (tokens, cost) to compute. Grouped by timestamp and model.
   */
  usage_metrics?: UsageMetricSpec[] | null;
  /**
   * Call Metrics
   * Call-level metrics (latency, counts) to compute. Grouped by timestamp only.
   */
  call_metrics?: CallMetricSpec[] | null;
  filter?: CallsFilter | null;
  /**
   * Timezone
   * IANA timezone for bucket alignment (e.g., 'America/New_York')
   * @default "UTC"
   */
  timezone?: string;
}

/**
 * CallStatsRes
 * Response containing time-series call statistics.
 */
export interface CallStatsRes {
  /**
   * Start
   * Resolved start time (UTC)
   * @format date-time
   */
  start: string;
  /**
   * End
   * Resolved end time (UTC)
   * @format date-time
   */
  end: string;
  /**
   * Granularity
   * Bucket size used (in seconds)
   */
  granularity: number;
  /**
   * Timezone
   * Timezone used for bucket alignment
   */
  timezone: string;
  /**
   * Usage Buckets
   * Usage metrics by model. Each bucket contains 'timestamp', 'model', and aggregated metric values.
   * @default []
   */
  usage_buckets?: Record<string, any>[];
  /**
   * Call Buckets
   * Call-level metrics. Each bucket contains 'timestamp' and aggregated metric values.
   * @default []
   */
  call_buckets?: Record<string, any>[];
}

/** CallUpdateReq */
export interface CallUpdateReq {
  /** Project Id */
  project_id: string;
  /** Call Id */
  call_id: string;
  /** Display Name */
  display_name?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** CallUpdateRes */
export type CallUpdateRes = object;

/** CallsDeleteReq */
export interface CallsDeleteReq {
  /** Project Id */
  project_id: string;
  /** Call Ids */
  call_ids: string[];
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** CallsDeleteRes */
export interface CallsDeleteRes {
  /**
   * Num Deleted
   * The number of calls deleted
   */
  num_deleted: number;
}

/** CallsFilter */
export interface CallsFilter {
  /** Op Names */
  op_names?: string[] | null;
  /** Input Refs */
  input_refs?: string[] | null;
  /** Output Refs */
  output_refs?: string[] | null;
  /** Parent Ids */
  parent_ids?: string[] | null;
  /** Trace Ids */
  trace_ids?: string[] | null;
  /** Call Ids */
  call_ids?: string[] | null;
  /** Thread Ids */
  thread_ids?: string[] | null;
  /** Turn Ids */
  turn_ids?: string[] | null;
  /** Trace Roots Only */
  trace_roots_only?: boolean | null;
  /** Wb User Ids */
  wb_user_ids?: string[] | null;
  /** Wb Run Ids */
  wb_run_ids?: string[] | null;
}

/** CallsQueryReq */
export interface CallsQueryReq {
  /** Project Id */
  project_id: string;
  filter?: CallsFilter | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
  /** Sort By */
  sort_by?: SortBy[] | null;
  query?: Query | null;
  /**
   * Include Costs
   * Beta, subject to change. If true, the response will include any model costs for each call.
   * @default false
   */
  include_costs?: boolean | null;
  /**
   * Include Feedback
   * Beta, subject to change. If true, the response will include feedback for each call.
   * @default false
   */
  include_feedback?: boolean | null;
  /**
   * Include Storage Size
   * Beta, subject to change. If true, the response will include the storage size for a call.
   * @default false
   */
  include_storage_size?: boolean | null;
  /**
   * Include Total Storage Size
   * Beta, subject to change. If true, the response will include the total storage size for a trace.
   * @default false
   */
  include_total_storage_size?: boolean | null;
  /**
   * Include Usernames
   * If true, the response will attempt to resolve each call's wb_user_id to a username for the duration of this request.
   * @default false
   */
  include_usernames?: boolean | null;
  /** Columns */
  columns?: string[] | null;
  /**
   * Expand Columns
   * Columns to expand, i.e. refs to other objects
   */
  expand_columns?: string[] | null;
  /**
   * Return Expanded Column Values
   * If true, the response will include raw values for expanded columns. If false, the response expand_columns will only be used for filtering and ordering. This is useful for clients that want to resolve refs themselves, e.g. for performance reasons.
   * @default true
   */
  return_expanded_column_values?: boolean | null;
}

/** CallsQueryStatsReq */
export interface CallsQueryStatsReq {
  /** Project Id */
  project_id: string;
  filter?: CallsFilter | null;
  query?: Query | null;
  /** Limit */
  limit?: number | null;
  /**
   * Include Total Storage Size
   * @default false
   */
  include_total_storage_size?: boolean | null;
  /**
   * Expand Columns
   * Columns with refs to objects or table rows that require expansion during filtering or ordering.
   */
  expand_columns?: string[] | null;
}

/** CallsQueryStatsRes */
export interface CallsQueryStatsRes {
  /** Count */
  count: number;
  /**
   * Has More
   * @default false
   */
  has_more?: boolean;
  /** Total Storage Size Bytes */
  total_storage_size_bytes?: number | null;
}

/**
 * CallsScoreReq
 * Request to enqueue scoring jobs for a list of calls.
 *
 * Scoring is performed asynchronously by the call_scoring_worker, which
 * consumes messages from Kafka and applies each scorer_ref to each call_id.
 */
export interface CallsScoreReq {
  /** Project Id */
  project_id: string;
  /**
   * Call Ids
   * List of call IDs to score
   */
  call_ids: string[];
  /**
   * Scorer Refs
   * List of scorer refs to apply
   */
  scorer_refs: string[];
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/**
 * CallsScoreRes
 * Empty response for calls_score.
 *
 * Defined as a model (rather than returning None) to follow the convention
 * used throughout this interface and to allow fields to be added later
 * without a breaking change.
 */
export type CallsScoreRes = object;

/**
 * CallsUpsertCompleteReq
 * Request for upserting a batch of completed calls.
 */
export interface CallsUpsertCompleteReq {
  /** Batch */
  batch: CompletedCallSchemaForInsert[];
}

/**
 * CallsUpsertCompleteRes
 * Response for upserting a batch of completed calls.
 */
export type CallsUpsertCompleteRes = object;

/**
 * CallsUsageReq
 * Request to compute aggregated usage for multiple root calls.
 *
 * This endpoint returns usage metrics for each requested root call, where each
 * root's metrics include the sum of its own usage plus all descendants' usage.
 *
 * Note: All matching calls are loaded into memory for aggregation. For very large
 * result sets (>10k calls), consider batching root call IDs or using narrower
 * filters at the application layer.
 */
export interface CallsUsageReq {
  /** Project Id */
  project_id: string;
  /**
   * Call Ids
   * Root call IDs to aggregate. Each result key corresponds to one input call ID.
   */
  call_ids: string[];
  /**
   * Include Costs
   * If true, include cost calculations in the usage.
   * @default false
   */
  include_costs?: boolean;
  /**
   * Limit
   * Maximum number of calls to process across all traces. Acts as a safety limit to prevent unbounded memory usage.
   * @default 10000
   */
  limit?: number;
}

/**
 * CallsUsageRes
 * Response with aggregated usage metrics per root call.
 */
export interface CallsUsageRes {
  /** Call Usage */
  call_usage?: Record<string, Record<string, LLMAggregatedUsage>>;
  /** Unfinished Call Ids */
  unfinished_call_ids?: string[];
}

/** CatalogModelsRes */
export interface CatalogModelsRes {
  /** Models */
  models: LLMModelDetails[];
}

/**
 * CompletedCallSchemaForInsert
 * Schema for inserting a completed call directly.
 *
 * This represents a call that is already finished at insertion time, with both
 * start and end information provided together. Used by the calls_complete endpoint.
 */
export interface CompletedCallSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Id */
  id: string;
  /** Trace Id */
  trace_id: string;
  /** Op Name */
  op_name: string;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
  /**
   * Ended At
   * @format date-time
   */
  ended_at: string;
  /** Display Name */
  display_name?: string | null;
  /** Parent Id */
  parent_id?: string | null;
  /** Thread Id */
  thread_id?: string | null;
  /** Turn Id */
  turn_id?: string | null;
  /** Attributes */
  attributes: Record<string, any>;
  /** Inputs */
  inputs: Record<string, any>;
  /** Output */
  output?: null;
  summary: SummaryInsertMap;
  /** Otel Dump */
  otel_dump?: Record<string, any> | null;
  /** Exception */
  exception?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
  /** Wb Run Step */
  wb_run_step?: number | null;
  /** Wb Run Step End */
  wb_run_step_end?: number | null;
}

/**
 * ContainsOperation
 * Case-insensitive substring match.
 *
 * Not part of MongoDB. Weave-specific addition.
 *
 * Example:
 *     ```
 *     {
 *         "$contains": {
 *             "input": {"$getField": "display_name"},
 *             "substr": {"$literal": "llm"},
 *             "case_insensitive": true
 *         }
 *     }
 *     ```
 */
export interface ContainsOperation {
  /**
   * Specification for the `$contains` operation.
   *
   * - `input`: The string to search.
   * - `substr`: The substring to search for.
   * - `case_insensitive`: If true, match is case-insensitive.
   */
  $contains: ContainsSpec;
}

/**
 * ContainsSpec
 * Specification for the `$contains` operation.
 *
 * - `input`: The string to search.
 * - `substr`: The substring to search for.
 * - `case_insensitive`: If true, match is case-insensitive.
 */
export interface ContainsSpec {
  /** Input */
  input:
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
  /** Substr */
  substr:
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
  /**
   * Case Insensitive
   * @default false
   */
  case_insensitive?: boolean | null;
}

/**
 * ConvertOperation
 * Convert the input value to a specific type (e.g., `int`, `bool`, `string`).
 *
 * Example:
 *     ```
 *     {
 *         "$convert": {
 *             "input": {"$getField": "inputs.value"},
 *             "to": "int"
 *         }
 *     }
 *     ```
 */
export interface ConvertOperation {
  /**
   * Specifies conversion details for `$convert`.
   *
   * - `input`: The operand to convert.
   * - `to`: The type to convert to.
   */
  $convert: ConvertSpec;
}

/**
 * ConvertSpec
 * Specifies conversion details for `$convert`.
 *
 * - `input`: The operand to convert.
 * - `to`: The type to convert to.
 */
export interface ConvertSpec {
  /** Input */
  input:
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
  /** To */
  to: 'double' | 'string' | 'int' | 'bool' | 'exists';
}

/**
 * Cost
 * Costs are expressed in USD per million tokens.
 */
export interface Cost {
  /**
   * Input
   * Cost per million input tokens (USD).
   */
  input: number;
  /**
   * Output
   * Cost per million output tokens (USD).
   */
  output: number;
  /**
   * Reasoning
   * Cost per million reasoning tokens (USD).
   */
  reasoning?: number | null;
  /**
   * Cache Read
   * Cost per million cached read tokens (USD).
   */
  cache_read?: number | null;
  /**
   * Cache Write
   * Cost per million cached write tokens (USD).
   */
  cache_write?: number | null;
  /**
   * Input Audio
   * Cost per million audio input tokens (USD).
   */
  input_audio?: number | null;
  /**
   * Output Audio
   * Cost per million audio output tokens (USD).
   */
  output_audio?: number | null;
}

/** CostCreateInput */
export interface CostCreateInput {
  /** Prompt Token Cost */
  prompt_token_cost: number;
  /** Completion Token Cost */
  completion_token_cost: number;
  /**
   * Cache Read Input Token Cost
   * @default 0
   */
  cache_read_input_token_cost?: number;
  /**
   * Cache Creation Input Token Cost
   * @default 0
   */
  cache_creation_input_token_cost?: number;
  /**
   * Prompt Token Cost Unit
   * The unit of the cost for the prompt tokens
   * @default "USD"
   */
  prompt_token_cost_unit?: string | null;
  /**
   * Completion Token Cost Unit
   * The unit of the cost for the completion tokens
   * @default "USD"
   */
  completion_token_cost_unit?: string | null;
  /**
   * Effective Date
   * The date after which the cost is effective for, will default to the current date if not provided
   */
  effective_date?: string | null;
  /**
   * Provider Id
   * The provider of the LLM, e.g. 'openai' or 'mistral'. If not provided, the provider_id will be set to 'default'
   */
  provider_id?: string | null;
}

/** CostCreateReq */
export interface CostCreateReq {
  /** Project Id */
  project_id: string;
  /** Costs */
  costs: Record<string, CostCreateInput>;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** CostCreateRes */
export interface CostCreateRes {
  /** Ids */
  ids: any[][];
}

/** CostPurgeReq */
export interface CostPurgeReq {
  /** Project Id */
  project_id: string;
  query: Query;
}

/** CostPurgeRes */
export type CostPurgeRes = object;

/** CostQueryOutput */
export interface CostQueryOutput {
  /** Id */
  id?: string | null;
  /** Llm Id */
  llm_id?: string | null;
  /** Prompt Token Cost */
  prompt_token_cost?: number | null;
  /** Completion Token Cost */
  completion_token_cost?: number | null;
  /** Cache Read Input Token Cost */
  cache_read_input_token_cost?: number | null;
  /** Cache Creation Input Token Cost */
  cache_creation_input_token_cost?: number | null;
  /** Prompt Token Cost Unit */
  prompt_token_cost_unit?: string | null;
  /** Completion Token Cost Unit */
  completion_token_cost_unit?: string | null;
  /** Effective Date */
  effective_date?: string | null;
  /** Provider Id */
  provider_id?: string | null;
}

/** CostQueryReq */
export interface CostQueryReq {
  /** Project Id */
  project_id: string;
  /** Fields */
  fields?: string[] | null;
  query?: Query | null;
  /** Sort By */
  sort_by?: SortBy[] | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
}

/** CostQueryRes */
export interface CostQueryRes {
  /** Results */
  results: CostQueryOutput[];
}

/** CreateAndLinkPayload */
export interface CreateAndLinkPayload {
  /**
   * Ref
   * @minLength 1
   */
  ref: string;
  target: CreateAndLinkTarget;
  /**
   * Aliases
   * @default []
   */
  aliases?: string[];
}

/** CreateAndLinkTarget */
export interface CreateAndLinkTarget {
  /**
   * Portfolio Name
   * @minLength 1
   */
  portfolio_name: string;
  /**
   * Entity Name
   * @minLength 1
   */
  entity_name: string;
  /**
   * Project Name
   * @minLength 1
   */
  project_name: string;
}

/** CreateAndLinkWeaveAssetRes */
export interface CreateAndLinkWeaveAssetRes {
  /** Version Index */
  version_index?: number | null;
}

/** Datacenter */
export interface Datacenter {
  /** Country Code */
  country_code: string;
}

/** DatasetCreateBody */
export interface DatasetCreateBody {
  /**
   * Name
   * The name of this dataset.  Datasets with the same name will be versioned together.
   */
  name?: string | null;
  /**
   * Description
   * A description of this dataset
   */
  description?: string | null;
  /**
   * Rows
   * Dataset rows
   */
  rows: Record<string, any>[];
}

/** DatasetCreateRes */
export interface DatasetCreateRes {
  /**
   * Digest
   * The digest of the created dataset
   */
  digest: string;
  /**
   * Object Id
   * The ID of the created dataset
   */
  object_id: string;
  /**
   * Version Index
   * The version index of the created dataset
   */
  version_index: number;
}

/** DatasetDeleteRes */
export interface DatasetDeleteRes {
  /**
   * Num Deleted
   * Number of dataset versions deleted
   */
  num_deleted: number;
}

/** DatasetReadRes */
export interface DatasetReadRes {
  /**
   * Object Id
   * The dataset ID
   */
  object_id: string;
  /**
   * Digest
   * The digest of the dataset object
   */
  digest: string;
  /**
   * Version Index
   * The version index of the object
   */
  version_index: number;
  /**
   * Created At
   * When the object was created
   * @format date-time
   */
  created_at: string;
  /**
   * Name
   * The name of the dataset
   */
  name: string;
  /**
   * Description
   * Description of the dataset
   */
  description?: string | null;
  /**
   * Rows
   * Reference to the dataset rows data
   */
  rows: string;
}

/** DeletedObjVersion */
export interface DeletedObjVersion {
  /** Digest */
  digest: string;
  /** Base Object Class */
  base_object_class?: string | null;
  /** Leaf Object Class */
  leaf_object_class?: string | null;
}

/** EndedCallSchemaForInsert */
export interface EndedCallSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Id */
  id: string;
  /** Trace Id */
  trace_id?: string | null;
  /** Is Eval */
  is_eval?: boolean | null;
  /**
   * Ended At
   * @format date-time
   */
  ended_at: string;
  /** Started At */
  started_at?: string | null;
  /** Exception */
  exception?: string | null;
  /** Output */
  // TODO: This type is manually updated at the moment. https://github.com/wandb/weave/pull/6195/changes#r2850346035
  output?: any;
  summary: SummaryInsertMap;
  /** Wb Run Step End */
  wb_run_step_end?: number | null;
}

/**
 * EqOperation
 * Equality check between two operands.
 *
 * Example:
 *     ```
 *     {
 *         "$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]
 *     }
 *     ```
 */
export interface EqOperation {
  /**
   * $Eq
   * @maxItems 2
   * @minItems 2
   */
  $eq: any[];
}

/** EvalResultsEvaluationSummary */
export interface EvalResultsEvaluationSummary {
  /** Evaluation Call Id */
  evaluation_call_id: string;
  /**
   * Trial Count
   * @default 0
   */
  trial_count?: number;
  /** Scorer Stats */
  scorer_stats?: EvalResultsScorerStats[];
  /**
   * Predict Total Tokens
   * Sum of per-trial predict-only token usage for this evaluation (the model's predict() tokens only, excluding LLM-as-a-judge scorer usage); None when no trial reports usage.
   */
  predict_total_tokens?: number | null;
  /**
   * Predict Total Cost
   * Sum of per-trial predict-only cost for this evaluation (the model's predict() cost only, excluding LLM-as-a-judge scorer cost); None when no trial reports cost.
   */
  predict_total_cost?: number | null;
  /** Evaluation Ref */
  evaluation_ref?: string | null;
  /** Model Ref */
  model_ref?: string | null;
  /** Display Name */
  display_name?: string | null;
  /** Trace Id */
  trace_id?: string | null;
  /** Started At */
  started_at?: string | null;
}

/**
 * EvalResultsFilter
 * A filter scoped to an optional evaluation.
 */
export interface EvalResultsFilter {
  /**
   * Evaluation Call Id
   * When set, filter fields are scoped to this evaluation's data.
   */
  evaluation_call_id?: string | null;
  /** Filter expression. Supported field prefixes: scores.<name>, inputs.<path>, outputs.<path>. */
  query: Query;
}

/** EvalResultsQueryBody */
export interface EvalResultsQueryBody {
  /**
   * Evaluation Call Ids
   * Evaluation root call IDs to include.
   */
  evaluation_call_ids?: string[] | null;
  /**
   * Evaluation Run Ids
   * Alias for evaluation call IDs from the Evaluation Runs API.
   */
  evaluation_run_ids?: string[] | null;
  /**
   * Require Intersection
   * When true, only include rows present in all requested evaluations.
   * @default false
   */
  require_intersection?: boolean;
  /**
   * Include Raw Data Rows
   * When true, populate raw_data_row on each result row. Inline rows are returned as their dict value; dataset-referenced rows are returned as the ref string unless resolve_row_refs is also true.
   * @default false
   */
  include_raw_data_rows?: boolean;
  /**
   * Resolve Row Refs
   * When true (requires include_raw_data_rows=True), resolve dataset-row reference strings to actual row data via a table lookup. When false, dataset-row refs are returned as-is.
   * @default false
   */
  resolve_row_refs?: boolean;
  /**
   * Include Rows
   * When true, include grouped row/trial data in `rows` and compute `total_rows` for the requested row-level view.
   * @default true
   */
  include_rows?: boolean;
  /**
   * Include Summary
   * When true, include aggregated scorer/evaluation summary data in `summary`.
   * @default false
   */
  include_summary?: boolean;
  /**
   * Summary Require Intersection
   * Optional intersection behavior for the summary section. When null, the value of `require_intersection` is used.
   */
  summary_require_intersection?: boolean | null;
  /**
   * Include Predict And Score Children
   * When true (default), fetch child calls (predict/score) of each predict_and_score call to populate predict_call_id, scorer_call_ids, and more precise latency/token data. When false, these fields are derived from the predict_and_score call itself (predict_call_id and scorer_call_ids will be null/empty).
   * @default true
   */
  include_predict_and_score_children?: boolean;
  /**
   * Include Costs
   * When true, price each trial's predict call so rows and summary report predict-only cost (`total_cost` / `predict_total_cost`); scorer costs are excluded. Opt-in: other callers skip the cost computation.
   * @default false
   */
  include_costs?: boolean;
  /**
   * Sort By
   * Sort specification for result rows. Supported field prefixes: scores.<name>, inputs.<path>, outputs.<path>. When null, rows are sorted by row_digest ASC.
   */
  sort_by?: EvalResultsSortBy[] | null;
  /**
   * Filters
   * Filters applied to grouped rows. Multiple filters are AND'd together.
   */
  filters?: EvalResultsFilter[] | null;
  /**
   * Filter Logic Operator
   * How to combine filters across evaluations: 'and' (Match All - row must match in ALL evals) or 'or' (Match Any - row must match in ANY eval). Defaults to 'or' (Match Any).
   * @default "or"
   */
  filter_logic_operator?: 'and' | 'or';
  /**
   * Limit
   * Optional row-level page size applied after grouping and intersection.
   */
  limit?: number | null;
  /**
   * Offset
   * Optional row-level page offset applied after grouping and intersection.
   * @default 0
   */
  offset?: number;
}

/** EvalResultsQueryRes */
export interface EvalResultsQueryRes {
  /** Rows */
  rows: EvalResultsRow[];
  /** Total Rows */
  total_rows: number;
  summary?: EvalResultsSummaryRes | null;
  /**
   * Warnings
   * Non-fatal warnings (e.g. failed to resolve dataset row refs).
   */
  warnings?: string[];
}

/** EvalResultsRow */
export interface EvalResultsRow {
  /** Row Digest */
  row_digest: string;
  /** Raw Data Row */
  raw_data_row?: null;
  /** Evaluations */
  evaluations?: EvalResultsRowEvaluation[];
}

/** EvalResultsRowEvaluation */
export interface EvalResultsRowEvaluation {
  /** Evaluation Call Id */
  evaluation_call_id: string;
  /** Trials */
  trials?: EvalResultsTrial[];
}

/**
 * EvalResultsScorerStats
 * Stats for a single flattened score dimension (scorer_key or scorer_key.path.to.leaf).
 */
export interface EvalResultsScorerStats {
  /** Scorer Key */
  scorer_key: string;
  /**
   * Path
   * Dot-joined subpath for nested dimensions, e.g. 'passed' for token_distance.passed. None for root-level scalar scorers.
   */
  path?: string | null;
  /**
   * Value Type
   * Type of the leaf value: binary (bool), continuous (number), or text (string).
   */
  value_type?: 'binary' | 'continuous' | 'text' | null;
  /**
   * Trial Count
   * @default 0
   */
  trial_count?: number;
  /**
   * Numeric Count
   * @default 0
   */
  numeric_count?: number;
  /** Numeric Mean */
  numeric_mean?: number | null;
  /**
   * Pass True Count
   * @default 0
   */
  pass_true_count?: number;
  /**
   * Pass Known Count
   * @default 0
   */
  pass_known_count?: number;
  /** Pass Rate */
  pass_rate?: number | null;
  /** Pass Signal Coverage */
  pass_signal_coverage?: number | null;
}

/**
 * EvalResultsSortBy
 * Sort specification for evaluation results, extending SortBy
 */
export interface EvalResultsSortBy {
  /** Field */
  field: string;
  /** Direction */
  direction: 'asc' | 'desc';
  /**
   * Evaluation Call Id
   * Scope the sort to a specific evaluation's scores.
   */
  evaluation_call_id?: string | null;
  /**
   * Mode
   * When 'value', sort by the field value for the specified evaluation. When 'difference', sort by max-min spread of the field across all evaluations (evaluation_call_id is ignored).
   * @default "value"
   */
  mode?: 'value' | 'difference';
}

/** EvalResultsSummaryRes */
export interface EvalResultsSummaryRes {
  /**
   * Row Count
   * @default 0
   */
  row_count?: number;
  /** Evaluations */
  evaluations?: EvalResultsEvaluationSummary[];
}

/** EvalResultsTrial */
export interface EvalResultsTrial {
  /** Predict And Score Call Id */
  predict_and_score_call_id: string;
  /** Predict Call Id */
  predict_call_id?: string | null;
  /** Model Output */
  model_output?: null;
  /** Scores */
  scores?: Record<string, any>;
  /** Model Latency Seconds */
  model_latency_seconds?: number | null;
  /** Total Tokens */
  total_tokens?: number | null;
  /** Total Cost */
  total_cost?: number | null;
  /** Scorer Call Ids */
  scorer_call_ids?: Record<string, string>;
  /** Genai Span Ref */
  genai_span_ref?: GenAISpanRef[] | null;
}

/** EvaluateModelReq */
export interface EvaluateModelReq {
  /** Project Id */
  project_id: string;
  /** Evaluation Ref */
  evaluation_ref: string;
  /** Model Ref */
  model_ref: string;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** EvaluateModelRes */
export interface EvaluateModelRes {
  /** Call Id */
  call_id: string;
}

/** EvaluationCreateBody */
export interface EvaluationCreateBody {
  /**
   * Name
   * The name of this evaluation.  Evaluations with the same name will be versioned together.
   */
  name: string;
  /**
   * Description
   * A description of this evaluation
   */
  description?: string | null;
  /**
   * Dataset
   * Reference to the dataset (weave:// URI)
   */
  dataset: string;
  /**
   * Scorers
   * List of scorer references (weave:// URIs)
   */
  scorers?: string[] | null;
  /**
   * Trials
   * Number of trials to run
   * @default 1
   */
  trials?: number;
  /**
   * Evaluation Name
   * Name for the evaluation run
   */
  evaluation_name?: string | null;
  /**
   * Eval Attributes
   * Optional attributes for the evaluation
   */
  eval_attributes?: Record<string, any> | null;
}

/** EvaluationCreateRes */
export interface EvaluationCreateRes {
  /**
   * Digest
   * The digest of the created evaluation
   */
  digest: string;
  /**
   * Object Id
   * The ID of the created evaluation
   */
  object_id: string;
  /**
   * Version Index
   * The version index of the created evaluation
   */
  version_index: number;
  /**
   * Evaluation Ref
   * Full reference to the created evaluation
   */
  evaluation_ref: string;
}

/** EvaluationDeleteRes */
export interface EvaluationDeleteRes {
  /**
   * Num Deleted
   * Number of evaluation versions deleted
   */
  num_deleted: number;
}

/** EvaluationReadRes */
export interface EvaluationReadRes {
  /**
   * Object Id
   * The evaluation ID
   */
  object_id: string;
  /**
   * Digest
   * The digest of the evaluation
   */
  digest: string;
  /**
   * Version Index
   * The version index of the evaluation
   */
  version_index: number;
  /**
   * Created At
   * When the evaluation was created
   * @format date-time
   */
  created_at: string;
  /**
   * Name
   * The name of the evaluation
   */
  name: string;
  /**
   * Description
   * A description of the evaluation
   */
  description?: string | null;
  /**
   * Dataset
   * Dataset reference (weave:// URI)
   */
  dataset: string;
  /**
   * Scorers
   * List of scorer references (weave:// URIs)
   */
  scorers: string[];
  /**
   * Trials
   * Number of trials
   */
  trials: number;
  /**
   * Evaluation Name
   * Name for the evaluation run
   */
  evaluation_name?: string | null;
  /**
   * Evaluate Op
   * Evaluate op reference (weave:// URI)
   */
  evaluate_op?: string | null;
  /**
   * Predict And Score Op
   * Predict and score op reference (weave:// URI)
   */
  predict_and_score_op?: string | null;
  /**
   * Summarize Op
   * Summarize op reference (weave:// URI)
   */
  summarize_op?: string | null;
}

/** EvaluationRunCreateBody */
export interface EvaluationRunCreateBody {
  /**
   * Evaluation
   * Reference to the evaluation (weave:// URI)
   */
  evaluation: string;
  /**
   * Model
   * Reference to the model (weave:// URI)
   */
  model: string;
  /**
   * Source Evaluation Run Id
   * Source evaluation run ID if this run was created by rescoring — provenance link
   */
  source_evaluation_run_id?: string | null;
}

/** EvaluationRunCreateRes */
export interface EvaluationRunCreateRes {
  /**
   * Evaluation Run Id
   * The ID of the created evaluation run
   */
  evaluation_run_id: string;
}

/** EvaluationRunDeleteRes */
export interface EvaluationRunDeleteRes {
  /**
   * Num Deleted
   * Number of evaluation runs deleted
   */
  num_deleted: number;
}

/**
 * EvaluationRunFinishBody
 * Request body for finishing an evaluation run via REST API.
 *
 * This model excludes project_id and evaluation_run_id since they come from the URL path in RESTful endpoints.
 */
export interface EvaluationRunFinishBody {
  /**
   * Summary
   * Optional summary dictionary for the evaluation run
   */
  summary?: Record<string, any> | null;
}

/** EvaluationRunFinishRes */
export interface EvaluationRunFinishRes {
  /**
   * Success
   * Whether the evaluation run was finished successfully
   */
  success: boolean;
}

/** EvaluationRunReadRes */
export interface EvaluationRunReadRes {
  /**
   * Evaluation Run Id
   * The evaluation run ID
   */
  evaluation_run_id: string;
  /**
   * Evaluation
   * Reference to the evaluation (weave:// URI)
   */
  evaluation: string;
  /**
   * Model
   * Reference to the model (weave:// URI)
   */
  model: string;
  /**
   * Status
   * Status of the evaluation run
   */
  status?: string | null;
  /**
   * Started At
   * When the evaluation run started
   */
  started_at?: string | null;
  /**
   * Finished At
   * When the evaluation run finished
   */
  finished_at?: string | null;
  /**
   * Summary
   * Summary data for the evaluation run
   */
  summary?: Record<string, any> | null;
  /**
   * Source Evaluation Run Id
   * Source evaluation run ID if this run was created by rescoring
   */
  source_evaluation_run_id?: string | null;
}

/** EvaluationStatusComplete */
export interface EvaluationStatusComplete {
  /**
   * Code
   * @default "complete"
   */
  code?: 'complete';
  /** Output */
  output: Record<string, any>;
}

/** EvaluationStatusFailed */
export interface EvaluationStatusFailed {
  /**
   * Code
   * @default "failed"
   */
  code?: 'failed';
  /** Error */
  error?: string | null;
}

/** EvaluationStatusNotFound */
export interface EvaluationStatusNotFound {
  /**
   * Code
   * @default "not_found"
   */
  code?: 'not_found';
}

/** EvaluationStatusReq */
export interface EvaluationStatusReq {
  /** Project Id */
  project_id: string;
  /** Call Id */
  call_id: string;
}

/** EvaluationStatusRes */
export interface EvaluationStatusRes {
  /** Status */
  status:
    | EvaluationStatusNotFound
    | EvaluationStatusRunning
    | EvaluationStatusFailed
    | EvaluationStatusComplete;
}

/** EvaluationStatusRunning */
export interface EvaluationStatusRunning {
  /**
   * Code
   * @default "running"
   */
  code?: 'running';
  /** Completed Rows */
  completed_rows: number;
  /** Total Rows */
  total_rows: number;
}

/**
 * FeedbackAggregateBucket
 * One (time bucket, group) row of aggregated scorer feedback.
 */
export interface FeedbackAggregateBucket {
  /**
   * Time Bucket Start Ms
   * Time bucket start, unix epoch ms (UTC). None when unbucketed.
   */
  time_bucket_start_ms?: number | null;
  /**
   * Group
   * Group-by dimension values for this row (e.g. {'scorer_id': '...'}).
   */
  group?: Record<string, string>;
  /**
   * Total Count
   * Number of feedback rows in this bucket/group.
   */
  total_count: number;
  /**
   * Scored Count
   * Rows that emitted a score (at least one tag or rating). Excludes agent-monitor rows that scored nothing — use this for score volume.
   */
  scored_count: number;
  /**
   * Tag Counts
   * Count of each scorer tag.
   */
  tag_counts?: Record<string, number>;
  /**
   * Rating Counts
   * Number of rows carrying each rating key (e.g. '_rating_').
   */
  rating_counts?: Record<string, number>;
  /**
   * Rating Sums
   * Sum of each rating key's values; client derives avg = sum/count.
   */
  rating_sums?: Record<string, number>;
}

/**
 * FeedbackAggregateReq
 * Query for aggregate scores by time bucket and dimension.
 */
export interface FeedbackAggregateReq {
  /** Project Id */
  project_id: string;
  /**
   * After Ms
   * Inclusive lower bound on created_at (milliseconds since epoch).
   * @min 0
   */
  after_ms: number;
  /**
   * Before Ms
   * Exclusive upper bound on created_at (milliseconds since epoch).
   * @min 0
   */
  before_ms: number;
  /**
   * Time Bucket Seconds
   * Time bucket size in seconds, e.g. 3600 for 1h buckets
   */
  time_bucket_seconds?: number | null;
  /**
   * Feedback Types
   * Filter on feedback_type by prefix
   */
  feedback_types?: string[];
  /**
   * Tags
   * Filter to feedback that includes any of the given tags
   */
  tags?: string[];
  /**
   * Rating Min
   * Include only rows with a rating >= this value
   */
  rating_min?: number | null;
  /**
   * Rating Max
   * Include only rows with a rating <= this value
   */
  rating_max?: number | null;
  /**
   * Monitor Ids
   * Filter to these monitor ids (exact match; suffix with '*' for prefix match).
   */
  monitor_ids?: string[];
  /**
   * Scorer Ids
   * Filter to these scorer ids (exact match; suffix with '*' for prefix match).
   */
  scorer_ids?: string[];
  /**
   * Span Agent Names
   * Filter to feedback whose span_agent_name matches any of these (exact).
   */
  span_agent_names?: string[];
  /**
   * Span Types
   * Filter by span type (turn vs conversation).
   */
  span_types?: ('agent_turn' | 'agent_conversation')[];
  /**
   * Group By
   * Allowed: ['scorer_id', 'span_agent_name', 'span_agent_version', 'span_status_code'].
   */
  group_by?: (
    | 'scorer_id'
    | 'span_agent_name'
    | 'span_agent_version'
    | 'span_status_code'
  )[];
}

/**
 * FeedbackAggregateRes
 * Sparse time-series of aggregated scorer feedback (empty buckets omitted).
 */
export interface FeedbackAggregateRes {
  /**
   * Time Bucket Seconds
   * Time bucket size used (seconds). None when unbucketed.
   */
  time_bucket_seconds?: number | null;
  /**
   * After Ms
   * Resolved inclusive lower bound, unix epoch ms (UTC).
   */
  after_ms: number;
  /**
   * Before Ms
   * Resolved exclusive upper bound, unix epoch ms (UTC).
   */
  before_ms: number;
  /** Buckets */
  buckets?: FeedbackAggregateBucket[];
}

/** FeedbackCreateBatchReq */
export interface FeedbackCreateBatchReq {
  /** Batch */
  batch: FeedbackCreateReq[];
}

/** FeedbackCreateBatchRes */
export interface FeedbackCreateBatchRes {
  /** Res */
  res: FeedbackCreateRes[];
}

/** FeedbackCreateReq */
export interface FeedbackCreateReq {
  /**
   * Id
   * If provided by the client, this ID will be used for the feedback row instead of a server-generated one.
   */
  id?: string | null;
  /** Project Id */
  project_id: string;
  /** Weave Ref */
  weave_ref: string;
  /** Creator */
  creator?: string | null;
  /** Feedback Type */
  feedback_type: string;
  /** Payload */
  payload: Record<string, any>;
  /** Annotation Ref */
  annotation_ref?: string | null;
  /** Runnable Ref */
  runnable_ref?: string | null;
  /** Call Ref */
  call_ref?: string | null;
  /** Trigger Ref */
  trigger_ref?: string | null;
  /**
   * Queue Id
   * The annotation queue ID this feedback was created from. References annotation_queues.id. NULL when feedback is created outside of queues.
   */
  queue_id?: string | null;
  /**
   * Scorer Tags
   * Tags applied to the ref by a scorer
   */
  scorer_tags?: string[];
  /**
   * Scorer Tag Reasons
   * reason text per tag, keyed by tag name
   */
  scorer_tag_reasons?: Record<string, string>;
  /**
   * Scorer Tag Confidences
   * confidence (0-1) per tag, keyed by tag name
   */
  scorer_tag_confidences?: Record<string, number>;
  /**
   * Scorer Ratings
   * numeric ratings (0-1) keyed by rating name
   */
  scorer_ratings?: Record<string, number>;
  /**
   * Scorer Rating Reasons
   * reason text per rating, keyed by rating name
   */
  scorer_rating_reasons?: Record<string, string>;
  /**
   * Scorer Rating Confidences
   * confidence (0-1) per rating, keyed by rating name
   */
  scorer_rating_confidences?: Record<string, number>;
  /**
   * Span Agent Name
   * Display name of the scored agent (from spans.agent_name)
   * @default ""
   */
  span_agent_name?: string;
  /**
   * Span Agent Version
   * Version of the scored agent (from spans.agent_version)
   * @default ""
   */
  span_agent_version?: string;
  /**
   * Span Status Code
   * Status of the scored turn (from spans.status_code)
   * @default "UNSET"
   */
  span_status_code?: string;
  /**
   * Span Conversation Id
   * Conversation the feedback belongs to (from spans.conversation_id)
   * @default ""
   */
  span_conversation_id?: string;
  /**
   * Span Trace Id
   * Turn the feedback belongs to (from spans.trace_id)
   * @default ""
   */
  span_trace_id?: string;
  /**
   * Scorer Trace Id
   * Trace of the scorer (judge) invocation that produced this feedback (spans.trace_id of the judge call). Distinct from span_trace_id, which is the scored turn. Lets signals price the invocation off the judge span without joining the calls model.
   * @default ""
   */
  scorer_trace_id?: string;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** FeedbackCreateRes */
export interface FeedbackCreateRes {
  /** Id */
  id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Wb User Id */
  wb_user_id: string;
  /** Payload */
  payload: Record<string, any>;
}

/**
 * FeedbackMetricSpec
 * Specification for a feedback payload metric to aggregate.
 */
export interface FeedbackMetricSpec {
  /**
   * Json Path
   * Dot path into payload_dump (e.g. 'output', 'output.score').
   */
  json_path: string;
  /**
   * Value Type
   * Type of value at path. numeric: avg/min/max; boolean: count_true/count_false.
   * @default "numeric"
   */
  value_type?: 'numeric' | 'boolean' | 'categorical';
  /**
   * Aggregations
   * Aggregation functions to compute. If empty, defaults are chosen based on value_type: numeric->avg/min/max, boolean->count_true/count_false.
   */
  aggregations?: AggregationType[];
  /**
   * Percentiles
   * Percentile values to compute (0–100), e.g. [5, 50, 95]. Only applicable for numeric value_type fields; ignored for boolean/categorical.
   */
  percentiles?: number[];
}

/**
 * FeedbackPayloadPath
 * Discovered path in feedback payload with inferred type.
 */
export interface FeedbackPayloadPath {
  /**
   * Json Path
   * Dot path into payload (e.g. 'output.score').
   */
  json_path: string;
  /**
   * Value Type
   * Inferred type of value at path.
   * @default "numeric"
   */
  value_type?: 'numeric' | 'boolean' | 'categorical';
}

/**
 * FeedbackPayloadSchemaReq
 * Request for feedback payload schema discovery.
 */
export interface FeedbackPayloadSchemaReq {
  /** Project Id */
  project_id: string;
  /**
   * Start
   * Inclusive start time (UTC, ISO 8601).
   * @format date-time
   */
  start: string;
  /**
   * End
   * Exclusive end time (UTC, ISO 8601). Defaults to now if omitted.
   */
  end?: string | null;
  /**
   * Feedback Type
   * Filter by feedback_type.
   */
  feedback_type?: string | null;
  /**
   * Trigger Ref
   * Filter by trigger_ref (exact or prefix match for all-versions).
   */
  trigger_ref?: string | null;
  /**
   * Sample Limit
   * Max distinct trigger_refs to sample when discovering the payload schema. Each distinct trigger_ref (monitor/source) typically has a fixed payload structure, so sampling one payload per ref is usually enough to see the full schema. 2 000 covers virtually all real-world projects while keeping the query fast; the hard cap of 5 000 prevents runaway scans.
   * @min 1
   * @max 5000
   * @default 2000
   */
  sample_limit?: number;
}

/**
 * FeedbackPayloadSchemaRes
 * Response with discovered feedback payload paths and types.
 */
export interface FeedbackPayloadSchemaRes {
  /**
   * Paths
   * Discovered leaf paths with inferred value types.
   */
  paths?: FeedbackPayloadPath[];
}

/** FeedbackPurgeReq */
export interface FeedbackPurgeReq {
  /** Project Id */
  project_id: string;
  query: Query;
}

/** FeedbackPurgeRes */
export type FeedbackPurgeRes = object;

/** FeedbackQueryReq */
export interface FeedbackQueryReq {
  /** Project Id */
  project_id: string;
  /** Fields */
  fields?: string[] | null;
  query?: Query | null;
  /** Sort By */
  sort_by?: SortBy[] | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
}

/** FeedbackQueryRes */
export interface FeedbackQueryRes {
  /** Result */
  result: Record<string, any>[];
  /**
   * Total Count
   * @min 0
   */
  total_count: number;
}

/** FeedbackReplaceReq */
export interface FeedbackReplaceReq {
  /**
   * Id
   * If provided by the client, this ID will be used for the feedback row instead of a server-generated one.
   */
  id?: string | null;
  /** Project Id */
  project_id: string;
  /** Weave Ref */
  weave_ref: string;
  /** Creator */
  creator?: string | null;
  /** Feedback Type */
  feedback_type: string;
  /** Payload */
  payload: Record<string, any>;
  /** Annotation Ref */
  annotation_ref?: string | null;
  /** Runnable Ref */
  runnable_ref?: string | null;
  /** Call Ref */
  call_ref?: string | null;
  /** Trigger Ref */
  trigger_ref?: string | null;
  /**
   * Queue Id
   * The annotation queue ID this feedback was created from. References annotation_queues.id. NULL when feedback is created outside of queues.
   */
  queue_id?: string | null;
  /**
   * Scorer Tags
   * Tags applied to the ref by a scorer
   */
  scorer_tags?: string[];
  /**
   * Scorer Tag Reasons
   * reason text per tag, keyed by tag name
   */
  scorer_tag_reasons?: Record<string, string>;
  /**
   * Scorer Tag Confidences
   * confidence (0-1) per tag, keyed by tag name
   */
  scorer_tag_confidences?: Record<string, number>;
  /**
   * Scorer Ratings
   * numeric ratings (0-1) keyed by rating name
   */
  scorer_ratings?: Record<string, number>;
  /**
   * Scorer Rating Reasons
   * reason text per rating, keyed by rating name
   */
  scorer_rating_reasons?: Record<string, string>;
  /**
   * Scorer Rating Confidences
   * confidence (0-1) per rating, keyed by rating name
   */
  scorer_rating_confidences?: Record<string, number>;
  /**
   * Span Agent Name
   * Display name of the scored agent (from spans.agent_name)
   * @default ""
   */
  span_agent_name?: string;
  /**
   * Span Agent Version
   * Version of the scored agent (from spans.agent_version)
   * @default ""
   */
  span_agent_version?: string;
  /**
   * Span Status Code
   * Status of the scored turn (from spans.status_code)
   * @default "UNSET"
   */
  span_status_code?: string;
  /**
   * Span Conversation Id
   * Conversation the feedback belongs to (from spans.conversation_id)
   * @default ""
   */
  span_conversation_id?: string;
  /**
   * Span Trace Id
   * Turn the feedback belongs to (from spans.trace_id)
   * @default ""
   */
  span_trace_id?: string;
  /**
   * Scorer Trace Id
   * Trace of the scorer (judge) invocation that produced this feedback (spans.trace_id of the judge call). Distinct from span_trace_id, which is the scored turn. Lets signals price the invocation off the judge span without joining the calls model.
   * @default ""
   */
  scorer_trace_id?: string;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /** Feedback Id */
  feedback_id: string;
}

/** FeedbackReplaceRes */
export interface FeedbackReplaceRes {
  /** Id */
  id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Wb User Id */
  wb_user_id: string;
  /** Payload */
  payload: Record<string, any>;
}

/**
 * FeedbackStatsReq
 * Request for aggregated feedback statistics over time buckets.
 */
export interface FeedbackStatsReq {
  /** Project Id */
  project_id: string;
  /**
   * Start
   * Inclusive start time (UTC, ISO 8601).
   * @format date-time
   */
  start: string;
  /**
   * End
   * Exclusive end time (UTC, ISO 8601). Defaults to now if omitted.
   */
  end?: string | null;
  /**
   * Feedback Type
   * Filter by feedback_type.
   */
  feedback_type?: string | null;
  /**
   * Trigger Ref
   * Filter by trigger_ref (exact or prefix match for all-versions).
   */
  trigger_ref?: string | null;
  /**
   * Granularity
   * Bucket size in seconds. If omitted, auto-selected based on time range.
   */
  granularity?: number | null;
  /**
   * Timezone
   * IANA timezone for bucket alignment.
   * @default "UTC"
   */
  timezone?: string;
  /**
   * Metrics
   * Metrics to aggregate from payload_dump.
   */
  metrics?: FeedbackMetricSpec[];
}

/**
 * FeedbackStatsRes
 * Response with time-series feedback statistics.
 */
export interface FeedbackStatsRes {
  /**
   * Start
   * Resolved start time (always UTC, regardless of the requested timezone).
   * @format date-time
   */
  start: string;
  /**
   * End
   * Resolved end time (always UTC, regardless of the requested timezone).
   * @format date-time
   */
  end: string;
  /**
   * Granularity
   * Bucket size used (in seconds)
   */
  granularity: number;
  /**
   * Timezone
   * Timezone used for bucket alignment
   */
  timezone: string;
  /**
   * Buckets
   * Time-bucketed aggregations. Each dict has 'timestamp' (ISO string), 'count' (int), and '{agg}_{slug}' keys for each requested metric+aggregation.
   */
  buckets?: Record<string, any>[];
  /**
   * Window Stats
   * Aggregations over the full query window, keyed by metric slug (e.g. 'output_score'). Each value maps agg name to result.
   */
  window_stats?: Record<string, Record<string, number | null>> | null;
}

/** FileContentReadReq */
export interface FileContentReadReq {
  /** Project Id */
  project_id: string;
  /** Digest */
  digest: string;
}

/** FileCreateRes */
export interface FileCreateRes {
  /** Digest */
  digest: string;
}

/** FilesStatsReq */
export interface FilesStatsReq {
  /** Project Id */
  project_id: string;
}

/** FilesStatsRes */
export interface FilesStatsRes {
  /** Total Size Bytes */
  total_size_bytes: number;
}

/** GenAISpanRef */
export interface GenAISpanRef {
  /** Trace Id */
  trace_id: string;
  /** Span Id */
  span_id: string;
}

/** Geolocation */
export interface Geolocation {
  /**
   * File Index
   * row in CSV file
   */
  file_index: number;
  /**
   * Range Start Int
   * Start of IP range as integer
   */
  range_start_int: number;
  /**
   * Range End Int
   * End of IP range as integer
   */
  range_end_int: number;
  /**
   * Range Start Ip
   * Start of IP range in dotted decimal notation
   */
  range_start_ip: string;
  /**
   * Range End Ip
   * End of IP range in dotted decimal notation
   */
  range_end_ip: string;
  /**
   * Country Code
   * 2-letter country code in ISO 3166-1 Alpha 2 format
   */
  country_code: string;
  /**
   * Country Name
   * Country name, None if could not be determined
   */
  country_name?: string | null;
}

/** GeolocationRes */
export interface GeolocationRes {
  /**
   * Ip
   * Resolved IP address, useful for debugging
   */
  ip: string;
  /** Information about the location of the IP address, None if could not be determined */
  location?: Geolocation | null;
  /**
   * Allowed
   * Whether the IP address is allowed to be used for inference.
   * @default false
   */
  allowed?: boolean;
}

/**
 * GetFieldOperator
 * Access a field on the traced call.
 *
 * Supports dot notation for nested access, e.g. `summary.usage.tokens`.
 *
 * Only works on fields present in the `CallSchema`, including:
 * - Top-level fields like `op_name`, `trace_id`, `started_at`
 * - Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc.
 *
 * Example:
 *     ```
 *     {"$getField": "op_name"}
 *     ```
 */
export interface GetFieldOperator {
  /** $Getfield */
  $getField: string;
}

/**
 * GtOperation
 * Greater than comparison.
 *
 * Example:
 *     ```
 *     {
 *         "$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
 *     }
 *     ```
 */
export interface GtOperation {
  /**
   * $Gt
   * @maxItems 2
   * @minItems 2
   */
  $gt: any[];
}

/**
 * GteOperation
 * Greater than or equal comparison.
 *
 * Example:
 *     ```
 *     {
 *         "$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
 *     }
 *     ```
 */
export interface GteOperation {
  /**
   * $Gte
   * @maxItems 2
   * @minItems 2
   */
  $gte: any[];
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[];
}

/** ImageGenerationCreateReq */
export interface ImageGenerationCreateReq {
  /** Project Id */
  project_id: string;
  inputs: ImageGenerationRequestInputs;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /**
   * Track Llm Call
   * Whether to track this image generation call in the trace server
   * @default true
   */
  track_llm_call?: boolean | null;
}

/** ImageGenerationCreateRes */
export interface ImageGenerationCreateRes {
  /** Response */
  response: Record<string, any>;
  /** Weave Call Id */
  weave_call_id?: string | null;
}

/** ImageGenerationRequestInputs */
export interface ImageGenerationRequestInputs {
  /** Model */
  model: string;
  /** Prompt */
  prompt: string;
  /** N */
  n?: number | null;
}

/**
 * InOperation
 * Membership check.
 *
 * Returns true if the left operand is in the list provided as the second operand.
 *
 * Example:
 *     ```
 *     {
 *         "$in": [
 *             {"$getField": "op_name"},
 *             [{"$literal": "predict"}, {"$literal": "generate"}]
 *         ]
 *     }
 *     ```
 */
export interface InOperation {
  /**
   * $In
   * @maxItems 2
   * @minItems 2
   */
  $in: any[];
}

/**
 * Interleaved
 * Reasoning interleaving support details.
 */
export interface Interleaved {
  /**
   * Field
   * Format identifier for interleaved reasoning.
   */
  field: 'reasoning_content' | 'reasoning_details';
}

/**
 * LLMAggregatedUsage
 * Aggregated usage metrics for a specific LLM.
 */
export interface LLMAggregatedUsage {
  /**
   * Requests
   * @default 0
   */
  requests?: number;
  /**
   * Prompt Tokens
   * @default 0
   */
  prompt_tokens?: number;
  /**
   * Completion Tokens
   * @default 0
   */
  completion_tokens?: number;
  /**
   * Total Tokens
   * @default 0
   */
  total_tokens?: number;
  /**
   * Cache Read Input Tokens
   * @default 0
   */
  cache_read_input_tokens?: number;
  /**
   * Cache Creation Input Tokens
   * @default 0
   */
  cache_creation_input_tokens?: number;
  /** Prompt Tokens Total Cost */
  prompt_tokens_total_cost?: number | null;
  /** Completion Tokens Total Cost */
  completion_tokens_total_cost?: number | null;
  /** Cache Read Input Tokens Total Cost */
  cache_read_input_tokens_total_cost?: number | null;
  /** Cache Creation Input Tokens Total Cost */
  cache_creation_input_tokens_total_cost?: number | null;
}

/** LLMModelDetails */
export interface LLMModelDetails {
  /** Provider */
  provider: string;
  /** Id */
  id: string;
  /** Idplayground */
  idPlayground: string;
  /** Idhuggingface */
  idHuggingFace: string;
  /** Label */
  label: string;
  /** Labelopenrouter */
  labelOpenRouter: string;
  /** Status */
  status: string;
  /** Lifecyclestage */
  lifecycleStage:
    | 'experimental'
    | 'general-availability'
    | 'deprecated'
    | 'retired';
  /** Availablein */
  availableIn: ('cw-prod' | 'cw-qa')[];
  /** Launchedquarter */
  launchedQuarter: string;
  /** Descriptionshort */
  descriptionShort: string;
  /** Descriptionmedium */
  descriptionMedium: string;
  /** Launchdate */
  launchDate: string;
  /** Featurereasoning */
  featureReasoning: boolean;
  /** Featurejsonmode */
  featureJsonMode: boolean;
  /** Featurestructuredoutput */
  featureStructuredOutput: boolean;
  /** Featuretoolcalling */
  featureToolCalling: boolean;
  /** Featurelora */
  featureLoRA: boolean;
  /** Featuretrainableserverlessrl */
  featureTrainableServerlessRL: boolean;
  /** Parametercounttotal */
  parameterCountTotal: number;
  /** Parametercountactive */
  parameterCountActive?: number;
  /** Contextwindow */
  contextWindow: number;
  /** Quantization */
  quantization:
    | 'int4'
    | 'int8'
    | 'fp4'
    | 'fp6'
    | 'fp8'
    | 'fp16'
    | 'bf16'
    | 'fp32';
  /** Pricecentsperbilliontokensinput */
  priceCentsPerBillionTokensInput: number;
  /** Pricecentsperbilliontokenscached */
  priceCentsPerBillionTokensCached: number;
  /** Pricecentsperbilliontokensoutput */
  priceCentsPerBillionTokensOutput: number;
  /** Isavailableopenrouter */
  isAvailableOpenRouter: boolean;
  /** Apistyle */
  apiStyle: string;
  /** Modalities */
  modalities: string[];
  /** Modalitiesinput */
  modalitiesInput: string[];
  /** Modalitiesoutput */
  modalitiesOutput: string[];
  /** Tags */
  tags: string[];
  /** Likeshuggingface */
  likesHuggingFace: number;
  /** Downloadshuggingface */
  downloadsHuggingFace: number;
  /** License */
  license: string;
}

/** LLMUsageSchema */
export interface LLMUsageSchema {
  /** Prompt Tokens */
  prompt_tokens?: number | null;
  /** Input Tokens */
  input_tokens?: number | null;
  /** Completion Tokens */
  completion_tokens?: number | null;
  /** Output Tokens */
  output_tokens?: number | null;
  /** Requests */
  requests?: number | null;
  /** Total Tokens */
  total_tokens?: number | null;
  /** Cache Creation Input Tokens */
  cache_creation_input_tokens?: number | null;
  /** Cache Read Input Tokens */
  cache_read_input_tokens?: number | null;
  [key: string]: any;
}

/**
 * Limit
 * Token limits for a model.
 */
export interface Limit {
  /**
   * Context
   * Maximum context window in tokens.
   */
  context: number;
  /**
   * Input
   * Maximum input tokens.
   */
  input: number;
  /**
   * Output
   * Maximum output tokens.
   */
  output: number;
}

/**
 * LiteralOperation
 * Represents a constant value in the query language.
 *
 * This can be any standard JSON-serializable value.
 *
 * Example:
 *     ```
 *     {"$literal": "predict"}
 *     ```
 */
export interface LiteralOperation {
  /** $Literal */
  $literal:
    | string
    | number
    | boolean
    | Record<string, LiteralOperation>
    | LiteralOperation[]
    | null;
}

/**
 * LtOperation
 * Less than comparison.
 *
 * Example:
 *     ```
 *     {
 *         "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
 *     }
 *     ```
 */
export interface LtOperation {
  /**
   * $Lt
   * @maxItems 2
   * @minItems 2
   */
  $lt: any[];
}

/**
 * LteOperation
 * Less than or equal comparison.
 *
 * Example:
 *     ```
 *     {
 *         "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
 *     }
 *     ```
 */
export interface LteOperation {
  /**
   * $Lte
   * @maxItems 2
   * @minItems 2
   */
  $lte: any[];
}

/**
 * Modalities
 * Supported input and output modalities.
 */
export interface Modalities {
  /**
   * Input
   * Supported input types (e.g. text, image, audio, video, pdf).
   */
  input: string[];
  /**
   * Output
   * Supported output types.
   */
  output: string[];
}

/** ModelCreateBody */
export interface ModelCreateBody {
  /**
   * Name
   * The name of this model. Models with the same name will be versioned together.
   */
  name: string;
  /**
   * Description
   * A description of this model
   */
  description?: string | null;
  /**
   * Source Code
   * Complete source code for the Model class including imports
   */
  source_code: string;
  /**
   * Attributes
   * Additional attributes to be stored with the model
   */
  attributes?: Record<string, any> | null;
}

/** ModelCreateRes */
export interface ModelCreateRes {
  /**
   * Digest
   * The digest of the created model
   */
  digest: string;
  /**
   * Object Id
   * The ID of the created model
   */
  object_id: string;
  /**
   * Version Index
   * The version index of the created model
   */
  version_index: number;
  /**
   * Model Ref
   * Full reference to the created model
   */
  model_ref: string;
}

/** ModelDeleteRes */
export interface ModelDeleteRes {
  /**
   * Num Deleted
   * Number of model versions deleted
   */
  num_deleted: number;
}

/** ModelReadRes */
export interface ModelReadRes {
  /**
   * Object Id
   * The model ID
   */
  object_id: string;
  /**
   * Digest
   * The digest of the model
   */
  digest: string;
  /**
   * Version Index
   * The version index of the object
   */
  version_index: number;
  /**
   * Created At
   * When the model was created
   * @format date-time
   */
  created_at: string;
  /**
   * Name
   * The name of the model
   */
  name: string;
  /**
   * Description
   * Description of the model
   */
  description?: string | null;
  /**
   * Source Code
   * The source code of the model
   */
  source_code: string;
  /**
   * Attributes
   * Additional attributes stored with the model
   */
  attributes?: Record<string, any> | null;
}

/**
 * ModelsDevModel
 * A single model entry in the models.dev schema.
 */
export interface ModelsDevModel {
  /**
   * Id
   * Model identifier used by the AI SDK.
   */
  id: string;
  /**
   * Name
   * Display name.
   */
  name: string;
  /**
   * Description
   * Human-readable description of the model.
   */
  description?: string | null;
  /**
   * Attachment
   * File attachment support.
   */
  attachment: boolean;
  /**
   * Reasoning
   * Chain-of-thought reasoning support.
   */
  reasoning: boolean;
  /**
   * Reasoning Options
   * How reasoning is controlled. Set (possibly to an empty list, meaning always-on) when reasoning is supported; omitted otherwise.
   */
  reasoning_options?:
    | (ReasoningToggle | ReasoningEffortOption | ReasoningBudgetTokens)[]
    | null;
  /**
   * Tool Call
   * Tool calling support.
   */
  tool_call: boolean;
  /**
   * Structured Output
   * Dedicated structured output feature.
   */
  structured_output?: boolean | null;
  /**
   * Temperature
   * Temperature control support.
   */
  temperature?: boolean | null;
  /**
   * Knowledge
   * Knowledge cutoff in YYYY-MM or YYYY-MM-DD format.
   */
  knowledge?: string | null;
  /**
   * Release Date
   * First public release date (YYYY-MM-DD).
   */
  release_date: string;
  /**
   * Last Updated
   * Most recent update date (YYYY-MM-DD).
   */
  last_updated: string;
  /**
   * Open Weights
   * Public weights availability.
   */
  open_weights: boolean;
  /**
   * Status
   * Lifecycle status of the model.
   */
  status?: 'alpha' | 'beta' | 'deprecated' | null;
  /**
   * Interleaved
   * Reasoning interleaving support.
   */
  interleaved?: boolean | Interleaved | null;
  /** Pricing information. */
  cost?: Cost | null;
  /** Token limits. */
  limit?: Limit | null;
  /** Supported input and output modalities. */
  modalities?: Modalities | null;
}

/**
 * ModelsDevProvider
 * A provider entry in the models.dev schema.
 */
export interface ModelsDevProvider {
  /**
   * Id
   * Provider identifier, derived from the folder name.
   */
  id: string;
  /**
   * Name
   * Display name of the provider.
   */
  name: string;
  /**
   * Npm
   * AI SDK package name.
   */
  npm: string;
  /**
   * Env
   * Environment variable keys for authentication.
   */
  env: string[];
  /**
   * Doc
   * Link to provider documentation.
   */
  doc: string;
  /**
   * Api
   * OpenAI-compatible API endpoint. Required only when using @ai-sdk/openai-compatible.
   */
  api?: string | null;
  /**
   * Models
   * Mapping of model id -> model.
   */
  models?: Record<string, ModelsDevModel>;
}

/**
 * NormalizedMessage
 * A single message normalized from any provider format.
 *
 * Maps to ClickHouse ``Tuple(role String, content String, finish_reason String)``.
 *
 * - role: message role (user, assistant, tool, system)
 * - content: plain text for simple messages, or JSON-serialized parts
 *   array for multimodal/structured messages
 * - finish_reason: per-message finish reason (output messages only)
 */
export interface NormalizedMessage {
  /**
   * Role
   * @default ""
   */
  role?: string;
  /** Content */
  content: string;
  /**
   * Finish Reason
   * @default ""
   */
  finish_reason?: string;
}

/**
 * NotOperation
 * Logical NOT. Inverts the condition.
 *
 * Example:
 *     ```
 *     {
 *         "$not": [
 *             {"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}
 *         ]
 *     }
 *     ```
 */
export interface NotOperation {
  /**
   * $Not
   * @maxItems 1
   * @minItems 1
   */
  $not: any[];
}

/** NvidiaHardwareOption */
export interface NvidiaHardwareOption {
  /** Id */
  id: string;
  /** Name */
  name: string;
  /** Type */
  type: string;
  pricing: NvidiaServerlessPricing;
  /** Specs */
  specs?: Record<string, string> | null;
}

/** NvidiaHardwareRes */
export interface NvidiaHardwareRes {
  /** Hardware */
  hardware: NvidiaHardwareOption[];
}

/** NvidiaServerlessPricing */
export interface NvidiaServerlessPricing {
  /** Cents Per Million Input Tokens */
  cents_per_million_input_tokens: number;
  /** Cents Per Million Output Tokens */
  cents_per_million_output_tokens: number;
}

/** ObjAddTagsRes */
export type ObjAddTagsRes = object;

/** ObjCreateReq */
export interface ObjCreateReq {
  obj: ObjSchemaForInsert;
}

/** ObjCreateRes */
export interface ObjCreateRes {
  /** Digest */
  digest: string;
  /** Object Id */
  object_id?: string | null;
}

/** ObjDeleteReq */
export interface ObjDeleteReq {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /**
   * Digests
   * List of digests to delete. If not provided, all digests for the object will be deleted.
   */
  digests?: string[] | null;
}

/** ObjDeleteRes */
export interface ObjDeleteRes {
  /** Num Deleted */
  num_deleted: number;
  /**
   * Deleted Versions
   * Metadata for each deleted object version, with digest aliases resolved to content digests. None when the backing server does not report it.
   */
  deleted_versions?: DeletedObjVersion[] | null;
}

/** ObjQueryReq */
export interface ObjQueryReq {
  /**
   * Project Id
   * The ID of the project to query
   */
  project_id: string;
  /** Filter criteria for the query. See `ObjectVersionFilter` */
  filter?: ObjectVersionFilter | null;
  /**
   * Limit
   * Maximum number of results to return
   */
  limit?: number | null;
  /**
   * Offset
   * Number of results to skip before returning
   */
  offset?: number | null;
  /**
   * Sort By
   * Sorting criteria for the query results. Currently only supports 'object_id' and 'created_at'.
   */
  sort_by?: SortBy[] | null;
  /**
   * Metadata Only
   * If true, the `val` column is not read from the database and is empty.All other fields are returned.
   * @default false
   */
  metadata_only?: boolean | null;
  /**
   * Include Storage Size
   * If true, the `size_bytes` column is returned.
   * @default false
   */
  include_storage_size?: boolean | null;
  /**
   * Include Tags And Aliases
   * If true, tags and aliases are fetched and included in the response.
   * @default false
   */
  include_tags_and_aliases?: boolean | null;
}

/** ObjQueryRes */
export interface ObjQueryRes {
  /** Objs */
  objs: ObjSchema[];
}

/** ObjReadReq */
export interface ObjReadReq {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /** Digest */
  digest: string;
  /**
   * Metadata Only
   * If true, the `val` column is not read from the database and is empty.All other fields are returned.
   * @default false
   */
  metadata_only?: boolean | null;
  /**
   * Include Tags And Aliases
   * If true, tags and aliases are fetched and included in the response.
   * @default false
   */
  include_tags_and_aliases?: boolean | null;
}

/** ObjReadRes */
export interface ObjReadRes {
  obj: ObjSchema;
}

/**
 * ObjRemoveAliasesBody
 * Request body for removing aliases (object_id comes from path).
 */
export interface ObjRemoveAliasesBody {
  /** Project Id */
  project_id: string;
  /** Aliases */
  aliases: string[];
}

/** ObjRemoveAliasesRes */
export type ObjRemoveAliasesRes = object;

/** ObjRemoveTagsRes */
export type ObjRemoveTagsRes = object;

/** ObjSchema */
export interface ObjSchema {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Deleted At */
  deleted_at?: string | null;
  /** Digest */
  digest: string;
  /** Version Index */
  version_index: number;
  /** Is Latest */
  is_latest: number;
  /** Kind */
  kind: string;
  /** Base Object Class */
  base_object_class: string | null;
  /** Leaf Object Class */
  leaf_object_class?: string | null;
  /** Val */
  val: any;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /** Size Bytes */
  size_bytes?: number | null;
  /** Tags */
  tags?: string[] | null;
  /** Aliases */
  aliases?: string[] | null;
}

/** ObjSchemaForInsert */
export interface ObjSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /** Val */
  val: any;
  /** Builtin Object Class */
  builtin_object_class?: string | null;
  /**
   * Set Base Object Class
   * @deprecated
   */
  set_base_object_class?: string | null;
  /**
   * Expected Digest
   * Client-computed digest for server-side validation. If provided, the server will verify it matches the server-computed digest.
   */
  expected_digest?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/**
 * ObjSetAliasesBody
 * Request body for setting aliases (object_id comes from path).
 */
export interface ObjSetAliasesBody {
  /** Project Id */
  project_id: string;
  /** Digest */
  digest: string;
  /** Aliases */
  aliases: string[];
}

/** ObjSetAliasesRes */
export type ObjSetAliasesRes = object;

/**
 * ObjTagsBody
 * Request body for adding/removing tags (object_id and digest come from path).
 */
export interface ObjTagsBody {
  /** Project Id */
  project_id: string;
  /** Tags */
  tags: string[];
}

/** ObjectVersionFilter */
export interface ObjectVersionFilter {
  /**
   * Base Object Classes
   * Filter objects by their base classes
   */
  base_object_classes?: string[] | null;
  /**
   * Exclude Base Object Classes
   * Exclude objects by their base classes
   */
  exclude_base_object_classes?: string[] | null;
  /**
   * Leaf Object Classes
   * Filter objects by their leaf classes
   */
  leaf_object_classes?: string[] | null;
  /**
   * Object Ids
   * Filter objects by their IDs
   */
  object_ids?: string[] | null;
  /**
   * Is Op
   * Filter objects based on whether they are weave.ops or not. `True` will only return ops, `False` will return non-ops, and `None` will return all objects
   */
  is_op?: boolean | null;
  /**
   * Latest Only
   * If True, return only the latest version of each object. `False` and `None` will return all versions
   */
  latest_only?: boolean | null;
  /**
   * Tags
   * Filter object versions that have any of the specified tags
   */
  tags?: string[] | null;
  /**
   * Aliases
   * Filter objects that have any of the specified aliases
   */
  aliases?: string[] | null;
}

/**
 * OpCreateBody
 * Request body for creating an Op object via REST API.
 *
 * This model excludes project_id since it comes from the URL path in RESTful endpoints.
 */
export interface OpCreateBody {
  /**
   * Name
   * The name of this op. Ops with the same name will be versioned together.
   */
  name?: string | null;
  /**
   * Source Code
   * Complete source code for this op, including imports
   */
  source_code?: string | null;
}

/**
 * OpCreateRes
 * Response model for creating an Op object.
 */
export interface OpCreateRes {
  /**
   * Digest
   * The digest of the created op
   */
  digest: string;
  /**
   * Object Id
   * The ID of the created op
   */
  object_id: string;
  /**
   * Version Index
   * The version index of the created op
   */
  version_index: number;
}

/** OpDeleteRes */
export interface OpDeleteRes {
  /**
   * Num Deleted
   * Number of op versions deleted from this op
   */
  num_deleted: number;
}

/**
 * OpReadRes
 * Response model for reading an Op object.
 *
 * The code field contains the actual source code of the op.
 */
export interface OpReadRes {
  /**
   * Object Id
   * The op ID
   */
  object_id: string;
  /**
   * Digest
   * The digest of the op
   */
  digest: string;
  /**
   * Version Index
   * The version index of this op
   */
  version_index: number;
  /**
   * Created At
   * When this op was created
   * @format date-time
   */
  created_at: string;
  /**
   * Code
   * The actual op source code
   */
  code: string;
}

/**
 * OrOperation
 * Logical OR. At least one condition must be true.
 *
 * Example:
 *     ```
 *     {
 *         "$or": [
 *             {"$eq": [{"$getField": "op_name"}, {"$literal": "a"}]},
 *             {"$eq": [{"$getField": "op_name"}, {"$literal": "b"}]}
 *         ]
 *     }
 *     ```
 */
export interface OrOperation {
  /** $Or */
  $or: (
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
    | ContainsOperation
  )[];
}

/**
 * PredictionCreateBody
 * Request body for creating a Prediction via REST API.
 *
 * This model excludes project_id since it comes from the URL path in RESTful endpoints.
 */
export interface PredictionCreateBody {
  /**
   * Model
   * The model reference (weave:// URI)
   */
  model: string;
  /**
   * Inputs
   * The inputs to the prediction
   */
  inputs: Record<string, any>;
  /**
   * Output
   * The output of the prediction
   */
  output: any;
  /**
   * Evaluation Run Id
   * Optional evaluation run ID to link this prediction as a child call
   */
  evaluation_run_id?: string | null;
  /**
   * Genai Span Ref
   * Optional GenAI span reference(s) produced by this prediction.
   */
  genai_span_ref?: GenAISpanRef[] | null;
}

/** PredictionCreateRes */
export interface PredictionCreateRes {
  /**
   * Prediction Id
   * The prediction ID
   */
  prediction_id: string;
}

/** PredictionDeleteRes */
export interface PredictionDeleteRes {
  /**
   * Num Deleted
   * Number of predictions deleted
   */
  num_deleted: number;
}

/** PredictionFinishRes */
export interface PredictionFinishRes {
  /**
   * Success
   * Whether the prediction was finished successfully
   */
  success: boolean;
}

/** PredictionReadRes */
export interface PredictionReadRes {
  /**
   * Prediction Id
   * The prediction ID
   */
  prediction_id: string;
  /**
   * Model
   * The model reference (weave:// URI)
   */
  model: string;
  /**
   * Inputs
   * The inputs to the prediction
   */
  inputs: Record<string, any>;
  /**
   * Output
   * The output of the prediction
   */
  output: any;
  /**
   * Evaluation Run Id
   * Evaluation run ID if this prediction is linked to one
   */
  evaluation_run_id?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/**
 * Pricing
 * All pricing values are in USD per 1 token.
 *
 * Pricing fields are in string format to avoid floating point precision issues.
 */
export interface Pricing {
  /** Prompt */
  prompt: string;
  /** Completion */
  completion: string;
  /** Image */
  image: string;
  /** Request */
  request: string;
  /** Input Cache Read */
  input_cache_read: string;
}

/** ProjectsInfoReq */
export interface ProjectsInfoReq {
  /**
   * Project Ids
   * External project IDs in 'entity/project' format.
   */
  project_ids: string[];
}

/** ProjectsInfoRes */
export interface ProjectsInfoRes {
  /**
   * External Project Id
   * External project ID in 'entity/project' format.
   */
  external_project_id: string;
  /**
   * Internal Project Id
   * Internal project ID.
   */
  internal_project_id: string;
}

/** Query */
export interface Query {
  /** $Expr */
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

/** RatingCondition */
export interface RatingCondition {
  /** Scorer Key */
  scorer_key: string;
  /** Op */
  op: 'gte' | 'gt' | 'lte' | 'lt' | 'eq';
  /** Value */
  value: number;
}

/**
 * ReasoningBudgetTokens
 * Reasoning is controlled via a token budget.
 */
export interface ReasoningBudgetTokens {
  /**
   * Type
   * @default "budget_tokens"
   */
  type?: 'budget_tokens';
  /**
   * Min
   * Minimum reasoning budget.
   */
  min?: number | null;
  /**
   * Max
   * Maximum reasoning budget.
   */
  max?: number | null;
}

/**
 * ReasoningEffortOption
 * Reasoning effort can be selected from a set of levels.
 */
export interface ReasoningEffortOption {
  /**
   * Type
   * @default "effort"
   */
  type?: 'effort';
  /**
   * Values
   * Accepted effort levels (null denotes an implicit default).
   */
  values: (
    | 'none'
    | 'minimal'
    | 'low'
    | 'medium'
    | 'high'
    | 'xhigh'
    | 'max'
    | 'default'
    | null
  )[];
}

/**
 * ReasoningToggle
 * Reasoning can be turned on or off.
 */
export interface ReasoningToggle {
  /**
   * Type
   * @default "toggle"
   */
  type?: 'toggle';
}

/** RefsReadBatchReq */
export interface RefsReadBatchReq {
  /** Refs */
  refs: string[];
}

/** RefsReadBatchRes */
export interface RefsReadBatchRes {
  /** Vals */
  vals: any[];
}

/**
 * RescoreReq
 * Full rescore request including server-set fields.
 */
export interface RescoreReq {
  /**
   * Source Evaluation Run Id
   * The evaluation run whose predictions will be rescored
   */
  source_evaluation_run_id: string;
  /**
   * Scorer Refs
   * Scorer references (weave:// URIs) to apply; must be non-empty
   * @minItems 1
   */
  scorer_refs: string[];
  /** Project Id */
  project_id: string;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/**
 * RescoreRes
 * Response for a rescore request.
 */
export interface RescoreRes {
  /**
   * Call Id
   * Call ID for /evaluations/status polling
   */
  call_id: string;
  /**
   * Evaluation Run Id
   * The newly created EvaluationRun ID
   */
  evaluation_run_id: string;
}

/** RouterOpenRouterModel */
export interface RouterOpenRouterModel {
  /** Id */
  id: string;
  /** Hugging Face Id */
  hugging_face_id: string;
  /** Name */
  name: string;
  /** Created */
  created: number;
  /** Input Modalities */
  input_modalities: string[];
  /** Output Modalities */
  output_modalities: string[];
  /** Quantization */
  quantization:
    | 'int4'
    | 'int8'
    | 'fp4'
    | 'fp6'
    | 'fp8'
    | 'fp16'
    | 'bf16'
    | 'fp32';
  /** Context Length */
  context_length: number;
  /** Max Output Length */
  max_output_length: number;
  /**
   * All pricing values are in USD per 1 token.
   *
   * Pricing fields are in string format to avoid floating point precision issues.
   */
  pricing: Pricing;
  /** Supported Sampling Parameters */
  supported_sampling_parameters: (
    | 'temperature'
    | 'top_p'
    | 'top_k'
    | 'repetition_penalty'
    | 'frequency_penalty'
    | 'presence_penalty'
    | 'stop'
    | 'seed'
  )[];
  /** Supported Features */
  supported_features: (
    | 'tools'
    | 'json_mode'
    | 'structured_outputs'
    | 'web_search'
    | 'reasoning'
  )[];
  /** Datacenters */
  datacenters: Datacenter[];
  /**
   * Deprecation Date
   * Date when the model is deprecated (YYYY-MM-DD). Omitted from output if not set.
   */
  deprecation_date?: string | null;
}

/** RouterOpenRouterModelsRes */
export interface RouterOpenRouterModelsRes {
  /** Data */
  data: RouterOpenRouterModel[];
}

/**
 * ScoreCreateBody
 * Request body for creating a Score via REST API.
 *
 * This model excludes project_id since it comes from the URL path in RESTful endpoints.
 */
export interface ScoreCreateBody {
  /**
   * Prediction Id
   * The prediction ID
   */
  prediction_id: string;
  /**
   * Scorer
   * The scorer reference (weave:// URI)
   */
  scorer: string;
  /**
   * Value
   * The raw output of the scorer
   */
  value: any;
  /**
   * Evaluation Run Id
   * Optional evaluation run ID to link this score as a child call
   */
  evaluation_run_id?: string | null;
}

/** ScoreCreateRes */
export interface ScoreCreateRes {
  /**
   * Score Id
   * The score ID
   */
  score_id: string;
}

/** ScoreDeleteRes */
export interface ScoreDeleteRes {
  /**
   * Num Deleted
   * Number of scores deleted
   */
  num_deleted: number;
}

/** ScoreReadRes */
export interface ScoreReadRes {
  /**
   * Score Id
   * The score ID
   */
  score_id: string;
  /**
   * Scorer
   * The scorer reference (weave:// URI)
   */
  scorer: string;
  /**
   * Value
   * The raw output of the scorer
   */
  value: any;
  /**
   * Evaluation Run Id
   * Evaluation run ID if this score is linked to one
   */
  evaluation_run_id?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** ScorerCreateBody */
export interface ScorerCreateBody {
  /**
   * Name
   * The name of this scorer.  Scorers with the same name will be versioned together.
   */
  name: string;
  /**
   * Description
   * A description of this scorer
   */
  description?: string | null;
  /**
   * Op Source Code
   * Complete source code for the Scorer.score op including imports
   */
  op_source_code: string;
}

/** ScorerCreateRes */
export interface ScorerCreateRes {
  /**
   * Digest
   * The digest of the created scorer
   */
  digest: string;
  /**
   * Object Id
   * The ID of the created scorer
   */
  object_id: string;
  /**
   * Version Index
   * The version index of the created scorer
   */
  version_index: number;
  /**
   * Scorer
   * Full reference to the created scorer
   */
  scorer: string;
}

/** ScorerDeleteRes */
export interface ScorerDeleteRes {
  /**
   * Num Deleted
   * Number of scorer versions deleted
   */
  num_deleted: number;
}

/** ScorerReadRes */
export interface ScorerReadRes {
  /**
   * Object Id
   * The scorer ID
   */
  object_id: string;
  /**
   * Digest
   * The digest of the scorer
   */
  digest: string;
  /**
   * Version Index
   * The version index of the object
   */
  version_index: number;
  /**
   * Created At
   * When the scorer was created
   * @format date-time
   */
  created_at: string;
  /**
   * Name
   * The name of the scorer
   */
  name: string;
  /**
   * Description
   * Description of the scorer
   */
  description?: string | null;
  /**
   * Score Op
   * The Scorer.score op reference
   */
  score_op: string;
}

/** ServerInfoRes */
export interface ServerInfoRes {
  /** Min Required Weave Python Version */
  min_required_weave_python_version: string;
  /** Trace Server Version */
  trace_server_version: string;
}

/**
 * SizeOperation
 * Return the number of elements in a collection or characters in a string.
 *
 * Example:
 *     ```
 *     {"$size": {"$getField": "scorer_tags"}}
 *     ```
 */
export interface SizeOperation {
  /** $Size */
  $size:
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
}

/** SortBy */
export interface SortBy {
  /** Field */
  field: string;
  /** Direction */
  direction: 'asc' | 'desc';
}

/** StartedCallSchemaForInsert */
export interface StartedCallSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Id */
  id?: string | null;
  /** Op Name */
  op_name: string;
  /** Display Name */
  display_name?: string | null;
  /** Trace Id */
  trace_id?: string | null;
  /** Parent Id */
  parent_id?: string | null;
  /** Thread Id */
  thread_id?: string | null;
  /** Turn Id */
  turn_id?: string | null;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
  /** Attributes */
  attributes: Record<string, any>;
  /** Inputs */
  inputs: Record<string, any>;
  /** Otel Dump */
  otel_dump?: Record<string, any> | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
  /** Wb Run Step */
  wb_run_step?: number | null;
}

/** SummaryInsertMap */
export interface SummaryInsertMap {
  /** Usage */
  usage?: Record<string, LLMUsageSchema>;
  /** Status Counts */
  status_counts?: Partial<Record<TraceStatus, number>>;
  [key: string]: any;
}

/** TableAppendSpec */
export interface TableAppendSpec {
  append: TableAppendSpecPayload;
}

/** TableAppendSpecPayload */
export interface TableAppendSpecPayload {
  /** Row */
  row: Record<string, any>;
}

/** TableCreateFromDigestsReq */
export interface TableCreateFromDigestsReq {
  /** Project Id */
  project_id: string;
  /** Row Digests */
  row_digests: string[];
  /**
   * Expected Digest
   * Client-computed table digest for server-side validation.
   */
  expected_digest?: string | null;
}

/** TableCreateFromDigestsRes */
export interface TableCreateFromDigestsRes {
  /** Digest */
  digest: string;
}

/** TableCreateReq */
export interface TableCreateReq {
  table: TableSchemaForInsert;
}

/** TableCreateRes */
export interface TableCreateRes {
  /** Digest */
  digest: string;
  /**
   * Row Digests
   * The digests of the rows that were created
   */
  row_digests?: string[];
}

/** TableInsertSpec */
export interface TableInsertSpec {
  insert: TableInsertSpecPayload;
}

/** TableInsertSpecPayload */
export interface TableInsertSpecPayload {
  /** Index */
  index: number;
  /** Row */
  row: Record<string, any>;
}

/** TablePopSpec */
export interface TablePopSpec {
  pop: TablePopSpecPayload;
}

/** TablePopSpecPayload */
export interface TablePopSpecPayload {
  /** Index */
  index: number;
}

/** TableQueryReq */
export interface TableQueryReq {
  /**
   * Project Id
   * The ID of the project
   */
  project_id: string;
  /**
   * Digest
   * The digest of the table to query
   */
  digest: string;
  /** Optional filter to apply to the query. See `TableRowFilter` for more details. */
  filter?: TableRowFilter | null;
  /**
   * Limit
   * Maximum number of rows to return
   */
  limit?: number | null;
  /**
   * Offset
   * Number of rows to skip before starting to return rows
   */
  offset?: number | null;
  /**
   * Sort By
   * List of fields to sort by. Fields can be dot-separated to access dictionary values. No sorting uses the default table order (insertion order).
   */
  sort_by?: SortBy[] | null;
}

/** TableQueryRes */
export interface TableQueryRes {
  /** Rows */
  rows: TableRowSchema[];
}

/** TableQueryStatsBatchReq */
export interface TableQueryStatsBatchReq {
  /**
   * Project Id
   * The ID of the project
   */
  project_id: string;
  /**
   * Digests
   * The digests of the tables to query
   * @default []
   */
  digests?: string[] | null;
  /**
   * Include Storage Size
   * If true, the `storage_size_bytes` column is returned.
   * @default false
   */
  include_storage_size?: boolean | null;
}

/** TableQueryStatsBatchRes */
export interface TableQueryStatsBatchRes {
  /** Tables */
  tables: TableStatsRow[];
}

/** TableQueryStatsReq */
export interface TableQueryStatsReq {
  /**
   * Project Id
   * The ID of the project
   */
  project_id: string;
  /**
   * Digest
   * The digest of the table to query
   */
  digest: string;
}

/** TableQueryStatsRes */
export interface TableQueryStatsRes {
  /** Count */
  count: number;
}

/** TableRowFilter */
export interface TableRowFilter {
  /**
   * Row Digests
   * List of row digests to filter by
   */
  row_digests?: string[] | null;
}

/** TableRowSchema */
export interface TableRowSchema {
  /** Digest */
  digest: string;
  /** Val */
  val: any;
  /** Original Index */
  original_index?: number | null;
}

/** TableSchemaForInsert */
export interface TableSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Rows */
  rows: Record<string, any>[];
  /**
   * Expected Digest
   * Client-computed table digest for server-side validation.
   */
  expected_digest?: string | null;
}

/** TableStatsRow */
export interface TableStatsRow {
  /** Count */
  count: number;
  /** Digest */
  digest: string;
  /** Storage Size Bytes */
  storage_size_bytes?: number | null;
}

/** TableUpdateReq */
export interface TableUpdateReq {
  /** Project Id */
  project_id: string;
  /** Base Digest */
  base_digest: string;
  /** Updates */
  updates: (TableAppendSpec | TablePopSpec | TableInsertSpec)[];
}

/** TableUpdateRes */
export interface TableUpdateRes {
  /** Digest */
  digest: string;
  /**
   * Updated Row Digests
   * The digests of the rows that were updated
   */
  updated_row_digests?: string[];
}

/** TagsListRes */
export interface TagsListRes {
  /** Tags */
  tags: string[];
}

/** ThreadsQueryFilter */
export interface ThreadsQueryFilter {
  /**
   * After Datetime
   * Only include threads with start_time after this timestamp
   */
  after_datetime?: string | null;
  /**
   * Before Datetime
   * Only include threads with last_updated before this timestamp
   */
  before_datetime?: string | null;
  /**
   * Thread Ids
   * Only include threads with thread_ids in this list
   */
  thread_ids?: string[] | null;
}

/**
 * ThreadsQueryReq
 * Query threads with aggregated statistics based on turn calls only.
 *
 * Turn calls are the immediate children of thread contexts (where call.id == turn_id).
 * This provides meaningful conversation-level statistics rather than including all
 * nested implementation details.
 */
export interface ThreadsQueryReq {
  /**
   * Project Id
   * The ID of the project
   */
  project_id: string;
  /** Filter criteria for the threads query */
  filter?: ThreadsQueryFilter | null;
  /**
   * Limit
   * Maximum number of threads to return
   */
  limit?: number | null;
  /**
   * Offset
   * Number of threads to skip
   */
  offset?: number | null;
  /**
   * Sort By
   * Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count', 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.
   */
  sort_by?: SortBy[] | null;
}

/**
 * TraceUsageReq
 * Request to compute per-call usage for a trace, with descendant rollup.
 *
 * This endpoint returns usage metrics for each call in the trace, where each
 * call's metrics include the sum of its own usage plus all descendants' usage.
 * Use this for trace view where you want to see rolled-up metrics per call.
 *
 * Note: All matching calls are loaded into memory for aggregation. For very large
 * result sets (>10k calls), consider using more specific filters or pagination
 * at the application layer.
 */
export interface TraceUsageReq {
  /** Project Id */
  project_id: string;
  /** Filter to select calls. Typically use trace_ids to get all calls in a trace. */
  filter?: CallsFilter | null;
  /** Additional query conditions for filtering calls. */
  query?: Query | null;
  /**
   * Include Costs
   * If true, include cost calculations in the usage.
   * @default false
   */
  include_costs?: boolean;
  /**
   * Limit
   * Maximum number of calls to process. Acts as a safety limit to prevent unbounded memory usage.
   * @default 10000
   */
  limit?: number;
}

/**
 * TraceUsageRes
 * Response with per-call usage metrics (each includes descendant contributions).
 */
export interface TraceUsageRes {
  /** Call Usage */
  call_usage?: Record<string, Record<string, LLMAggregatedUsage>>;
  /** Unfinished Call Ids */
  unfinished_call_ids?: string[];
}

/**
 * UsageMetricSpec
 * Specification for a usage metric to aggregate (grouped by model).
 */
export interface UsageMetricSpec {
  /**
   * Metric
   * Metric to aggregate. Token metrics are normalized across providers.
   */
  metric:
    | 'input_tokens'
    | 'output_tokens'
    | 'total_tokens'
    | 'cache_read_input_tokens'
    | 'cache_creation_input_tokens'
    | 'input_cost'
    | 'output_cost'
    | 'total_cost';
  /**
   * Aggregations
   * Basic aggregation functions to apply
   * @default ["sum"]
   */
  aggregations?: AggregationType[];
  /**
   * Percentiles
   * Percentile values to compute (0-100). E.g., [50, 95, 99] for p50, p95, p99
   * @default []
   */
  percentiles?: number[];
}

/** ValidationError */
export interface ValidationError {
  /** Location */
  loc: (string | number)[];
  /** Message */
  msg: string;
  /** Error Type */
  type: string;
}

/** CustomRuntimeApplyBody */
export interface CustomRuntimeApplyBody {
  /**
   * Base Url
   * Public OpenAI-compatible endpoint base URL
   */
  base_url: string;
  /**
   * Api Key Secret
   * Team secret name used as the endpoint API key; never the secret value
   */
  api_key_secret?: string | null;
  /**
   * Headers
   * Literal headers forwarded to the endpoint
   */
  headers?: Record<string, string>;
  /**
   * Runtime Ids
   * Complete desired list of IDs exposed by the endpoint
   */
  runtime_ids: CustomRuntimeID[];
}

/** CustomRuntimeApplyRes */
export interface CustomRuntimeApplyRes {
  /**
   * Name
   * Stable custom runtime name
   */
  name: string;
  /** Base Url */
  base_url: string;
  /** Api Key Secret */
  api_key_secret: string | null;
  /** Headers */
  headers: Record<string, string>;
  /** Runtime Ids */
  runtime_ids: CustomRuntimeIDRes[];
}

/** CustomRuntimeID */
export interface CustomRuntimeID {
  /**
   * Id
   * Value sent in the OpenAI-compatible request model field
   */
  id: string;
  /**
   * Max Tokens
   * Maximum tokens supported by this runtime ID
   * @exclusiveMin 0
   * @default 4096
   */
  max_tokens?: number;
}

/** CustomRuntimeIDRes */
export interface CustomRuntimeIDRes {
  /**
   * Id
   * Value sent in the OpenAI-compatible request model field
   */
  id: string;
  /**
   * Max Tokens
   * Maximum tokens supported by this runtime ID
   * @exclusiveMin 0
   * @default 4096
   */
  max_tokens?: number;
  /** Playground Id */
  playground_id: string;
}

export type QueryParamsType = Record<string | number, any>;
export type ResponseFormat = keyof Omit<Body, 'body' | 'bodyUsed'>;

export interface FullRequestParams extends Omit<RequestInit, 'body'> {
  /** set parameter to `true` for call `securityWorker` for this request */
  secure?: boolean;
  /** request path */
  path: string;
  /** content type of request body */
  type?: ContentType;
  /** query params */
  query?: QueryParamsType;
  /** format of response (i.e. response.json() -> format: "json") */
  format?: ResponseFormat;
  /** request body */
  body?: unknown;
  /** base url */
  baseUrl?: string;
  /** request cancellation token */
  cancelToken?: CancelToken;
}

export type RequestParams = Omit<
  FullRequestParams,
  'body' | 'method' | 'query' | 'path'
>;

export interface ApiConfig<SecurityDataType = unknown> {
  baseUrl?: string;
  baseApiParams?: Omit<RequestParams, 'baseUrl' | 'cancelToken' | 'signal'>;
  securityWorker?: (
    securityData: SecurityDataType | null
  ) => Promise<RequestParams | void> | RequestParams | void;
  customFetch?: typeof fetch;
}

export interface HttpResponse<D extends unknown, E extends unknown = unknown>
  extends Response {
  data: D;
  error: E;
}

type CancelToken = Symbol | string | number;

export enum ContentType {
  Json = 'application/json',
  JsonApi = 'application/vnd.api+json',
  FormData = 'multipart/form-data',
  UrlEncoded = 'application/x-www-form-urlencoded',
  Text = 'text/plain',
}

export class HttpClient<SecurityDataType = unknown> {
  public baseUrl: string = '';
  private securityData: SecurityDataType | null = null;
  private securityWorker?: ApiConfig<SecurityDataType>['securityWorker'];
  private abortControllers = new Map<CancelToken, AbortController>();
  private customFetch = (...fetchParams: Parameters<typeof fetch>) =>
    fetch(...fetchParams);

  private baseApiParams: RequestParams = {
    credentials: 'same-origin',
    headers: {},
    redirect: 'follow',
    referrerPolicy: 'no-referrer',
  };

  constructor(apiConfig: ApiConfig<SecurityDataType> = {}) {
    Object.assign(this, apiConfig);
  }

  public setSecurityData = (data: SecurityDataType | null) => {
    this.securityData = data;
  };

  protected encodeQueryParam(key: string, value: any) {
    const encodedKey = encodeURIComponent(key);
    return `${encodedKey}=${encodeURIComponent(typeof value === 'number' ? value : `${value}`)}`;
  }

  protected addQueryParam(query: QueryParamsType, key: string) {
    return this.encodeQueryParam(key, query[key]);
  }

  protected addArrayQueryParam(query: QueryParamsType, key: string) {
    const value = query[key];
    return value.map((v: any) => this.encodeQueryParam(key, v)).join('&');
  }

  protected toQueryString(rawQuery?: QueryParamsType): string {
    const query = rawQuery || {};
    const keys = Object.keys(query).filter(
      key => 'undefined' !== typeof query[key]
    );
    return keys
      .map(key =>
        Array.isArray(query[key])
          ? this.addArrayQueryParam(query, key)
          : this.addQueryParam(query, key)
      )
      .join('&');
  }

  protected addQueryParams(rawQuery?: QueryParamsType): string {
    const queryString = this.toQueryString(rawQuery);
    return queryString ? `?${queryString}` : '';
  }

  private contentFormatters: Record<ContentType, (input: any) => any> = {
    [ContentType.Json]: (input: any) =>
      input !== null && (typeof input === 'object' || typeof input === 'string')
        ? JSON.stringify(input)
        : input,
    [ContentType.JsonApi]: (input: any) =>
      input !== null && (typeof input === 'object' || typeof input === 'string')
        ? JSON.stringify(input)
        : input,
    [ContentType.Text]: (input: any) =>
      input !== null && typeof input !== 'string'
        ? JSON.stringify(input)
        : input,
    [ContentType.FormData]: (input: any) => {
      if (input instanceof FormData) {
        return input;
      }

      return Object.keys(input || {}).reduce((formData, key) => {
        const property = input[key];
        formData.append(
          key,
          property instanceof Blob
            ? property
            : typeof property === 'object' && property !== null
              ? JSON.stringify(property)
              : `${property}`
        );
        return formData;
      }, new FormData());
    },
    [ContentType.UrlEncoded]: (input: any) => this.toQueryString(input),
  };

  protected mergeRequestParams(
    params1: RequestParams,
    params2?: RequestParams
  ): RequestParams {
    return {
      ...this.baseApiParams,
      ...params1,
      ...(params2 || {}),
      headers: {
        ...(this.baseApiParams.headers || {}),
        ...(params1.headers || {}),
        ...((params2 && params2.headers) || {}),
      },
    };
  }

  protected createAbortSignal = (
    cancelToken: CancelToken
  ): AbortSignal | undefined => {
    if (this.abortControllers.has(cancelToken)) {
      const abortController = this.abortControllers.get(cancelToken);
      if (abortController) {
        return abortController.signal;
      }
      return void 0;
    }

    const abortController = new AbortController();
    this.abortControllers.set(cancelToken, abortController);
    return abortController.signal;
  };

  public abortRequest = (cancelToken: CancelToken) => {
    const abortController = this.abortControllers.get(cancelToken);

    if (abortController) {
      abortController.abort();
      this.abortControllers.delete(cancelToken);
    }
  };

  public request = async <T = any, E = any>({
    body,
    secure,
    path,
    type,
    query,
    format,
    baseUrl,
    cancelToken,
    ...params
  }: FullRequestParams): Promise<HttpResponse<T, E>> => {
    const secureParams =
      ((typeof secure === 'boolean' ? secure : this.baseApiParams.secure) &&
        this.securityWorker &&
        (await this.securityWorker(this.securityData))) ||
      {};
    const requestParams = this.mergeRequestParams(params, secureParams);
    const queryString = query && this.toQueryString(query);
    const payloadFormatter = this.contentFormatters[type || ContentType.Json];
    const responseFormat = format || requestParams.format;

    return this.customFetch(
      `${baseUrl || this.baseUrl || ''}${path}${queryString ? `?${queryString}` : ''}`,
      {
        ...requestParams,
        headers: {
          ...(requestParams.headers || {}),
          ...(type && type !== ContentType.FormData
            ? {'Content-Type': type}
            : {}),
        },
        signal:
          (cancelToken
            ? this.createAbortSignal(cancelToken)
            : requestParams.signal) || null,
        body:
          typeof body === 'undefined' || body === null
            ? null
            : payloadFormatter(body),
      }
    ).then(async response => {
      const r = response as HttpResponse<T, E>;
      r.data = null as unknown as T;
      r.error = null as unknown as E;

      const responseToParse = responseFormat ? response.clone() : response;
      const data = !responseFormat
        ? r
        : await responseToParse[responseFormat]()
            .then(data => {
              if (r.ok) {
                r.data = data;
              } else {
                r.error = data;
              }
              return r;
            })
            .catch(e => {
              r.error = e;
              return r;
            });

      if (cancelToken) {
        this.abortControllers.delete(cancelToken);
      }

      if (!response.ok) throw data;
      return data;
    });
  };
}

/**
 * @title FastAPI
 * @version 0.1.0
 */
export class Api<
  SecurityDataType extends unknown,
> extends HttpClient<SecurityDataType> {
  health = {
    /**
     * No description
     *
     * @tags Service
     * @name ReadRootHealthGet
     * @summary Read Root
     * @request GET:/health
     */
    readRootHealthGet: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/health`,
        method: 'GET',
        format: 'json',
        ...params,
      }),
  };
  version = {
    /**
     * No description
     *
     * @tags Service
     * @name ReadVersionVersionGet
     * @summary Read Version
     * @request GET:/version
     */
    readVersionVersionGet: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/version`,
        method: 'GET',
        format: 'json',
        ...params,
      }),
  };
  geolocate = {
    /**
     * @description Lookup the geographic location of a user based on their IP address. This API exists for debugging purposes and may not be available in the future.
     *
     * @tags Service
     * @name GetCallerLocationGeolocateGet
     * @summary Get Caller Location
     * @request GET:/geolocate
     */
    getCallerLocationGeolocateGet: (
      query?: {
        /**
         * Ip
         * IP address to geolocate, defaults to client IP address
         */
        ip?: string | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<GeolocationRes, HTTPValidationError>({
        path: `/geolocate`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),
  };
  serverInfo = {
    /**
     * No description
     *
     * @tags Service
     * @name ServerInfoServerInfoGet
     * @summary Server Info
     * @request GET:/server_info
     */
    serverInfoServerInfoGet: (params: RequestParams = {}) =>
      this.request<ServerInfoRes, any>({
        path: `/server_info`,
        method: 'GET',
        format: 'json',
        ...params,
      }),
  };
  otel = {
    /**
     * No description
     *
     * @tags OpenTelemetry
     * @name ExportTraceOtelV1TracesPost
     * @summary Export Trace
     * @request POST:/otel/v1/traces
     */
    exportTraceOtelV1TracesPost: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/otel/v1/traces`,
        method: 'POST',
        format: 'json',
        ...params,
      }),
  };
  agents = {
    /**
     * @description Ingest OTel spans into the GenAI observability system.
     *
     * @tags Agents
     * @name ExportGenaiTraceAgentsOtelV1TracesPost
     * @summary Export Genai Trace
     * @request POST:/agents/otel/v1/traces
     */
    exportGenaiTraceAgentsOtelV1TracesPost: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/agents/otel/v1/traces`,
        method: 'POST',
        format: 'json',
        ...params,
      }),

    /**
     * @description Query agent spans, either as raw rows or grouped aggregates.
     *
     * @tags Agents
     * @name GenaiSpansQueryAgentsSpansQueryPost
     * @summary Genai Spans Query
     * @request POST:/agents/spans/query
     */
    genaiSpansQueryAgentsSpansQueryPost: (
      data: AgentSpansQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentSpansQueryRes, HTTPValidationError>({
        path: `/agents/spans/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Query chart-ready aggregations over agent spans.
     *
     * @tags Agents
     * @name GenaiSpansStatsAgentsSpansStatsPost
     * @summary Genai Spans Stats
     * @request POST:/agents/spans/stats
     */
    genaiSpansStatsAgentsSpansStatsPost: (
      data: AgentSpanStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentSpanStatsRes, HTTPValidationError>({
        path: `/agents/spans/stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Discover typed custom attribute keys on matching agent spans.
     *
     * @tags Agents
     * @name GenaiCustomAttrsSchemaAgentsSpansCustomAttrsSchemaPost
     * @summary Genai Custom Attrs Schema
     * @request POST:/agents/spans/custom-attrs/schema
     */
    genaiCustomAttrsSchemaAgentsSpansCustomAttrsSchemaPost: (
      data: AgentCustomAttrsSchemaReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentCustomAttrsSchemaRes, HTTPValidationError>({
        path: `/agents/spans/custom-attrs/schema`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiAgentsQueryAgentsQueryPost
     * @summary Genai Agents Query
     * @request POST:/agents/query
     */
    genaiAgentsQueryAgentsQueryPost: (
      data: AgentsQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentsQueryRes, HTTPValidationError>({
        path: `/agents/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiAgentVersionsQueryAgentsAgentVersionsQueryPost
     * @summary Genai Agent Versions Query
     * @request POST:/agents/agent-versions/query
     */
    genaiAgentVersionsQueryAgentsAgentVersionsQueryPost: (
      data: AgentVersionsQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentVersionsQueryRes, HTTPValidationError>({
        path: `/agents/agent-versions/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiSearchAgentsSearchPost
     * @summary Genai Search
     * @request POST:/agents/search
     */
    genaiSearchAgentsSearchPost: (
      data: AgentSearchReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentSearchRes, HTTPValidationError>({
        path: `/agents/search`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiTracesChatAgentsTracesChatPost
     * @summary Genai Traces Chat
     * @request POST:/agents/traces/chat
     */
    genaiTracesChatAgentsTracesChatPost: (
      data: AgentTraceChatReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentTraceChatRes, HTTPValidationError>({
        path: `/agents/traces/chat`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiConversationChatAgentsConversationsChatPost
     * @summary Genai Conversation Chat
     * @request POST:/agents/conversations/chat
     */
    genaiConversationChatAgentsConversationsChatPost: (
      data: AgentConversationChatReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentConversationChatRes, HTTPValidationError>({
        path: `/agents/conversations/chat`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Agents
     * @name GenaiConversationSpansAgentsConversationsSpansPost
     * @summary Genai Conversation Spans
     * @request POST:/agents/conversations/spans
     */
    genaiConversationSpansAgentsConversationsSpansPost: (
      data: AgentConversationSpansReq,
      params: RequestParams = {}
    ) =>
      this.request<AgentConversationSpansRes, HTTPValidationError>({
        path: `/agents/conversations/spans`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  call = {
    /**
     * No description
     *
     * @tags Calls
     * @name CallStartCallStartPost
     * @summary Call Start
     * @request POST:/call/start
     */
    callStartCallStartPost: (data: CallStartReq, params: RequestParams = {}) =>
      this.request<CallStartRes, HTTPValidationError>({
        path: `/call/start`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallEndCallEndPost
     * @summary Call End
     * @request POST:/call/end
     */
    callEndCallEndPost: (data: CallEndReq, params: RequestParams = {}) =>
      this.request<CallEndRes, HTTPValidationError>({
        path: `/call/end`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallStartBatchCallUpsertBatchPost
     * @summary Call Start Batch
     * @request POST:/call/upsert_batch
     */
    callStartBatchCallUpsertBatchPost: (
      data: CallCreateBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<CallCreateBatchRes, HTTPValidationError>({
        path: `/call/upsert_batch`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallUpdateCallUpdatePost
     * @summary Call Update
     * @request POST:/call/update
     */
    callUpdateCallUpdatePost: (
      data: CallUpdateReq,
      params: RequestParams = {}
    ) =>
      this.request<CallUpdateRes, HTTPValidationError>({
        path: `/call/update`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallReadCallReadPost
     * @summary Call Read
     * @request POST:/call/read
     */
    callReadCallReadPost: (data: CallReadReq, params: RequestParams = {}) =>
      this.request<CallReadRes, HTTPValidationError>({
        path: `/call/read`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  calls = {
    /**
     * No description
     *
     * @tags Calls
     * @name CallsDeleteCallsDeletePost
     * @summary Calls Delete
     * @request POST:/calls/delete
     */
    callsDeleteCallsDeletePost: (
      data: CallsDeleteReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsDeleteRes, HTTPValidationError>({
        path: `/calls/delete`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallsQueryStatsCallsQueryStatsPost
     * @summary Calls Query Stats
     * @request POST:/calls/query_stats
     */
    callsQueryStatsCallsQueryStatsPost: (
      data: CallsQueryStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsQueryStatsRes, HTTPValidationError>({
        path: `/calls/query_stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Compute aggregated usage for multiple root calls, with descendant rollup.
     *
     * @tags Calls
     * @name CallsUsageCallsUsagePost
     * @summary Calls Usage
     * @request POST:/calls/usage
     */
    callsUsageCallsUsagePost: (
      data: CallsUsageReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsUsageRes, HTTPValidationError>({
        path: `/calls/usage`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallsQueryStreamCallsStreamQueryPost
     * @summary Calls Query Stream
     * @request POST:/calls/stream_query
     */
    callsQueryStreamCallsStreamQueryPost: (
      data: CallsQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/calls/stream_query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallStatsCallsStatsPost
     * @summary Call Stats
     * @request POST:/calls/stats
     */
    callStatsCallsStatsPost: (data: CallStatsReq, params: RequestParams = {}) =>
      this.request<CallStatsRes, HTTPValidationError>({
        path: `/calls/stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Scores
     * @name CallsScoreCallsScorePost
     * @summary Calls Score
     * @request POST:/calls/score
     */
    callsScoreCallsScorePost: (
      data: CallsScoreReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsScoreRes, HTTPValidationError>({
        path: `/calls/score`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  inference = {
    /**
     * @description Returns a list of available Serverless Inference models. This API is available without authentication.
     *
     * @tags Inference
     * @name InferenceCatalogModelsInferenceCatalogModelsGet
     * @summary Inference Catalog Models
     * @request GET:/inference/catalog/models
     */
    inferenceCatalogModelsInferenceCatalogModelsGet: (
      params: RequestParams = {}
    ) =>
      this.request<CatalogModelsRes, any>({
        path: `/inference/catalog/models`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Returns a list of available models for Artificial Analysis. This API is available without authentication.
     *
     * @tags Inference
     * @name InferenceAnalysisArtificialanalysisModelsInferenceAnalysisArtificialanalysisModelsGet
     * @summary Inference Analysis Artificialanalysis Models
     * @request GET:/inference/analysis/artificialanalysis/models
     */
    inferenceAnalysisArtificialanalysisModelsInferenceAnalysisArtificialanalysisModelsGet:
      (params: RequestParams = {}) =>
        this.request<RouterOpenRouterModelsRes, any>({
          path: `/inference/analysis/artificialanalysis/models`,
          method: 'GET',
          format: 'json',
          ...params,
        }),

    /**
     * @description Returns a list of models that are available to be used with OpenRouter. This API is available without authentication.
     *
     * @tags Inference
     * @name InferenceRouterOpenrouterModelsInferenceRouterOpenrouterModelsGet
     * @summary Inference Router Openrouter Models
     * @request GET:/inference/router/openrouter/models
     */
    inferenceRouterOpenrouterModelsInferenceRouterOpenrouterModelsGet: (
      params: RequestParams = {}
    ) =>
      this.request<RouterOpenRouterModelsRes, any>({
        path: `/inference/router/openrouter/models`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Returns the available models in the models.dev `api.json` schema. This API is available without authentication.
     *
     * @tags Inference
     * @name InferenceModelsdevModelsInferenceModelsdevModelsGet
     * @summary Inference Modelsdev Models
     * @request GET:/inference/modelsdev/models
     */
    inferenceModelsdevModelsInferenceModelsdevModelsGet: (
      params: RequestParams = {}
    ) =>
      this.request<Record<string, ModelsDevProvider>, any>({
        path: `/inference/modelsdev/models`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Returns available hardware and pricing for a given model. Called by NVIDIA to show users their options and redirect them based on what we support.  Only serverless options are returned.
     *
     * @tags Inference
     * @name NvidiaHardwareInferenceNvidiaV2HardwareGet
     * @summary Nvidia Hardware
     * @request GET:/inference/nvidia/v2/hardware
     * @secure
     */
    nvidiaHardwareInferenceNvidiaV2HardwareGet: (
      query: {
        /**
         * Model
         * Model name without the publisher prefix
         */
        model: string;
      },
      params: RequestParams = {}
    ) =>
      this.request<NvidiaHardwareRes, HTTPValidationError>({
        path: `/inference/nvidia/v2/hardware`,
        method: 'GET',
        query: query,
        secure: true,
        format: 'json',
        ...params,
      }),
  };
  trace = {
    /**
     * @description Compute per-call usage for a trace, with descendant rollup.
     *
     * @tags Calls
     * @name TraceUsageTraceUsagePost
     * @summary Trace Usage
     * @request POST:/trace/usage
     */
    traceUsageTraceUsagePost: (
      data: TraceUsageReq,
      params: RequestParams = {}
    ) =>
      this.request<TraceUsageRes, HTTPValidationError>({
        path: `/trace/usage`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  obj = {
    /**
     * No description
     *
     * @tags Objects
     * @name ObjCreateObjCreatePost
     * @summary Obj Create
     * @request POST:/obj/create
     */
    objCreateObjCreatePost: (data: ObjCreateReq, params: RequestParams = {}) =>
      this.request<ObjCreateRes, HTTPValidationError>({
        path: `/obj/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Objects
     * @name ObjReadObjReadPost
     * @summary Obj Read
     * @request POST:/obj/read
     */
    objReadObjReadPost: (data: ObjReadReq, params: RequestParams = {}) =>
      this.request<ObjReadRes, HTTPValidationError>({
        path: `/obj/read`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Objects
     * @name ObjDeleteObjDeletePost
     * @summary Obj Delete
     * @request POST:/obj/delete
     */
    objDeleteObjDeletePost: (data: ObjDeleteReq, params: RequestParams = {}) =>
      this.request<ObjDeleteRes, HTTPValidationError>({
        path: `/obj/delete`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  objs = {
    /**
     * No description
     *
     * @tags Objects
     * @name ObjsQueryObjsQueryPost
     * @summary Objs Query
     * @request POST:/objs/query
     */
    objsQueryObjsQueryPost: (data: ObjQueryReq, params: RequestParams = {}) =>
      this.request<ObjQueryRes, HTTPValidationError>({
        path: `/objs/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Add tags to an object version.
     *
     * @tags Objects
     * @name ObjAddTagsObjsObjectIdVersionsDigestTagsPut
     * @summary Obj Add Tags
     * @request PUT:/objs/{object_id}/versions/{digest}/tags
     */
    objAddTagsObjsObjectIdVersionsDigestTagsPut: (
      objectId: string,
      digest: string,
      data: ObjTagsBody,
      params: RequestParams = {}
    ) =>
      this.request<ObjAddTagsRes, HTTPValidationError>({
        path: `/objs/${objectId}/versions/${digest}/tags`,
        method: 'PUT',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Remove tags from an object version.
     *
     * @tags Objects
     * @name ObjRemoveTagsObjsObjectIdVersionsDigestTagsRemovePost
     * @summary Obj Remove Tags
     * @request POST:/objs/{object_id}/versions/{digest}/tags/remove
     */
    objRemoveTagsObjsObjectIdVersionsDigestTagsRemovePost: (
      objectId: string,
      digest: string,
      data: ObjTagsBody,
      params: RequestParams = {}
    ) =>
      this.request<ObjRemoveTagsRes, HTTPValidationError>({
        path: `/objs/${objectId}/versions/${digest}/tags/remove`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Set aliases for an object version.
     *
     * @tags Objects
     * @name ObjSetAliasesObjsObjectIdAliasesPut
     * @summary Obj Set Aliases
     * @request PUT:/objs/{object_id}/aliases
     */
    objSetAliasesObjsObjectIdAliasesPut: (
      objectId: string,
      data: ObjSetAliasesBody,
      params: RequestParams = {}
    ) =>
      this.request<ObjSetAliasesRes, HTTPValidationError>({
        path: `/objs/${objectId}/aliases`,
        method: 'PUT',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Remove aliases from an object.
     *
     * @tags Objects
     * @name ObjRemoveAliasesObjsObjectIdAliasesRemovePost
     * @summary Obj Remove Aliases
     * @request POST:/objs/{object_id}/aliases/remove
     */
    objRemoveAliasesObjsObjectIdAliasesRemovePost: (
      objectId: string,
      data: ObjRemoveAliasesBody,
      params: RequestParams = {}
    ) =>
      this.request<ObjRemoveAliasesRes, HTTPValidationError>({
        path: `/objs/${objectId}/aliases/remove`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  tags = {
    /**
     * @description List all tags in a project.
     *
     * @tags Objects
     * @name TagsListTagsGet
     * @summary Tags List
     * @request GET:/tags
     */
    tagsListTagsGet: (
      query: {
        /** Project Id */
        project_id: string;
      },
      params: RequestParams = {}
    ) =>
      this.request<TagsListRes, HTTPValidationError>({
        path: `/tags`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),
  };
  aliases = {
    /**
     * @description List all aliases in a project.
     *
     * @tags Objects
     * @name AliasesListAliasesGet
     * @summary Aliases List
     * @request GET:/aliases
     */
    aliasesListAliasesGet: (
      query: {
        /** Project Id */
        project_id: string;
      },
      params: RequestParams = {}
    ) =>
      this.request<AliasesListRes, HTTPValidationError>({
        path: `/aliases`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),
  };
  table = {
    /**
     * No description
     *
     * @tags Tables
     * @name TableCreateTableCreatePost
     * @summary Table Create
     * @request POST:/table/create
     */
    tableCreateTableCreatePost: (
      data: TableCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<TableCreateRes, HTTPValidationError>({
        path: `/table/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableUpdateTableUpdatePost
     * @summary Table Update
     * @request POST:/table/update
     */
    tableUpdateTableUpdatePost: (
      data: TableUpdateReq,
      params: RequestParams = {}
    ) =>
      this.request<TableUpdateRes, HTTPValidationError>({
        path: `/table/update`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableCreateFromDigestsTableCreateFromDigestsPost
     * @summary Table Create From Digests
     * @request POST:/table/create_from_digests
     */
    tableCreateFromDigestsTableCreateFromDigestsPost: (
      data: TableCreateFromDigestsReq,
      params: RequestParams = {}
    ) =>
      this.request<TableCreateFromDigestsRes, HTTPValidationError>({
        path: `/table/create_from_digests`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableQueryTableQueryPost
     * @summary Table Query
     * @request POST:/table/query
     */
    tableQueryTableQueryPost: (
      data: TableQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<TableQueryRes, HTTPValidationError>({
        path: `/table/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableQueryStatsTableQueryStatsPost
     * @summary Table Query Stats
     * @request POST:/table/query_stats
     */
    tableQueryStatsTableQueryStatsPost: (
      data: TableQueryStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<TableQueryStatsRes, HTTPValidationError>({
        path: `/table/query_stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableQueryStatsBatchTableQueryStatsBatchPost
     * @summary Table Query Stats Batch
     * @request POST:/table/query_stats_batch
     */
    tableQueryStatsBatchTableQueryStatsBatchPost: (
      data: TableQueryStatsBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<TableQueryStatsBatchRes, HTTPValidationError>({
        path: `/table/query_stats_batch`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  refs = {
    /**
     * No description
     *
     * @tags Refs
     * @name RefsReadBatchRefsReadBatchPost
     * @summary Refs Read Batch
     * @request POST:/refs/read_batch
     */
    refsReadBatchRefsReadBatchPost: (
      data: RefsReadBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<RefsReadBatchRes, HTTPValidationError>({
        path: `/refs/read_batch`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  file = {
    /**
     * No description
     *
     * @tags Files
     * @name FileCreateFileCreatePost
     * @summary File Create
     * @request POST:/file/create
     */
    fileCreateFileCreatePost: (
      data: BodyFileCreateFileCreatePost,
      params: RequestParams = {}
    ) =>
      this.request<FileCreateRes, HTTPValidationError>({
        path: `/file/create`,
        method: 'POST',
        body: data,
        type: ContentType.FormData,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Files
     * @name FileContentFileContentPost
     * @summary File Content
     * @request POST:/file/content
     */
    fileContentFileContentPost: (
      data: FileContentReadReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/file/content`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  files = {
    /**
     * No description
     *
     * @tags Files
     * @name FilesStatsFilesQueryStatsPost
     * @summary Files Stats
     * @request POST:/files/query_stats
     */
    filesStatsFilesQueryStatsPost: (
      data: FilesStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<FilesStatsRes, HTTPValidationError>({
        path: `/files/query_stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  cost = {
    /**
     * No description
     *
     * @tags Costs
     * @name CostCreateCostCreatePost
     * @summary Cost Create
     * @request POST:/cost/create
     */
    costCreateCostCreatePost: (
      data: CostCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<CostCreateRes, HTTPValidationError>({
        path: `/cost/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Costs
     * @name CostQueryCostQueryPost
     * @summary Cost Query
     * @request POST:/cost/query
     */
    costQueryCostQueryPost: (data: CostQueryReq, params: RequestParams = {}) =>
      this.request<CostQueryRes, HTTPValidationError>({
        path: `/cost/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Costs
     * @name CostPurgeCostPurgePost
     * @summary Cost Purge
     * @request POST:/cost/purge
     */
    costPurgeCostPurgePost: (data: CostPurgeReq, params: RequestParams = {}) =>
      this.request<CostPurgeRes, HTTPValidationError>({
        path: `/cost/purge`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  feedback = {
    /**
     * @description Add feedback to a call or object.
     *
     * @tags Feedback
     * @name FeedbackCreateFeedbackCreatePost
     * @summary Feedback Create
     * @request POST:/feedback/create
     */
    feedbackCreateFeedbackCreatePost: (
      data: FeedbackCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackCreateRes, HTTPValidationError>({
        path: `/feedback/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Add multiple feedback items to calls or objects.
     *
     * @tags Feedback
     * @name FeedbackCreateBatchFeedbackBatchCreatePost
     * @summary Feedback Create Batch
     * @request POST:/feedback/batch/create
     */
    feedbackCreateBatchFeedbackBatchCreatePost: (
      data: FeedbackCreateBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackCreateBatchRes, HTTPValidationError>({
        path: `/feedback/batch/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Query for feedback.
     *
     * @tags Feedback
     * @name FeedbackQueryFeedbackQueryPost
     * @summary Feedback Query
     * @request POST:/feedback/query
     */
    feedbackQueryFeedbackQueryPost: (
      data: FeedbackQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackQueryRes, HTTPValidationError>({
        path: `/feedback/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Permanently delete feedback.
     *
     * @tags Feedback
     * @name FeedbackPurgeFeedbackPurgePost
     * @summary Feedback Purge
     * @request POST:/feedback/purge
     */
    feedbackPurgeFeedbackPurgePost: (
      data: FeedbackPurgeReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackPurgeRes, HTTPValidationError>({
        path: `/feedback/purge`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Feedback
     * @name FeedbackReplaceFeedbackReplacePost
     * @summary Feedback Replace
     * @request POST:/feedback/replace
     */
    feedbackReplaceFeedbackReplacePost: (
      data: FeedbackReplaceReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackReplaceRes, HTTPValidationError>({
        path: `/feedback/replace`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Return aggregated feedback statistics over time buckets.
     *
     * @tags Feedback
     * @name FeedbackStatsFeedbackStatsPost
     * @summary Feedback Stats
     * @request POST:/feedback/stats
     */
    feedbackStatsFeedbackStatsPost: (
      data: FeedbackStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackStatsRes, HTTPValidationError>({
        path: `/feedback/stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Aggregate typed scorer feedback (tags, ratings) over time buckets.
     *
     * @tags Feedback
     * @name FeedbackAggregateFeedbackAggregatePost
     * @summary Feedback Aggregate
     * @request POST:/feedback/aggregate
     */
    feedbackAggregateFeedbackAggregatePost: (
      data: FeedbackAggregateReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackAggregateRes, HTTPValidationError>({
        path: `/feedback/aggregate`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Discover feedback payload schema (paths and types) from sample rows.
     *
     * @tags Feedback
     * @name FeedbackPayloadSchemaFeedbackPayloadSchemaPost
     * @summary Feedback Payload Schema
     * @request POST:/feedback/payload_schema
     */
    feedbackPayloadSchemaFeedbackPayloadSchemaPost: (
      data: FeedbackPayloadSchemaReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackPayloadSchemaRes, HTTPValidationError>({
        path: `/feedback/payload_schema`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  service = {
    /**
     * No description
     *
     * @tags Service
     * @name ProjectsInfoServiceProjectsInfoPost
     * @summary Projects Info
     * @request POST:/service/projects_info
     */
    projectsInfoServiceProjectsInfoPost: (
      data: ProjectsInfoReq,
      params: RequestParams = {}
    ) =>
      this.request<ProjectsInfoRes[], HTTPValidationError>({
        path: `/service/projects_info`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  threads = {
    /**
     * No description
     *
     * @tags Threads
     * @name ThreadsQueryStreamThreadsStreamQueryPost
     * @summary Threads Query Stream
     * @request POST:/threads/stream_query
     */
    threadsQueryStreamThreadsStreamQueryPost: (
      data: ThreadsQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/threads/stream_query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  annotationQueues = {
    /**
     * @description Create a new annotation queue.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueCreateAnnotationQueuesPost
     * @summary Annotation Queue Create
     * @request POST:/annotation_queues
     */
    annotationQueueCreateAnnotationQueuesPost: (
      data: AnnotationQueueCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueCreateRes, HTTPValidationError>({
        path: `/annotation_queues`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Query annotation queues for a project (streaming NDJSON response).
     *
     * @tags Annotation Queues
     * @name AnnotationQueuesQueryStreamAnnotationQueuesQueryPost
     * @summary Annotation Queues Query Stream
     * @request POST:/annotation_queues/query
     */
    annotationQueuesQueryStreamAnnotationQueuesQueryPost: (
      data: AnnotationQueuesQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/annotation_queues/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Read a specific annotation queue.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueReadAnnotationQueuesQueueIdGet
     * @summary Annotation Queue Read
     * @request GET:/annotation_queues/{queue_id}
     */
    annotationQueueReadAnnotationQueuesQueueIdGet: (
      queueId: string,
      query: {
        /** Project Id */
        project_id: string;
      },
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueReadRes, HTTPValidationError>({
        path: `/annotation_queues/${queueId}`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete (soft-delete) an annotation queue.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueDeleteAnnotationQueuesQueueIdDelete
     * @summary Annotation Queue Delete
     * @request DELETE:/annotation_queues/{queue_id}
     */
    annotationQueueDeleteAnnotationQueuesQueueIdDelete: (
      queueId: string,
      query: {
        /** Project Id */
        project_id: string;
      },
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueDeleteRes, HTTPValidationError>({
        path: `/annotation_queues/${queueId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Update an annotation queue's metadata (name, description, scorer_refs).
     *
     * @tags Annotation Queues
     * @name AnnotationQueueUpdateAnnotationQueuesQueueIdPut
     * @summary Annotation Queue Update
     * @request PUT:/annotation_queues/{queue_id}
     */
    annotationQueueUpdateAnnotationQueuesQueueIdPut: (
      queueId: string,
      data: AnnotationQueueUpdateBody,
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueUpdateRes, HTTPValidationError>({
        path: `/annotation_queues/${queueId}`,
        method: 'PUT',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Add calls to an annotation queue.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueAddCallsAnnotationQueuesQueueIdItemsPost
     * @summary Annotation Queue Add Calls
     * @request POST:/annotation_queues/{queue_id}/items
     */
    annotationQueueAddCallsAnnotationQueuesQueueIdItemsPost: (
      queueId: string,
      data: AnnotationQueueAddCallsBody,
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueAddCallsRes, HTTPValidationError>({
        path: `/annotation_queues/${queueId}/items`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Query items in an annotation queue with pagination and sorting.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueItemsQueryAnnotationQueuesQueueIdItemsQueryPost
     * @summary Annotation Queue Items Query
     * @request POST:/annotation_queues/{queue_id}/items/query
     */
    annotationQueueItemsQueryAnnotationQueuesQueueIdItemsQueryPost: (
      queueId: string,
      data: AnnotationQueueItemsQueryBody,
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueueItemsQueryRes, HTTPValidationError>({
        path: `/annotation_queues/${queueId}/items/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Get stats for multiple annotation queues.
     *
     * @tags Annotation Queues
     * @name AnnotationQueuesStatsAnnotationQueuesStatsPost
     * @summary Annotation Queues Stats
     * @request POST:/annotation_queues/stats
     */
    annotationQueuesStatsAnnotationQueuesStatsPost: (
      data: AnnotationQueuesStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<AnnotationQueuesStatsRes, HTTPValidationError>({
        path: `/annotation_queues/stats`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Update the annotation state of a queue item for the current annotator.
     *
     * @tags Annotation Queues
     * @name AnnotationQueueItemProgressUpdateAnnotationQueuesQueueIdItemsItemIdProgressPost
     * @summary Annotation Queue Item Progress Update
     * @request POST:/annotation_queues/{queue_id}/items/{item_id}/progress
     */
    annotationQueueItemProgressUpdateAnnotationQueuesQueueIdItemsItemIdProgressPost:
      (
        queueId: string,
        itemId: string,
        data: AnnotationQueueItemProgressUpdateBody,
        params: RequestParams = {}
      ) =>
        this.request<AnnotatorQueueItemsProgressUpdateRes, HTTPValidationError>(
          {
            path: `/annotation_queues/${queueId}/items/${itemId}/progress`,
            method: 'POST',
            body: data,
            type: ContentType.Json,
            format: 'json',
            ...params,
          }
        ),
  };
  evaluations = {
    /**
     * No description
     *
     * @tags Evaluations
     * @name EvaluateModelEvaluationsEvaluateModelPost
     * @summary Evaluate Model
     * @request POST:/evaluations/evaluate_model
     */
    evaluateModelEvaluationsEvaluateModelPost: (
      data: EvaluateModelReq,
      params: RequestParams = {}
    ) =>
      this.request<EvaluateModelRes, HTTPValidationError>({
        path: `/evaluations/evaluate_model`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Evaluations
     * @name EvaluationStatusEvaluationsStatusPost
     * @summary Evaluation Status
     * @request POST:/evaluations/status
     */
    evaluationStatusEvaluationsStatusPost: (
      data: EvaluationStatusReq,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationStatusRes, HTTPValidationError>({
        path: `/evaluations/status`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Rescore an existing evaluation run with different scorer(s). Applies the provided scorer(s) to the predictions from source_evaluation_run_id and returns a new evaluation_run_id. Original prediction call IDs are preserved.
     *
     * @tags Evaluations
     * @name RescoreEvaluationEvaluationsRescorePost
     * @summary Rescore Evaluation
     * @request POST:/evaluations/rescore
     */
    rescoreEvaluationEvaluationsRescorePost: (
      data: RescoreReq,
      params: RequestParams = {}
    ) =>
      this.request<RescoreRes, HTTPValidationError>({
        path: `/evaluations/rescore`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  image = {
    /**
     * No description
     *
     * @tags Images
     * @name ImageCreateImageCreatePost
     * @summary Image Create
     * @request POST:/image/create
     */
    imageCreateImageCreatePost: (
      data: ImageGenerationCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<ImageGenerationCreateRes, HTTPValidationError>({
        path: `/image/create`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  linkToRegistry = {
    /**
     * No description
     *
     * @tags Registry
     * @name LinkToRegistryLinkToRegistryPost
     * @summary Link To Registry
     * @request POST:/link_to_registry
     */
    linkToRegistryLinkToRegistryPost: (
      data: CreateAndLinkPayload,
      params: RequestParams = {}
    ) =>
      this.request<CreateAndLinkWeaveAssetRes, HTTPValidationError>({
        path: `/link_to_registry`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  v2 = {
    /**
     * @description Upsert a batch of completed calls directly to the calls_complete table. Each call in the batch contains both start and end information. This endpoint is used when calls are buffered client-side and sent as complete records.
     *
     * @tags Calls
     * @name CallsCompleteV2EntityProjectCallsCompletePost
     * @summary Calls Complete
     * @request POST:/v2/{entity}/{project}/calls/complete
     */
    callsCompleteV2EntityProjectCallsCompletePost: (
      entity: string,
      project: string,
      data: CallsUpsertCompleteReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsUpsertCompleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/calls/complete`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create an op object.
     *
     * @tags Ops
     * @name OpCreateV2EntityProjectOpsPost
     * @summary Op Create
     * @request POST:/v2/{entity}/{project}/ops
     */
    opCreateV2EntityProjectOpsPost: (
      entity: string,
      project: string,
      data: OpCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<OpCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/ops`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List op objects.
     *
     * @tags Ops
     * @name OpListV2EntityProjectOpsGet
     * @summary Op List
     * @request GET:/v2/{entity}/{project}/ops
     */
    opListV2EntityProjectOpsGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Limit
         * Maximum number of ops to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of ops to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/v2/${entity}/${project}/ops`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Get an op object.
     *
     * @tags Ops
     * @name OpReadV2EntityProjectOpsObjectIdVersionsDigestGet
     * @summary Op Read
     * @request GET:/v2/{entity}/{project}/ops/{object_id}/versions/{digest}
     */
    opReadV2EntityProjectOpsObjectIdVersionsDigestGet: (
      entity: string,
      project: string,
      objectId: string,
      digest: string,
      query?: {
        /**
         * Eager
         * Whether to eagerly load the op code
         * @default false
         */
        eager?: boolean;
      },
      params: RequestParams = {}
    ) =>
      this.request<OpReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/ops/${objectId}/versions/${digest}`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete an op object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted.
     *
     * @tags Ops
     * @name OpDeleteV2EntityProjectOpsObjectIdDelete
     * @summary Op Delete
     * @request DELETE:/v2/{entity}/{project}/ops/{object_id}
     */
    opDeleteV2EntityProjectOpsObjectIdDelete: (
      entity: string,
      project: string,
      objectId: string,
      query?: {
        /**
         * Digests
         * List of digests to delete. If not provided, all digests for the op will be deleted.
         */
        digests?: string[] | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<OpDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/ops/${objectId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create a dataset object.
     *
     * @tags Datasets
     * @name DatasetCreateV2EntityProjectDatasetsPost
     * @summary Dataset Create
     * @request POST:/v2/{entity}/{project}/datasets
     */
    datasetCreateV2EntityProjectDatasetsPost: (
      entity: string,
      project: string,
      data: DatasetCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<DatasetCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/datasets`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List dataset objects.
     *
     * @tags Datasets
     * @name DatasetListV2EntityProjectDatasetsGet
     * @summary Dataset List
     * @request GET:/v2/{entity}/{project}/datasets
     */
    datasetListV2EntityProjectDatasetsGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Limit
         * Maximum number of datasets to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of datasets to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/v2/${entity}/${project}/datasets`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Get a dataset object.
     *
     * @tags Datasets
     * @name DatasetReadV2EntityProjectDatasetsObjectIdVersionsDigestGet
     * @summary Dataset Read
     * @request GET:/v2/{entity}/{project}/datasets/{object_id}/versions/{digest}
     */
    datasetReadV2EntityProjectDatasetsObjectIdVersionsDigestGet: (
      entity: string,
      project: string,
      objectId: string,
      digest: string,
      params: RequestParams = {}
    ) =>
      this.request<DatasetReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/datasets/${objectId}/versions/${digest}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete a dataset object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted.
     *
     * @tags Datasets
     * @name DatasetDeleteV2EntityProjectDatasetsObjectIdDelete
     * @summary Dataset Delete
     * @request DELETE:/v2/{entity}/{project}/datasets/{object_id}
     */
    datasetDeleteV2EntityProjectDatasetsObjectIdDelete: (
      entity: string,
      project: string,
      objectId: string,
      query?: {
        /**
         * Digests
         * List of digests to delete. If not provided, all digests for the dataset will be deleted.
         */
        digests?: string[] | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<DatasetDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/datasets/${objectId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create a scorer object.
     *
     * @tags Scorers
     * @name ScorerCreateV2EntityProjectScorersPost
     * @summary Scorer Create
     * @request POST:/v2/{entity}/{project}/scorers
     */
    scorerCreateV2EntityProjectScorersPost: (
      entity: string,
      project: string,
      data: ScorerCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<ScorerCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scorers`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List scorer objects.
     *
     * @tags Scorers
     * @name ScorerListV2EntityProjectScorersGet
     * @summary Scorer List
     * @request GET:/v2/{entity}/{project}/scorers
     */
    scorerListV2EntityProjectScorersGet: (
      entity: string,
      project: string,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scorers`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Get a scorer object.
     *
     * @tags Scorers
     * @name ScorerReadV2EntityProjectScorersObjectIdVersionsDigestGet
     * @summary Scorer Read
     * @request GET:/v2/{entity}/{project}/scorers/{object_id}/versions/{digest}
     */
    scorerReadV2EntityProjectScorersObjectIdVersionsDigestGet: (
      entity: string,
      project: string,
      objectId: string,
      digest: string,
      params: RequestParams = {}
    ) =>
      this.request<ScorerReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scorers/${objectId}/versions/${digest}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete a scorer object.
     *
     * @tags Scorers
     * @name ScorerDeleteV2EntityProjectScorersObjectIdDelete
     * @summary Scorer Delete
     * @request DELETE:/v2/{entity}/{project}/scorers/{object_id}
     */
    scorerDeleteV2EntityProjectScorersObjectIdDelete: (
      entity: string,
      project: string,
      objectId: string,
      query?: {
        /**
         * Digests
         * List of digests to delete. If not provided, all digests for the scorer will be deleted.
         */
        digests?: string[] | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<ScorerDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scorers/${objectId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create an evaluation object.
     *
     * @tags Evaluations
     * @name EvaluationCreateV2EntityProjectEvaluationsPost
     * @summary Evaluation Create
     * @request POST:/v2/{entity}/{project}/evaluations
     */
    evaluationCreateV2EntityProjectEvaluationsPost: (
      entity: string,
      project: string,
      data: EvaluationCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluations`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List evaluation objects.
     *
     * @tags Evaluations
     * @name EvaluationListV2EntityProjectEvaluationsGet
     * @summary Evaluation List
     * @request GET:/v2/{entity}/{project}/evaluations
     */
    evaluationListV2EntityProjectEvaluationsGet: (
      entity: string,
      project: string,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluations`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Get an evaluation object.
     *
     * @tags Evaluations
     * @name EvaluationReadV2EntityProjectEvaluationsObjectIdVersionsDigestGet
     * @summary Evaluation Read
     * @request GET:/v2/{entity}/{project}/evaluations/{object_id}/versions/{digest}
     */
    evaluationReadV2EntityProjectEvaluationsObjectIdVersionsDigestGet: (
      entity: string,
      project: string,
      objectId: string,
      digest: string,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluations/${objectId}/versions/${digest}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete an evaluation object.
     *
     * @tags Evaluations
     * @name EvaluationDeleteV2EntityProjectEvaluationsObjectIdDelete
     * @summary Evaluation Delete
     * @request DELETE:/v2/{entity}/{project}/evaluations/{object_id}
     */
    evaluationDeleteV2EntityProjectEvaluationsObjectIdDelete: (
      entity: string,
      project: string,
      objectId: string,
      query?: {
        /**
         * Digests
         * List of digests to delete. If not provided, all digests for the evaluation will be deleted.
         */
        digests?: string[] | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<EvaluationDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluations/${objectId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create a model object.
     *
     * @tags Models
     * @name ModelCreateV2EntityProjectModelsPost
     * @summary Model Create
     * @request POST:/v2/{entity}/{project}/models
     */
    modelCreateV2EntityProjectModelsPost: (
      entity: string,
      project: string,
      data: ModelCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<ModelCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/models`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List model objects.
     *
     * @tags Models
     * @name ModelListV2EntityProjectModelsGet
     * @summary Model List
     * @request GET:/v2/{entity}/{project}/models
     */
    modelListV2EntityProjectModelsGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Limit
         * Maximum number of models to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of models to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/v2/${entity}/${project}/models`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Get a model object.
     *
     * @tags Models
     * @name ModelReadV2EntityProjectModelsObjectIdVersionsDigestGet
     * @summary Model Read
     * @request GET:/v2/{entity}/{project}/models/{object_id}/versions/{digest}
     */
    modelReadV2EntityProjectModelsObjectIdVersionsDigestGet: (
      entity: string,
      project: string,
      objectId: string,
      digest: string,
      params: RequestParams = {}
    ) =>
      this.request<ModelReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/models/${objectId}/versions/${digest}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete a model object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted.
     *
     * @tags Models
     * @name ModelDeleteV2EntityProjectModelsObjectIdDelete
     * @summary Model Delete
     * @request DELETE:/v2/{entity}/{project}/models/{object_id}
     */
    modelDeleteV2EntityProjectModelsObjectIdDelete: (
      entity: string,
      project: string,
      objectId: string,
      query?: {
        /**
         * Digests
         * List of digests to delete. If not provided, all digests for the model will be deleted.
         */
        digests?: string[] | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<ModelDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/models/${objectId}`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create an evaluation run.
     *
     * @tags Evaluation Runs
     * @name EvaluationRunCreateV2EntityProjectEvaluationRunsPost
     * @summary Evaluation Run Create
     * @request POST:/v2/{entity}/{project}/evaluation_runs
     */
    evaluationRunCreateV2EntityProjectEvaluationRunsPost: (
      entity: string,
      project: string,
      data: EvaluationRunCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationRunCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluation_runs`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List evaluation runs.
     *
     * @tags Evaluation Runs
     * @name EvaluationRunListV2EntityProjectEvaluationRunsGet
     * @summary Evaluation Run List
     * @request GET:/v2/{entity}/{project}/evaluation_runs
     */
    evaluationRunListV2EntityProjectEvaluationRunsGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Evaluations
         * Filter by evaluation references
         */
        evaluations?: string[] | null;
        /**
         * Models
         * Filter by model references
         */
        models?: string[] | null;
        /**
         * Evaluation Run Ids
         * Filter by evaluation run IDs
         */
        evaluation_run_ids?: string[] | null;
        /**
         * Limit
         * Maximum number of evaluation runs to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of evaluation runs to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<EvaluationRunReadRes[], HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluation_runs`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete evaluation runs.
     *
     * @tags Evaluation Runs
     * @name EvaluationRunDeleteV2EntityProjectEvaluationRunsDelete
     * @summary Evaluation Run Delete
     * @request DELETE:/v2/{entity}/{project}/evaluation_runs
     */
    evaluationRunDeleteV2EntityProjectEvaluationRunsDelete: (
      entity: string,
      project: string,
      query: {
        /**
         * Evaluation Run Ids
         * List of evaluation run IDs to delete
         */
        evaluation_run_ids: string[];
      },
      params: RequestParams = {}
    ) =>
      this.request<EvaluationRunDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluation_runs`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Read an evaluation run.
     *
     * @tags Evaluation Runs
     * @name EvaluationRunReadV2EntityProjectEvaluationRunsEvaluationRunIdGet
     * @summary Evaluation Run Read
     * @request GET:/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}
     */
    evaluationRunReadV2EntityProjectEvaluationRunsEvaluationRunIdGet: (
      entity: string,
      project: string,
      evaluationRunId: string,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationRunReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluation_runs/${evaluationRunId}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Finish an evaluation run.
     *
     * @tags Evaluation Runs
     * @name EvaluationRunFinishV2EntityProjectEvaluationRunsEvaluationRunIdFinishPost
     * @summary Evaluation Run Finish
     * @request POST:/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}/finish
     */
    evaluationRunFinishV2EntityProjectEvaluationRunsEvaluationRunIdFinishPost: (
      entity: string,
      project: string,
      evaluationRunId: string,
      data: EvaluationRunFinishBody,
      params: RequestParams = {}
    ) =>
      this.request<EvaluationRunFinishRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/evaluation_runs/${evaluationRunId}/finish`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create a prediction.
     *
     * @tags Predictions
     * @name PredictionCreateV2EntityProjectPredictionsPost
     * @summary Prediction Create
     * @request POST:/v2/{entity}/{project}/predictions
     */
    predictionCreateV2EntityProjectPredictionsPost: (
      entity: string,
      project: string,
      data: PredictionCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<PredictionCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/predictions`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List predictions.
     *
     * @tags Predictions
     * @name PredictionListV2EntityProjectPredictionsGet
     * @summary Prediction List
     * @request GET:/v2/{entity}/{project}/predictions
     */
    predictionListV2EntityProjectPredictionsGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Evaluation Run Id
         * Filter by evaluation run ID
         */
        evaluation_run_id?: string | null;
        /**
         * Limit
         * Maximum number of predictions to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of predictions to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<PredictionReadRes[], HTTPValidationError>({
        path: `/v2/${entity}/${project}/predictions`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete predictions.
     *
     * @tags Predictions
     * @name PredictionDeleteV2EntityProjectPredictionsDelete
     * @summary Prediction Delete
     * @request DELETE:/v2/{entity}/{project}/predictions
     */
    predictionDeleteV2EntityProjectPredictionsDelete: (
      entity: string,
      project: string,
      query: {
        /**
         * Prediction Ids
         * List of prediction IDs to delete
         */
        prediction_ids: string[];
      },
      params: RequestParams = {}
    ) =>
      this.request<PredictionDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/predictions`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Read a prediction.
     *
     * @tags Predictions
     * @name PredictionReadV2EntityProjectPredictionsPredictionIdGet
     * @summary Prediction Read
     * @request GET:/v2/{entity}/{project}/predictions/{prediction_id}
     */
    predictionReadV2EntityProjectPredictionsPredictionIdGet: (
      entity: string,
      project: string,
      predictionId: string,
      params: RequestParams = {}
    ) =>
      this.request<PredictionReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/predictions/${predictionId}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Finish a prediction.
     *
     * @tags Predictions
     * @name PredictionFinishV2EntityProjectPredictionsPredictionIdFinishPost
     * @summary Prediction Finish
     * @request POST:/v2/{entity}/{project}/predictions/{prediction_id}/finish
     */
    predictionFinishV2EntityProjectPredictionsPredictionIdFinishPost: (
      entity: string,
      project: string,
      predictionId: string,
      params: RequestParams = {}
    ) =>
      this.request<PredictionFinishRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/predictions/${predictionId}/finish`,
        method: 'POST',
        format: 'json',
        ...params,
      }),

    /**
     * @description Create a score.
     *
     * @tags Scores
     * @name ScoreCreateV2EntityProjectScoresPost
     * @summary Score Create
     * @request POST:/v2/{entity}/{project}/scores
     */
    scoreCreateV2EntityProjectScoresPost: (
      entity: string,
      project: string,
      data: ScoreCreateBody,
      params: RequestParams = {}
    ) =>
      this.request<ScoreCreateRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scores`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description List scores.
     *
     * @tags Scores
     * @name ScoreListV2EntityProjectScoresGet
     * @summary Score List
     * @request GET:/v2/{entity}/{project}/scores
     */
    scoreListV2EntityProjectScoresGet: (
      entity: string,
      project: string,
      query?: {
        /**
         * Evaluation Run Id
         * Filter by evaluation run ID
         */
        evaluation_run_id?: string | null;
        /**
         * Limit
         * Maximum number of scores to return
         */
        limit?: number | null;
        /**
         * Offset
         * Number of scores to skip
         */
        offset?: number | null;
      },
      params: RequestParams = {}
    ) =>
      this.request<ScoreReadRes[], HTTPValidationError>({
        path: `/v2/${entity}/${project}/scores`,
        method: 'GET',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Delete scores.
     *
     * @tags Scores
     * @name ScoreDeleteV2EntityProjectScoresDelete
     * @summary Score Delete
     * @request DELETE:/v2/{entity}/{project}/scores
     */
    scoreDeleteV2EntityProjectScoresDelete: (
      entity: string,
      project: string,
      query: {
        /**
         * Score Ids
         * List of score IDs to delete
         */
        score_ids: string[];
      },
      params: RequestParams = {}
    ) =>
      this.request<ScoreDeleteRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scores`,
        method: 'DELETE',
        query: query,
        format: 'json',
        ...params,
      }),

    /**
     * @description Read a score.
     *
     * @tags Scores
     * @name ScoreReadV2EntityProjectScoresScoreIdGet
     * @summary Score Read
     * @request GET:/v2/{entity}/{project}/scores/{score_id}
     */
    scoreReadV2EntityProjectScoresScoreIdGet: (
      entity: string,
      project: string,
      scoreId: string,
      params: RequestParams = {}
    ) =>
      this.request<ScoreReadRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/scores/${scoreId}`,
        method: 'GET',
        format: 'json',
        ...params,
      }),

    /**
     * @description Read grouped evaluation result rows for one or more evaluations.
     *
     * @tags Eval Results
     * @name EvalResultsQueryV2EntityProjectEvalResultsQueryPost
     * @summary Eval Results Query
     * @request POST:/v2/{entity}/{project}/eval_results/query
     */
    evalResultsQueryV2EntityProjectEvalResultsQueryPost: (
      entity: string,
      project: string,
      data: EvalResultsQueryBody,
      params: RequestParams = {}
    ) =>
      this.request<EvalResultsQueryRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/eval_results/query`,
        method: 'POST',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Create or replace a custom runtime configuration.
     *
     * @tags Custom Runtimes
     * @name CustomRuntimeApplyV2EntityProjectCustomRuntimesRuntimeNamePut
     * @summary Custom Runtime Apply
     * @request PUT:/v2/{entity}/{project}/custom-runtimes/{runtime_name}
     */
    customRuntimeApplyV2EntityProjectCustomRuntimesRuntimeNamePut: (
      entity: string,
      project: string,
      runtimeName: string,
      data: CustomRuntimeApplyBody,
      params: RequestParams = {}
    ) =>
      this.request<CustomRuntimeApplyRes, HTTPValidationError>({
        path: `/v2/${entity}/${project}/custom-runtimes/${runtimeName}`,
        method: 'PUT',
        body: data,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
}
