// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import * as Shared from './shared';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';

export class Calls extends APIResource {
  /**
   * Call Update
   *
   * @example
   * ```ts
   * const call = await client.calls.update({
   *   call_id: 'call_id',
   *   project_id: 'project_id',
   * });
   * ```
   */
  update(body: CallUpdateParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/call/update', { body, ...options });
  }

  /**
   * Calls Delete
   *
   * @example
   * ```ts
   * const call = await client.calls.delete({
   *   call_ids: ['string'],
   *   project_id: 'project_id',
   * });
   * ```
   */
  delete(body: CallDeleteParams, options?: RequestOptions): APIPromise<CallDeleteResponse> {
    return this._client.post('/calls/delete', { body, ...options });
  }

  /**
   * Call End
   *
   * @example
   * ```ts
   * const response = await client.calls.end({
   *   end: {
   *     id: 'id',
   *     ended_at: '2019-12-27T18:11:19.117Z',
   *     project_id: 'project_id',
   *     summary: {},
   *   },
   * });
   * ```
   */
  end(body: CallEndParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/call/end', { body, ...options });
  }

  /**
   * Calls Query Stats
   *
   * @example
   * ```ts
   * const response = await client.calls.queryStats({
   *   project_id: 'project_id',
   * });
   * ```
   */
  queryStats(body: CallQueryStatsParams, options?: RequestOptions): APIPromise<CallQueryStatsResponse> {
    return this._client.post('/calls/query_stats', { body, ...options });
  }

  /**
   * Call Read
   *
   * @example
   * ```ts
   * const response = await client.calls.read({
   *   id: 'id',
   *   project_id: 'project_id',
   * });
   * ```
   */
  read(body: CallReadParams, options?: RequestOptions): APIPromise<CallReadResponse> {
    return this._client.post('/call/read', { body, ...options });
  }

  /**
   * Call Start
   *
   * @example
   * ```ts
   * const response = await client.calls.start({
   *   start: {
   *     attributes: { foo: 'bar' },
   *     inputs: { foo: 'bar' },
   *     op_name: 'op_name',
   *     project_id: 'project_id',
   *     started_at: '2019-12-27T18:11:19.117Z',
   *   },
   * });
   * ```
   */
  start(body: CallStartParams, options?: RequestOptions): APIPromise<CallStartResponse> {
    return this._client.post('/call/start', { body, ...options });
  }

