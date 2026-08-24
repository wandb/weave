// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as AgentsAPI from './agents';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Conversations extends APIResource {
  /**
   * Genai Conversation Chat
   */
  chat(body: ConversationChatParams, options?: RequestOptions): APIPromise<ConversationChatResponse> {
    return this._client.post('/agents/conversations/chat', { body, ...options });
  }

  /**
   * Genai Conversation Spans
   */
  spans(body: ConversationSpansParams, options?: RequestOptions): APIPromise<ConversationSpansResponse> {
    return this._client.post('/agents/conversations/spans', { body, ...options });
  }
}

/**
 * Multi-turn chat view: an ordered list of per-turn chat responses.
 *
 * Each entry in `turns` corresponds to one trace_id, which Weave treats as one
 * conversation turn. This is not necessarily one `invoke_agent` span: a turn can
 * contain zero, one, or many agent invocations. The frontend can render
 * turn-number dividers between entries and still reuse `AgentTraceChatRes`
 * rendering for each individual turn.
 */
export interface ConversationChatResponse {
  conversation_id: string;

  feedback?: Array<{ [key: string]: unknown }> | null;

  has_more?: boolean;

  limit?: number;

  offset?: number;

  total_cost_usd?: number | null;

  total_turns?: number;

  turns?: Array<AgentsAPI.AgentTraceChatRes>;
}

/**
 * Span sequences + feedback markers, one entry per requested conversation.
 */
export interface ConversationSpansResponse {
  conversations?: Array<ConversationSpansResponse.Conversation>;
}

export namespace ConversationSpansResponse {
  /**
   * One conversation's span sequence and its feedback markers.
   */
  export interface Conversation {
    conversation_id: string;

    spans?: Array<Conversation.Span>;

    spans_feedback?: Array<Conversation.SpansFeedback>;
  }

  export namespace Conversation {
    /**
     * One span in a conversation's trace.
     *
     * Returned by `agent_conversation_spans`, which reads span scalar columns only (no
     * message bodies). Spans are ordered by `started_at`, which approximates — but
     * does not exactly match — the detail chat view's parent/child tree-walk order.
     * `operation_name` is the raw OTel value; the client maps it to a display
     * category.
     */
    export interface Span {
      duration_ms: number;

      operation_name: string;

      span_id: string;

      status: 'UNSET' | 'OK' | 'ERROR';

      trace_id: string;
    }

    /**
     * Tags and ratings applied to a conversation's turn (or the conversation).
     *
     * Positioned client-side by matching `trace_id` (turn) against the spans;
     * `trace_id` is None for conversation-level feedback.
     */
    export interface SpansFeedback {
      feedback_type: 'wandb.agent_user_feedback' | 'wandb.agent_monitor';

      /**
       * The turn this feedback is anchored to; None for conversation-level.
       */
      trace_id: string | null;

      /**
       * Numeric scorer ratings applied to this feedback.
       */
      ratings?: Array<SpansFeedback.Rating>;

      /**
       * Arbitrary descriptive tags applied to this feedback.
       */
      tags?: Array<string>;
    }

    export namespace SpansFeedback {
      /**
       * One numeric rating (a scorer score) applied to a turn or conversation.
       */
      export interface Rating {
        name: string;

        value: number;

        confidence?: number | null;

        reason?: string | null;
      }
    }
  }
}

export interface ConversationChatParams {
  conversation_id: string;

  project_id: string;

  include_feedback?: boolean;

  /**
   * Maximum number of conversation turns to return.
   */
  limit?: number;

  /**
   * Number of most-recent turns to skip. Results are returned in chronological order
   * within the selected page.
   */
  offset?: number;
}

export interface ConversationSpansParams {
  project_id: string;

  conversation_ids?: Array<string>;

  started_after?: string | null;

  started_before?: string | null;
}

export declare namespace Conversations {
  export {
    type ConversationChatResponse as ConversationChatResponse,
    type ConversationSpansResponse as ConversationSpansResponse,
    type ConversationChatParams as ConversationChatParams,
    type ConversationSpansParams as ConversationSpansParams,
  };
}
