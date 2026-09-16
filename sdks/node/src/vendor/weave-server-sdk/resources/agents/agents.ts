// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as AgentVersionsAPI from './agent-versions';
import { AgentVersionQueryParams, AgentVersionQueryResponse, AgentVersions } from './agent-versions';
import * as ConversationsAPI from './conversations';
import {
  ConversationChatParams,
  ConversationChatResponse,
  ConversationSpansParams,
  ConversationSpansResponse,
  Conversations,
} from './conversations';
import * as SpansAPI from './spans';
import {
  SpanCustomAttrsSchemaParams,
  SpanCustomAttrsSchemaResponse,
  SpanQueryParams,
  SpanQueryResponse,
  SpanStatsParams,
  SpanStatsResponse,
  Spans,
} from './spans';
import * as TracesAPI from './traces';
import { TraceChatParams, Traces } from './traces';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Agents extends APIResource {
  spans: SpansAPI.Spans = new SpansAPI.Spans(this._client);
  agentVersions: AgentVersionsAPI.AgentVersions = new AgentVersionsAPI.AgentVersions(this._client);
  traces: TracesAPI.Traces = new TracesAPI.Traces(this._client);
  conversations: ConversationsAPI.Conversations = new ConversationsAPI.Conversations(this._client);

  /**
   * Genai Agents Query
   */
  query(body: AgentQueryParams, options?: RequestOptions): APIPromise<AgentQueryResponse> {
    return this._client.post('/agents/query', { body, ...options });
  }

  /**
   * Genai Search
   */
  search(body: AgentSearchParams, options?: RequestOptions): APIPromise<AgentSearchResponse> {
    return this._client.post('/agents/search', { body, ...options });
  }
}

/**
 * Structured chat view: a linear sequence of messages representing the agent
 * trajectory for a single trace.
 */
export interface AgentTraceChatRes {
  agent_name: string | null;

  agent_version: string | null;

  ended_at: string | null;

  feedback: Array<AgentTraceChatRes.Feedback> | null;

  messages: Array<AgentTraceChatRes.Message>;

  provider: string | null;

  root_span_name: string | null;

  started_at: string | null;

  status_code: 'UNSET' | 'OK' | 'ERROR' | null;

  total_cache_creation_input_tokens: number;

  total_cache_read_input_tokens: number;

  total_cost_usd: number | null;

  /**
   * Wall-clock duration of the trace root span in milliseconds. This is not a sum of
   * child span durations.
   */
  total_duration_ms: number | null;

  total_input_tokens: number;

  total_output_tokens: number;

  total_reasoning_tokens: number;

  trace_id: string;

  wb_user_id: string | null;
}

export namespace AgentTraceChatRes {
  /**
   * Feedback row from the agent chat `include_feedback` projection.
   *
   * Field names match FEEDBACK*QUERY_FIELDS. This is not the feedback table row and
   * not FeedbackCreateReq: project_id and span*\* are not selected.
   */
  export interface Feedback {
    id: string;

    annotation_ref: string | null;

    call_ref: string | null;

    created_at: string | null;

    creator: string | null;

    feedback_type: string;

    payload: { [key: string]: unknown };

    runnable_ref: string | null;

    scorer_rating_confidences: { [key: string]: number };

    scorer_rating_reasons: { [key: string]: string };

    scorer_ratings: { [key: string]: number };

    scorer_tag_confidences: { [key: string]: number };

    scorer_tag_reasons: { [key: string]: string };

    scorer_tags: Array<string>;

    trigger_ref: string | null;

    wb_user_id: string | null;

    weave_ref: string;
  }

  /**
   * A single element in the structured agent trajectory / chat view.
   *
   * Common event fields live at the top level. Type-specific fields are grouped
   * under the payload matching `type`, and exactly one payload must be set. This
   * keeps subtype nullability explicit while preserving a single ordered timeline
   * model for callers.
   */
  export interface Message {
    /**
     * Payload for a future agent-to-agent handoff event.
     */
    agent_handoff: unknown | null;

    agent_name: string | null;

    /**
     * Payload for an agent lifecycle boundary.
     */
    agent_start: Message.AgentStart | null;

    agent_version: string | null;

    /**
     * Payload for assistant text emitted by an agent or LLM span.
     */
    assistant_message: Message.AssistantMessage | null;

    /**
     * Payload for a context-window compaction event.
     */
    context_compacted: Message.ContextCompacted | null;

    feedback: Array<Message.Feedback> | null;

    span_id: string | null;

    started_at: string | null;

    status_code: 'UNSET' | 'OK' | 'ERROR' | null;

    /**
     * Payload for a tool call timeline event.
     */
    tool_call: Message.ToolCall | null;

    type:
      | 'user_message'
      | 'assistant_message'
      | 'tool_call'
      | 'agent_handoff'
      | 'agent_start'
      | 'context_compacted';

    /**
     * Payload for a user prompt in the chat timeline.
     */
    user_message: Message.UserMessage | null;
  }

  export namespace Message {
    /**
     * Payload for an agent lifecycle boundary.
     */
    export interface AgentStart {
      model: string | null;

      status: 'UNSET' | 'OK' | 'ERROR' | null;

      system_instructions: string | null;

      tool_definitions: string | null;
    }

    /**
     * Payload for assistant text emitted by an agent or LLM span.
     */
    export interface AssistantMessage {
      content_refs: Array<string>;

      duration_ms: number | null;

      input_cost_usd: number | null;

      input_tokens: number | null;

      model: string | null;

      output_cost_usd: number | null;

      output_tokens: number | null;

      reasoning_content: string | null;

      reasoning_tokens: number | null;