  /**
   * Calls Query Stream
   *
   * @example
   * ```ts
   * const response = await client.calls.streamQuery({
   *   project_id: 'project_id',
   * });
   * ```
   */
  streamQuery(
    params: CallStreamQueryParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<CallStreamQueryResponse>> {
    const { accept, ...body } = params;
    return this._client
      .post('/calls/stream_query', {
        body,
        ...options,
        headers: buildHeaders([
          { Accept: 'application/jsonl', ...(accept != null ? { accept: accept } : undefined) },
          options?.headers,
        ]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<CallStreamQueryResponse>
    >;
  }

  /**
   * Call Start Batch
   *
   * @example
   * ```ts
   * const response = await client.calls.upsertBatch({
   *   batch: [
   *     {
   *       req: {
   *         start: {
   *           attributes: { foo: 'bar' },
   *           inputs: { foo: 'bar' },
   *           op_name: 'op_name',
   *           project_id: 'project_id',
   *           started_at: '2019-12-27T18:11:19.117Z',
   *         },
   *       },
   *     },
   *   ],
   * });
   * ```
   */
  upsertBatch(body: CallUpsertBatchParams, options?: RequestOptions): APIPromise<CallUpsertBatchResponse> {
    return this._client.post('/call/upsert_batch', { body, ...options });
  }

  /**
   * Compute aggregated usage for multiple root calls, with descendant rollup.
   *
   * @example
   * ```ts
   * const response = await client.calls.usage({
   *   call_ids: ['string'],
   *   project_id: 'project_id',
   * });
   * ```
   */
  usage(body: CallUsageParams, options?: RequestOptions): APIPromise<CallUsageResponse> {
    return this._client.post('/calls/usage', { body, ...options });
  }
}

export type CallUpdateResponse = unknown;

export interface CallDeleteResponse {
  /**
   * The number of calls deleted
   */
  num_deleted: number;
}

export type CallEndResponse = unknown;

export interface CallQueryStatsResponse {
  count: number;

  has_more?: boolean;

  total_storage_size_bytes?: number | null;
}

export interface CallReadResponse {
  call: CallReadResponse.Call | null;
}

export namespace CallReadResponse {
  export interface Call {
    id: string;

    attributes: { [key: string]: unknown };

    inputs: { [key: string]: unknown };

    op_name: string;

    project_id: string;

    started_at: string;

    trace_id: string;

    deleted_at?: string | null;

    display_name?: string | null;

    ended_at?: string | null;

    exception?: string | null;

    /**
     * Expiration timestamp for this call. None = no TTL configured for the project
     * (the row will not be expired).
     */
    expire_at?: string | null;

    output?: unknown;

    parent_id?: string | null;

    storage_size_bytes?: number | null;

    summary?: { [key: string]: unknown };

    thread_id?: string | null;

    total_storage_size_bytes?: number | null;

    turn_id?: string | null;

    wb_run_id?: string | null;

    wb_run_step?: number | null;

    wb_run_step_end?: number | null;

    wb_user_id?: string | null;

    wb_username?: string | null;
  }
}

export interface CallStartResponse {
  id: string;

  trace_id: string;
}

export type CallStreamQueryResponse = unknown;

export interface CallUpsertBatchResponse {
  res: Array<CallUpsertBatchResponse.CallStartRes | unknown>;
}

export namespace CallUpsertBatchResponse {
  export interface CallStartRes {
    id: string;

    trace_id: string;
  }
}

/**
 * Response with aggregated usage metrics per root call.
 */
export interface CallUsageResponse {
  call_usage?: { [key: string]: { [key: string]: CallUsageResponse.LLMAggregatedUsage } };

  unfinished_call_ids?: Array<string>;
}

export namespace CallUsageResponse {
  /**
   * Aggregated usage metrics for a specific LLM.
   */
  export interface LLMAggregatedUsage {
    cache_creation_input_tokens?: number;

    cache_creation_input_tokens_total_cost?: number | null;

    cache_read_input_tokens?: number;

    cache_read_input_tokens_total_cost?: number | null;

    completion_tokens?: number;

    completion_tokens_total_cost?: number | null;

    prompt_tokens?: number;

    prompt_tokens_total_cost?: number | null;

    requests?: number;

    total_tokens?: number;
  }
}

export interface CallUpdateParams {
  call_id: string;

  project_id: string;

  display_name?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface CallDeleteParams {
  call_ids: Array<string>;

  project_id: string;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface CallEndParams {
  end: CallEndParams.End;
}

export namespace CallEndParams {
  export interface End {
    id: string;

    ended_at: string;

    project_id: string;

    summary: End.Summary;

    exception?: string | null;

    is_eval?: boolean | null;

    output?: unknown;

    started_at?: string | null;

    trace_id?: string | null;

    wb_run_step_end?: number | null;
  }

  export namespace End {
    export interface Summary {
      status_counts?: { [key: string]: number };

      usage?: { [key: string]: Summary.Usage };

      [k: string]: unknown;
    }

    export namespace Summary {
      export interface Usage {
        cache_creation_input_tokens?: number | null;

        cache_read_input_tokens?: number | null;

        completion_tokens?: number | null;

        input_tokens?: number | null;

        output_tokens?: number | null;

        prompt_tokens?: number | null;

        requests?: number | null;

        total_tokens?: number | null;

        [k: string]: unknown;
      }
    }
  }
}

export interface CallQueryStatsParams {
  project_id: string;

  /**
   * Columns with refs to objects or table rows that require expansion during
   * filtering or ordering.
   */
  expand_columns?: Array<string> | null;

  filter?: CallQueryStatsParams.Filter | null;

  include_total_storage_size?: boolean | null;

  limit?: number | null;

  query?: CallQueryStatsParams.Query | null;
}

export namespace CallQueryStatsParams {
  export interface Filter {
    call_ids?: Array<string> | null;

    input_refs?: Array<string> | null;

    op_names?: Array<string> | null;

    output_refs?: Array<string> | null;

    parent_ids?: Array<string> | null;

    thread_ids?: Array<string> | null;

    trace_ids?: Array<string> | null;

    trace_roots_only?: boolean | null;

    turn_ids?: Array<string> | null;

    wb_run_ids?: Array<string> | null;

    wb_user_ids?: Array<string> | null;
  }

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

export interface CallReadParams {
  id: string;

  project_id: string;

  include_costs?: boolean | null;

  include_storage_size?: boolean | null;

  include_total_storage_size?: boolean | null;
}

export interface CallStartParams {
  start: CallStartParams.Start;
}

export namespace CallStartParams {
  export interface Start {
    attributes: { [key: string]: unknown };

    inputs: { [key: string]: unknown };

    op_name: string;

    project_id: string;

    started_at: string;

    id?: string | null;

    display_name?: string | null;

    otel_dump?: { [key: string]: unknown } | null;

    parent_id?: string | null;

    thread_id?: string | null;

    trace_id?: string | null;

    turn_id?: string | null;

    wb_run_id?: string | null;

    wb_run_step?: number | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }
}

export interface CallStreamQueryParams {
  /**
   * Body param
   */
  project_id: string;

  /**
   * Body param
   */
  columns?: Array<string> | null;

  /**
   * Body param: Columns to expand, i.e. refs to other objects
   */
  expand_columns?: Array<string> | null;

  /**
   * Body param
   */
  filter?: CallStreamQueryParams.Filter | null;

  /**
   * Body param: Beta, subject to change. If true, the response will include any
   * model costs for each call.
   */
  include_costs?: boolean | null;

  /**
   * Body param: Beta, subject to change. If true, the response will include feedback
   * for each call.
   */
  include_feedback?: boolean | null;

  /**
   * Body param: Beta, subject to change. If true, the response will include the
   * storage size for a call.
   */
  include_storage_size?: boolean | null;

  /**
   * Body param: Beta, subject to change. If true, the response will include the
   * total storage size for a trace.
   */
  include_total_storage_size?: boolean | null;

  /**
   * Body param: If true, the response will attempt to resolve each call's wb_user_id
   * to a username for the duration of this request.
   */
  include_usernames?: boolean | null;

  /**
   * Body param
   */
  limit?: number | null;

  /**
   * Body param
   */
  offset?: number | null;

  /**
   * Body param
   */
  query?: CallStreamQueryParams.Query | null;

  /**
   * Body param: If true, the response will include raw values for expanded columns.
   * If false, the response expand_columns will only be used for filtering and
   * ordering. This is useful for clients that want to resolve refs themselves, e.g.
   * for performance reasons.
   */
  return_expanded_column_values?: boolean | null;

  /**
   * Body param
   */
  sort_by?: Array<CallStreamQueryParams.SortBy> | null;

  /**
   * Header param
   */
  accept?: string;
}

export namespace CallStreamQueryParams {
  export interface Filter {
    call_ids?: Array<string> | null;

    input_refs?: Array<string> | null;

    op_names?: Array<string> | null;

    output_refs?: Array<string> | null;

    parent_ids?: Array<string> | null;

    thread_ids?: Array<string> | null;

    trace_ids?: Array<string> | null;

    trace_roots_only?: boolean | null;

    turn_ids?: Array<string> | null;

    wb_run_ids?: Array<string> | null;

    wb_user_ids?: Array<string> | null;
  }

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

export interface CallUpsertBatchParams {
  batch: Array<CallUpsertBatchParams.CallBatchStartMode | CallUpsertBatchParams.CallBatchEndMode>;
}

export namespace CallUpsertBatchParams {
  export interface CallBatchStartMode {
    req: CallBatchStartMode.Req;

    mode?: string;
  }

  export namespace CallBatchStartMode {
    export interface Req {
      start: Req.Start;
    }

    export namespace Req {
      export interface Start {
        attributes: { [key: string]: unknown };

        inputs: { [key: string]: unknown };

        op_name: string;

        project_id: string;

        started_at: string;

        id?: string | null;

        display_name?: string | null;

        otel_dump?: { [key: string]: unknown } | null;

        parent_id?: string | null;

        thread_id?: string | null;

        trace_id?: string | null;

        turn_id?: string | null;

        wb_run_id?: string | null;

        wb_run_step?: number | null;

        /**
         * Do not set directly. Server will automatically populate this field.
         */
        wb_user_id?: string | null;
      }
    }
  }

  export interface CallBatchEndMode {
    req: CallBatchEndMode.Req;

    mode?: string;
  }

  export namespace CallBatchEndMode {
    export interface Req {
      end: Req.End;
    }

    export namespace Req {
      export interface End {
        id: string;

        ended_at: string;

        project_id: string;

        summary: End.Summary;

        exception?: string | null;

        is_eval?: boolean | null;

        output?: unknown;

        started_at?: string | null;

        trace_id?: string | null;

        wb_run_step_end?: number | null;
      }

      export namespace End {
        export interface Summary {
          status_counts?: { [key: string]: number };

          usage?: { [key: string]: Summary.Usage };

          [k: string]: unknown;
        }

        export namespace Summary {
          export interface Usage {
            cache_creation_input_tokens?: number | null;

            cache_read_input_tokens?: number | null;

            completion_tokens?: number | null;

            input_tokens?: number | null;

            output_tokens?: number | null;

            prompt_tokens?: number | null;

            requests?: number | null;

            total_tokens?: number | null;

            [k: string]: unknown;
          }
        }
      }
    }
  }
}

export interface CallUsageParams {
  /**
   * Root call IDs to aggregate. Each result key corresponds to one input call ID.
   */
  call_ids: Array<string>;

  project_id: string;

  /**
   * If true, include cost calculations in the usage.
   */
  include_costs?: boolean;

  /**
   * Maximum number of calls to process across all traces. Acts as a safety limit to
   * prevent unbounded memory usage.
   */
  limit?: number;
}

export declare namespace Calls {
  export {
    type CallUpdateResponse as CallUpdateResponse,
    type CallDeleteResponse as CallDeleteResponse,
    type CallEndResponse as CallEndResponse,
    type CallQueryStatsResponse as CallQueryStatsResponse,
    type CallReadResponse as CallReadResponse,
    type CallStartResponse as CallStartResponse,
    type CallStreamQueryResponse as CallStreamQueryResponse,
    type CallUpsertBatchResponse as CallUpsertBatchResponse,
    type CallUsageResponse as CallUsageResponse,
    type CallUpdateParams as CallUpdateParams,
    type CallDeleteParams as CallDeleteParams,
    type CallEndParams as CallEndParams,
    type CallQueryStatsParams as CallQueryStatsParams,
    type CallReadParams as CallReadParams,
    type CallStartParams as CallStartParams,
    type CallStreamQueryParams as CallStreamQueryParams,
    type CallUpsertBatchParams as CallUpsertBatchParams,
    type CallUsageParams as CallUsageParams,
  };
}
