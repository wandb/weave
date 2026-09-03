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
   * Aggregate typed scorer feedback (tags, ratings) over time buckets.
   *
   * @example
   * ```ts
   * const response = await client.feedback.aggregate({
   *   after_ms: 0,
   *   before_ms: 0,
   *   project_id: 'entity/project',
   * });
   * ```
   */
  aggregate(body: FeedbackAggregateParams, options?: RequestOptions): APIPromise<FeedbackAggregateResponse> {
    return this._client.post('/feedback/aggregate', { body, ...options });
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
   * Discover feedback payload schema (paths and types) from sample rows.
   *
   * @example
   * ```ts
   * const response = await client.feedback.payloadSchema({
   *   project_id: 'project_id',
   *   start: '2019-12-27T18:11:19.117Z',
   * });
   * ```
   */
  payloadSchema(
    body: FeedbackPayloadSchemaParams,
    options?: RequestOptions,
  ): APIPromise<FeedbackPayloadSchemaResponse> {
    return this._client.post('/feedback/payload_schema', { body, ...options });
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

  /**
   * Return aggregated feedback statistics over time buckets.
   *
   * @example
   * ```ts
   * const response = await client.feedback.stats({
   *   project_id: 'project_id',
   *   start: '2019-12-27T18:11:19.117Z',
   * });
   * ```
   */
  stats(body: FeedbackStatsParams, options?: RequestOptions): APIPromise<FeedbackStatsResponse> {
    return this._client.post('/feedback/stats', { body, ...options });
  }
}

export interface FeedbackCreateResponse {
  id: string;

  created_at: string;

  payload: { [key: string]: unknown };

  wb_user_id: string;
}

/**
 * Sparse time-series of aggregated scorer feedback (empty buckets omitted).
 */
export interface FeedbackAggregateResponse {
  /**
   * Resolved inclusive lower bound, unix epoch ms (UTC).
   */
  after_ms: number;

  /**
   * Resolved exclusive upper bound, unix epoch ms (UTC).
   */
  before_ms: number;

  buckets?: Array<FeedbackAggregateResponse.Bucket>;

  /**
   * Time bucket size used (seconds). None when unbucketed.
   */
  time_bucket_seconds?: number | null;
}

export namespace FeedbackAggregateResponse {
  /**
   * One (time bucket, group) row of aggregated scorer feedback.
   */
  export interface Bucket {
    /**
     * Rows that emitted a score (at least one tag or rating). Excludes agent-monitor
     * rows that scored nothing — use this for score volume.
     */
    scored_count: number;

    /**
     * Number of feedback rows in this bucket/group.
     */
    total_count: number;

    /**
     * Group-by dimension values for this row (e.g. {'scorer_id': '...'}).
     */
    group?: { [key: string]: string };

    /**
     * Number of rows carrying each rating key (e.g. '_rating_').
     */
    rating_counts?: { [key: string]: number };

    /**
     * Sum of each rating key's values; client derives avg = sum/count.
     */
    rating_sums?: { [key: string]: number };

    /**
     * Count of each scorer tag.
     */
    tag_counts?: { [key: string]: number };

    /**
     * Time bucket start, unix epoch ms (UTC). None when unbucketed.
     */
    time_bucket_start_ms?: number | null;
  }
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

/**
 * Response with discovered feedback payload paths and types.
 */
export interface FeedbackPayloadSchemaResponse {
  /**
   * Discovered leaf paths with inferred value types.
   */
  paths?: Array<FeedbackPayloadSchemaResponse.Path>;
}

export namespace FeedbackPayloadSchemaResponse {
  /**
   * Discovered path in feedback payload with inferred type.
   */
  export interface Path {
    /**
     * Dot path into payload (e.g. 'output.score').
     */
    json_path: string;

    /**
     * Inferred type of value at path.
     */
    value_type?: 'numeric' | 'boolean' | 'categorical';
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

/**
 * Response with time-series feedback statistics.
 */
export interface FeedbackStatsResponse {
  /**
   * Resolved end time (always UTC, regardless of the requested timezone).
   */
  end: string;

  /**
   * Bucket size used (in seconds)
   */
  granularity: number;

  /**
   * Resolved start time (always UTC, regardless of the requested timezone).
   */
  start: string;

  /**
   * Timezone used for bucket alignment
   */
  timezone: string;

  /**
   * Time-bucketed aggregations. Each dict has 'timestamp' (ISO string), 'count'
   * (int), and '{agg}\_{slug}' keys for each requested metric+aggregation.
   */
  buckets?: Array<{ [key: string]: unknown }>;

  /**
   * Aggregations over the full query window, keyed by metric slug (e.g.
   * 'output_score'). Each value maps agg name to result.
   */
  window_stats?: { [key: string]: { [key: string]: number | null } } | null;
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

export interface FeedbackAggregateParams {
  /**
   * Inclusive lower bound on created_at (milliseconds since epoch).
   */
  after_ms: number;

  /**
   * Exclusive upper bound on created_at (milliseconds since epoch).
   */
  before_ms: number;

  project_id: string;

  /**
   * Filter on feedback_type by prefix
   */
  feedback_types?: Array<string>;

  /**
   * Allowed: ['scorer_id', 'span_agent_name', 'span_agent_version',
   * 'span_status_code'].
   */
  group_by?: Array<'scorer_id' | 'span_agent_name' | 'span_agent_version' | 'span_status_code'>;

  /**
   * Filter to these monitor ids (exact match; suffix with '\*' for prefix match).
   */
  monitor_ids?: Array<string>;

  /**
   * Include only rows with a rating <= this value
   */
  rating_max?: number | null;

  /**
   * Include only rows with a rating >= this value
   */
  rating_min?: number | null;

  /**
   * Filter to these scorer ids (exact match; suffix with '\*' for prefix match).
   */
  scorer_ids?: Array<string>;

  /**
   * Filter to feedback whose span_agent_name matches any of these (exact).
   */
  span_agent_names?: Array<string>;

  /**
   * Filter by span type (turn vs conversation).
   */
  span_types?: Array<'agent_turn' | 'agent_conversation'>;

  /**
   * Filter to feedback that includes any of the given tags
   */
  tags?: Array<string>;

  /**
   * Time bucket size in seconds, e.g. 3600 for 1h buckets
   */
  time_bucket_seconds?: number | null;
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

export interface FeedbackPayloadSchemaParams {
  project_id: string;

  /**
   * Inclusive start time (UTC, ISO 8601).
   */
  start: string;

  /**
   * Exclusive end time (UTC, ISO 8601). Defaults to now if omitted.
   */
  end?: string | null;

  /**
   * Filter by feedback_type.
   */
  feedback_type?: string | null;

  /**
   * Max distinct trigger_refs to sample when discovering the payload schema. Each
   * distinct trigger_ref (monitor/source) typically has a fixed payload structure,
   * so sampling one payload per ref is usually enough to see the full schema. 2 000
   * covers virtually all real-world projects while keeping the query fast; the hard
   * cap of 5 000 prevents runaway scans.
   */
  sample_limit?: number;

  /**
   * Filter by trigger_ref (exact or prefix match for all-versions).
   */
  trigger_ref?: string | null;
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

export interface FeedbackStatsParams {
  project_id: string;

  /**
   * Inclusive start time (UTC, ISO 8601).
   */
  start: string;

  /**
   * Exclusive end time (UTC, ISO 8601). Defaults to now if omitted.
   */
  end?: string | null;

  /**
   * Filter by feedback_type.
   */
  feedback_type?: string | null;

  /**
   * Bucket size in seconds. If omitted, auto-selected based on time range.
   */
  granularity?: number | null;

  /**
   * Metrics to aggregate from payload_dump.
   */
  metrics?: Array<FeedbackStatsParams.Metric>;

  /**
   * IANA timezone for bucket alignment.
   */
  timezone?: string;

  /**
   * Filter by trigger_ref (exact or prefix match for all-versions).
   */
  trigger_ref?: string | null;
}

export namespace FeedbackStatsParams {
  /**
   * Specification for a feedback payload metric to aggregate.
   */
  export interface Metric {
    /**
     * Dot path into payload_dump (e.g. 'output', 'output.score').
     */
    json_path: string;

    /**
     * Aggregation functions to compute. If empty, defaults are chosen based on
     * value_type: numeric->avg/min/max, boolean->count_true/count_false.
     */
    aggregations?: Array<'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_true' | 'count_false'>;

    /**
     * Percentile values to compute (0–100), e.g. [5, 50, 95]. Only applicable for
     * numeric value_type fields; ignored for boolean/categorical.
     */
    percentiles?: Array<number>;

    /**
     * Type of value at path. numeric: avg/min/max; boolean: count_true/count_false.
     */
    value_type?: 'numeric' | 'boolean' | 'categorical';
  }
}

export declare namespace Feedback {
  export {
    type FeedbackCreateResponse as FeedbackCreateResponse,
    type FeedbackAggregateResponse as FeedbackAggregateResponse,
    type FeedbackBatchCreateResponse as FeedbackBatchCreateResponse,
    type FeedbackPayloadSchemaResponse as FeedbackPayloadSchemaResponse,
    type FeedbackPurgeResponse as FeedbackPurgeResponse,
    type FeedbackQueryResponse as FeedbackQueryResponse,
    type FeedbackReplaceResponse as FeedbackReplaceResponse,
    type FeedbackStatsResponse as FeedbackStatsResponse,
    type FeedbackCreateParams as FeedbackCreateParams,
    type FeedbackAggregateParams as FeedbackAggregateParams,
    type FeedbackBatchCreateParams as FeedbackBatchCreateParams,
    type FeedbackPayloadSchemaParams as FeedbackPayloadSchemaParams,
    type FeedbackPurgeParams as FeedbackPurgeParams,
    type FeedbackQueryParams as FeedbackQueryParams,
    type FeedbackReplaceParams as FeedbackReplaceParams,
    type FeedbackStatsParams as FeedbackStatsParams,
  };
}