      status: 'UNSET' | 'OK' | 'ERROR' | null;

      text: string;

      total_cost_usd: number | null;
    }

    /**
     * Payload for a context-window compaction event.
     */
    export interface ContextCompacted {
      compaction_items_after: number | null;

      compaction_items_before: number | null;

      compaction_summary: string | null;
    }

    /**
     * Feedback row from the agent chat `include_feedback` projection.
     *
     * Field names match FEEDBACK*QUERY_FIELDS. This is not the feedback table row and
     * not FeedbackCreateReq: project_id and span*\* are not selected.
     */
    export interface Feedback {
      id: string;

      annotation_ref: string | null;

      call_ref: string | null;

      created_at: string | null;

      creator: string | null;

      feedback_type: string;

      payload: { [key: string]: unknown };

      runnable_ref: string | null;

      scorer_rating_confidences: { [key: string]: number };

      scorer_rating_reasons: { [key: string]: string };

      scorer_ratings: { [key: string]: number };

      scorer_tag_confidences: { [key: string]: number };

      scorer_tag_reasons: { [key: string]: string };

      scorer_tags: Array<string>;

      trigger_ref: string | null;

      wb_user_id: string | null;

      weave_ref: string;
    }

    /**
     * Payload for a tool call timeline event.
     */
    export interface ToolCall {
      content_refs: Array<string>;

      duration_ms: number | null;

      status: 'UNSET' | 'OK' | 'ERROR' | null;

      tool_arguments: string | null;

      tool_name: string | null;

      tool_result: string | null;
    }

    /**
     * Payload for a user prompt in the chat timeline.
     */
    export interface UserMessage {
      content_refs: Array<string>;

      text: string;
    }
  }
}

/**
 * Response containing aggregated agent stats.
 */
export interface AgentQueryResponse {
  agents: Array<AgentQueryResponse.Agent>;

  total_count: number;
}

export namespace AgentQueryResponse {
  /**
   * Aggregated per-agent stats from the agents table.
   */
  export interface Agent {
    agent_name: string;

    error_count: number;

    first_seen: string | null;

    invocation_count: number;

    last_seen: string | null;

    project_id: string;

    span_count: number;

    total_cost_usd: number | null;

    total_duration_ms: number;

    total_input_tokens: number;

    total_output_tokens: number;
  }
}

/**
 * Response from a full-text search across agent messages.
 */
export interface AgentSearchResponse {
  results: Array<AgentSearchResponse.Result>;

  total_conversations: number;
}

export namespace AgentSearchResponse {
  /**
   * A conversation containing messages that matched the search query.
   */
  export interface Result {
    agent_name: string;

    conversation_id: string;

    conversation_name: string;

    last_activity: string;

    matched_messages: Array<Result.MatchedMessage>;
  }

  export namespace Result {
    /**
     * A single message that matched the search query.
     */
    export interface MatchedMessage {
      content_digest: string;

      content_preview: string;

      role: '' | 'user' | 'assistant' | 'system' | 'tool' | 'tool_call' | 'tool_result' | (string & {});

      span_id: string;

      started_at: string;

      trace_id: string;
    }
  }
}

export interface AgentQueryParams {
  project_id: string;

  /**
   * Optional filters for querying agents.
   */
  filters?: AgentQueryParams.Filters | null;

  include_costs?: boolean;

  limit?: number;

  offset?: number;

  sort_by?: Array<AgentQueryParams.SortBy> | null;
}

export namespace AgentQueryParams {
  /**
   * Optional filters for querying agents.
   */
  export interface Filters {
    agent_name?: string | null;
  }

  /**
   * Sort specification for agent query endpoints.
   */
  export interface SortBy {
    field: string;

    direction?: 'asc' | 'desc';
  }
}

export interface AgentSearchParams {
  project_id: string;

  agent_name?: string | null;

  conversation_id?: string | null;

  limit?: number;

  offset?: number;

  provider_name?: string | null;

  query?: string;

  request_model?: string | null;

  roles?: Array<'' | 'user' | 'assistant' | 'system' | 'tool' | 'tool_call' | 'tool_result'> | null;

  started_after?: string | null;

  started_before?: string | null;

  trace_id?: string | null;

  truncate_content?: boolean;
}

Agents.Spans = Spans;
Agents.AgentVersions = AgentVersions;
Agents.Traces = Traces;
Agents.Conversations = Conversations;

export declare namespace Agents {
  export {
    type AgentTraceChatRes as AgentTraceChatRes,
    type AgentQueryResponse as AgentQueryResponse,
    type AgentSearchResponse as AgentSearchResponse,
    type AgentQueryParams as AgentQueryParams,
    type AgentSearchParams as AgentSearchParams,
  };

  export {
    Spans as Spans,
    type SpanCustomAttrsSchemaResponse as SpanCustomAttrsSchemaResponse,
    type SpanQueryResponse as SpanQueryResponse,
    type SpanStatsResponse as SpanStatsResponse,
    type SpanCustomAttrsSchemaParams as SpanCustomAttrsSchemaParams,
    type SpanQueryParams as SpanQueryParams,
    type SpanStatsParams as SpanStatsParams,
  };

  export {
    AgentVersions as AgentVersions,
    type AgentVersionQueryResponse as AgentVersionQueryResponse,
    type AgentVersionQueryParams as AgentVersionQueryParams,
  };

  export { Traces as Traces, type TraceChatParams as TraceChatParams };

  export {
    Conversations as Conversations,
    type ConversationChatResponse as ConversationChatResponse,
    type ConversationSpansResponse as ConversationSpansResponse,
    type ConversationChatParams as ConversationChatParams,
    type ConversationSpansParams as ConversationSpansParams,
  };
}
