// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import * as Shared from './shared';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Feedback extends APIResource {
  /**
   * Add feedback to a call or object.
   *
   * @example
   * ```ts
   * const feedback = await client.feedback.create({
   *   feedback_type: 'custom',
   *   payload: { key: 'bar' },
   *   project_id: 'entity/project',
   *   weave_ref: 'weave:///entity/project/object/name:digest',
   * });
   * ```
   */
  create(body: FeedbackCreateParams, options?: RequestOptions): APIPromise<FeedbackCreateResponse> {
    return this._client.post('/feedback/create', { body, ...options });
  }

  /**
   * Add multiple feedback items to calls or objects.
   *
   * @example
   * ```ts
   * const response = await client.feedback.batchCreate({
   *   batch: [
   *     {
   *       feedback_type: 'custom',
   *       payload: { key: 'bar' },
   *       project_id: 'entity/project',
   *       weave_ref:
   *         'weave:///entity/project/object/name:digest',
   *     },
   *   ],
   * });
   * ```
   */
  batchCreate(
    body: FeedbackBatchCreateParams,
    options?: RequestOptions,
  ): APIPromise<FeedbackBatchCreateResponse> {
    return this._client.post('/feedback/batch/create', { body, ...options });
  }

  /**
   * Permanently delete feedback.
   *
   * @example
   * ```ts
   * const response = await client.feedback.purge({
   *   project_id: 'entity/project',
   *   query: { $expr: { $and: [{ $literal: 'string' }] } },
   * });
   * ```
   */
  purge(body: FeedbackPurgeParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/feedback/purge', { body, ...options });
  }

  /**
   * Query for feedback.
   *
   * @example
   * ```ts
   * const response = await client.feedback.query({
   *   project_id: 'entity/project',
   * });
   * ```
   */
  query(body: FeedbackQueryParams, options?: RequestOptions): APIPromise<FeedbackQueryResponse> {
    return this._client.post('/feedback/query', { body, ...options });
  }

  /**
   * Feedback Replace
   *
   * @example
   * ```ts
   * const response = await client.feedback.replace({
   *   feedback_id: 'feedback_id',
   *   feedback_type: 'custom',
   *   payload: { key: 'bar' },
   *   project_id: 'entity/project',
   *   weave_ref: 'weave:///entity/project/object/name:digest',
   * });
   * ```
   */
  replace(body: FeedbackReplaceParams, options?: RequestOptions): APIPromise<FeedbackReplaceResponse> {
    return this._client.post('/feedback/replace', { body, ...options });
  }
}

export interface FeedbackCreateResponse {
  id: string;

  created_at: string;

  payload: { [key: string]: unknown };

  wb_user_id: string;
}

export interface FeedbackBatchCreateResponse {
  res: Array<FeedbackBatchCreateResponse.Re>;
}

export namespace FeedbackBatchCreateResponse {
  export interface Re {
    id: string;

    created_at: string;

    payload: { [key: string]: unknown };

    wb_user_id: string;
  }
}

export type FeedbackPurgeResponse = unknown;

export interface FeedbackQueryResponse {
  result: Array<{ [key: string]: unknown }>;

  total_count: number;
}

export interface FeedbackReplaceResponse {
  id: string;

  created_at: string;

  payload: { [key: string]: unknown };

  wb_user_id: string;
}

export interface FeedbackCreateParams {
  feedback_type: string;

  payload: { [key: string]: unknown };

  project_id: string;

  weave_ref: string;

  /**
   * If provided by the client, this ID will be used for the feedback row instead of
   * a server-generated one.
   */
  id?: string | null;

  annotation_ref?: string | null;

  call_ref?: string | null;

  creator?: string | null;

  /**
   * The annotation queue ID this feedback was created from. References
   * annotation_queues.id. NULL when feedback is created outside of queues.
   */
  queue_id?: string | null;

  runnable_ref?: string | null;

  /**
   * confidence (0-1) per rating, keyed by rating name
   */
  scorer_rating_confidences?: { [key: string]: number };

  /**
   * reason text per rating, keyed by rating name
   */
  scorer_rating_reasons?: { [key: string]: string };

