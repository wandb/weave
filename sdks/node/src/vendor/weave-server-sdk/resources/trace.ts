// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import * as Shared from './shared';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Trace extends APIResource {
  /**
   * Compute per-call usage for a trace, with descendant rollup.
   */
  usage(body: TraceUsageParams, options?: RequestOptions): APIPromise<TraceUsageResponse> {
    return this._client.post('/trace/usage', { body, ...options });
  }
}

/**
 * Response with per-call usage metrics (each includes descendant contributions).
 */
export interface TraceUsageResponse {
  call_usage: { [key: string]: { [key: string]: TraceUsageResponse.LLMAggregatedUsage } };

  unfinished_call_ids: Array<string>;
}

export namespace TraceUsageResponse {
  /**
   * Aggregated usage metrics for a specific LLM.
   *
   * Constructor defaults stay for Python callers. Serialization JSON Schema marks
   * those fields required so OpenAPI matches the JSON FastAPI sends.
   */
  export interface LLMAggregatedUsage {
    cache_creation_input_tokens: number;

    cache_creation_input_tokens_total_cost: number | null;

    cache_read_input_tokens: number;

    cache_read_input_tokens_total_cost: number | null;

    completion_tokens: number;

    completion_tokens_total_cost: number | null;

    prompt_tokens: number;

    prompt_tokens_total_cost: number | null;

    requests: number;

    total_tokens: number;
  }
}

export interface TraceUsageParams {
  project_id: string;

  /**
   * Filter to select calls. Typically use trace_ids to get all calls in a trace.
   */
  filter?: TraceUsageParams.Filter | null;

  /**
   * If true, include cost calculations in the usage.
   */
  include_costs?: boolean;

  /**
   * Maximum number of calls to process. Acts as a safety limit to prevent unbounded
   * memory usage.
   */
  limit?: number;

  /**
   * Additional query conditions for filtering calls.
   */
  query?: TraceUsageParams.Query | null;
}

export namespace TraceUsageParams {
  /**
   * Filter to select calls. Typically use trace_ids to get all calls in a trace.
   */
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

  /**
   * Additional query conditions for filtering calls.
   */
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

export declare namespace Trace {
  export { type TraceUsageResponse as TraceUsageResponse, type TraceUsageParams as TraceUsageParams };
}
