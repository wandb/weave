// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';
import { path } from '../internal/utils/path';

export class V2Calls extends APIResource {
  /**
   * Upsert a batch of completed calls directly to the calls_complete table.
   *
   * Each call in the batch contains both start and end information. This endpoint is
   * used when calls are buffered client-side and sent as complete records.
   */
  complete(project: string, params: V2CallCompleteParams, options?: RequestOptions): APIPromise<unknown> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/calls/complete`, { body, ...options });
  }
}

/**
 * Response for upserting a batch of completed calls.
 */
export type V2CallCompleteResponse = unknown;

export interface V2CallCompleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param
   */
  batch: Array<V2CallCompleteParams.Batch>;
}

export namespace V2CallCompleteParams {
  /**
   * Schema for inserting a completed call directly.
   *
   * This represents a call that is already finished at insertion time, with both
   * start and end information provided together. Used by the calls_complete
   * endpoint.
   */
  export interface Batch {
    id: string;

    attributes: { [key: string]: unknown };

    ended_at: string;

    inputs: { [key: string]: unknown };

    op_name: string;

    project_id: string;

    started_at: string;

    summary: Batch.Summary;

    trace_id: string;

    display_name?: string | null;

    exception?: string | null;

    otel_dump?: { [key: string]: unknown } | null;

    output?: unknown;

    parent_id?: string | null;

    thread_id?: string | null;

    turn_id?: string | null;

    wb_run_id?: string | null;

    wb_run_step?: number | null;

    wb_run_step_end?: number | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }

  export namespace Batch {
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

export declare namespace V2Calls {
  export {
    type V2CallCompleteResponse as V2CallCompleteResponse,
    type V2CallCompleteParams as V2CallCompleteParams,
  };
}