  /**
   * numeric ratings (0-1) keyed by rating name
   */
  scorer_ratings?: { [key: string]: number };

  /**
   * confidence (0-1) per tag, keyed by tag name
   */
  scorer_tag_confidences?: { [key: string]: number };

  /**
   * reason text per tag, keyed by tag name
   */
  scorer_tag_reasons?: { [key: string]: string };

  /**
   * Tags applied to the ref by a scorer
   */
  scorer_tags?: Array<string>;

  /**
   * Trace of the scorer (judge) invocation that produced this feedback
   * (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
   * scored turn. Lets signals price the invocation off the judge span without
   * joining the calls model.
   */
  scorer_trace_id?: string;

  /**
   * Display name of the scored agent (from spans.agent_name)
   */
  span_agent_name?: string;

  /**
   * Version of the scored agent (from spans.agent_version)
   */
  span_agent_version?: string;

  /**
   * Conversation the feedback belongs to (from spans.conversation_id)
   */
  span_conversation_id?: string;

  /**
   * Status of the scored turn (from spans.status_code)
   */
  span_status_code?: string;

  /**
   * Turn the feedback belongs to (from spans.trace_id)
   */
  span_trace_id?: string;

  trigger_ref?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface FeedbackBatchCreateParams {
  batch: Array<FeedbackBatchCreateParams.Batch>;
}

export namespace FeedbackBatchCreateParams {
  export interface Batch {
    feedback_type: string;

    payload: { [key: string]: unknown };

    project_id: string;

    weave_ref: string;

    /**
     * If provided by the client, this ID will be used for the feedback row instead of
     * a server-generated one.
     */
    id?: string | null;

    annotation_ref?: string | null;

    call_ref?: string | null;

    creator?: string | null;

    /**
     * The annotation queue ID this feedback was created from. References
     * annotation_queues.id. NULL when feedback is created outside of queues.
     */
    queue_id?: string | null;

    runnable_ref?: string | null;

    /**
     * confidence (0-1) per rating, keyed by rating name
     */
    scorer_rating_confidences?: { [key: string]: number };

    /**
     * reason text per rating, keyed by rating name
     */
    scorer_rating_reasons?: { [key: string]: string };

    /**
     * numeric ratings (0-1) keyed by rating name
     */
    scorer_ratings?: { [key: string]: number };

    /**
     * confidence (0-1) per tag, keyed by tag name
     */
    scorer_tag_confidences?: { [key: string]: number };

    /**
     * reason text per tag, keyed by tag name
     */
    scorer_tag_reasons?: { [key: string]: string };

    /**
     * Tags applied to the ref by a scorer
     */
    scorer_tags?: Array<string>;

    /**
     * Trace of the scorer (judge) invocation that produced this feedback
     * (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
     * scored turn. Lets signals price the invocation off the judge span without
     * joining the calls model.
     */
    scorer_trace_id?: string;

    /**
     * Display name of the scored agent (from spans.agent_name)
     */
    span_agent_name?: string;

    /**
     * Version of the scored agent (from spans.agent_version)
     */
    span_agent_version?: string;

    /**
     * Conversation the feedback belongs to (from spans.conversation_id)
     */
    span_conversation_id?: string;

    /**
     * Status of the scored turn (from spans.status_code)
     */
    span_status_code?: string;

    /**
     * Turn the feedback belongs to (from spans.trace_id)
     */
    span_trace_id?: string;

    trigger_ref?: string | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }
}

export interface FeedbackPurgeParams {
  project_id: string;

  query: FeedbackPurgeParams.Query;
}

export namespace FeedbackPurgeParams {
  export interface Query {
    /**
     * Logical AND. All conditions must evaluate to true.
     *
     * Example:
     * ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
     */
    $expr:
      | Shared.AndOperation
      | Shared.OrOperation
      | Shared.NotOperation
      | Shared.EqOperation
      | Shared.GtOperation
      | Query.LtOperation
      | Shared.GteOperation
      | Query.LteOperation
      | Shared.InOperation
      | Shared.ContainsOperation;
  }

  export namespace Query {
    /**
     * Less than comparison.
     *
     * Example:
     * ` { "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LtOperation {
      $lt: Array<unknown>;
    }

    /**
     * Less than or equal comparison.
     *
     * Example:
     * ` { "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LteOperation {
      $lte: Array<unknown>;
    }
  }
}

export interface FeedbackQueryParams {
  project_id: string;

  fields?: Array<string> | null;

  limit?: number | null;

  offset?: number | null;

  query?: FeedbackQueryParams.Query | null;

  sort_by?: Array<FeedbackQueryParams.SortBy> | null;
}

export namespace FeedbackQueryParams {
  export interface Query {
    /**
     * Logical AND. All conditions must evaluate to true.
     *
     * Example:
     * ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
     */
    $expr:
      | Shared.AndOperation
      | Shared.OrOperation
      | Shared.NotOperation
      | Shared.EqOperation
      | Shared.GtOperation
      | Query.LtOperation
      | Shared.GteOperation
      | Query.LteOperation
      | Shared.InOperation
      | Shared.ContainsOperation;
  }

  export namespace Query {
    /**
     * Less than comparison.
     *
     * Example:
     * ` { "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LtOperation {
      $lt: Array<unknown>;
    }

    /**
     * Less than or equal comparison.
     *
     * Example:
     * ` { "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LteOperation {
      $lte: Array<unknown>;
    }
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export interface FeedbackReplaceParams {
  feedback_id: string;

  feedback_type: string;

  payload: { [key: string]: unknown };

  project_id: string;

  weave_ref: string;

  /**
   * If provided by the client, this ID will be used for the feedback row instead of
   * a server-generated one.
   */
  id?: string | null;

  annotation_ref?: string | null;

  call_ref?: string | null;

  creator?: string | null;

  /**
   * The annotation queue ID this feedback was created from. References
   * annotation_queues.id. NULL when feedback is created outside of queues.
   */
  queue_id?: string | null;

  runnable_ref?: string | null;

  /**
   * confidence (0-1) per rating, keyed by rating name
   */
  scorer_rating_confidences?: { [key: string]: number };

  /**
   * reason text per rating, keyed by rating name
   */
  scorer_rating_reasons?: { [key: string]: string };

  /**
   * numeric ratings (0-1) keyed by rating name
   */
  scorer_ratings?: { [key: string]: number };

  /**
   * confidence (0-1) per tag, keyed by tag name
   */
  scorer_tag_confidences?: { [key: string]: number };

  /**
   * reason text per tag, keyed by tag name
   */
  scorer_tag_reasons?: { [key: string]: string };

  /**
   * Tags applied to the ref by a scorer
   */
  scorer_tags?: Array<string>;

  /**
   * Trace of the scorer (judge) invocation that produced this feedback
   * (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
   * scored turn. Lets signals price the invocation off the judge span without
   * joining the calls model.
   */
  scorer_trace_id?: string;

  /**
   * Display name of the scored agent (from spans.agent_name)
   */
  span_agent_name?: string;

  /**
   * Version of the scored agent (from spans.agent_version)
   */
  span_agent_version?: string;

  /**
   * Conversation the feedback belongs to (from spans.conversation_id)
   */
  span_conversation_id?: string;

  /**
   * Status of the scored turn (from spans.status_code)
   */
  span_status_code?: string;

  /**
   * Turn the feedback belongs to (from spans.trace_id)
   */
  span_trace_id?: string;

  trigger_ref?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export declare namespace Feedback {
  export {
    type FeedbackCreateResponse as FeedbackCreateResponse,
    type FeedbackBatchCreateResponse as FeedbackBatchCreateResponse,
    type FeedbackPurgeResponse as FeedbackPurgeResponse,
    type FeedbackQueryResponse as FeedbackQueryResponse,
    type FeedbackReplaceResponse as FeedbackReplaceResponse,
    type FeedbackCreateParams as FeedbackCreateParams,
    type FeedbackBatchCreateParams as FeedbackBatchCreateParams,
    type FeedbackPurgeParams as FeedbackPurgeParams,
    type FeedbackQueryParams as FeedbackQueryParams,
    type FeedbackReplaceParams as FeedbackReplaceParams,
  };
}
