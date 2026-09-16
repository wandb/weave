// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';

export class Threads extends APIResource {
  /**
   * Threads Query Stream
   *
   * @example
   * ```ts
   * const response = await client.threads.streamQuery({
   *   project_id: 'my_entity/my_project',
   * });
   * ```
   */
  streamQuery(
    body: ThreadStreamQueryParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<ThreadStreamQueryResponse>> {
    return this._client
      .post('/threads/stream_query', {
        body,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<ThreadStreamQueryResponse>
    >;
  }
}

export interface ThreadStreamQueryResponse {
  /**
   * Turn ID of the first turn in this thread (earliest start_time)
   */
  first_turn_id: string | null;

  /**
   * Turn ID of the latest turn in this thread (latest end_time)
   */
  last_turn_id: string | null;

  /**
   * Latest end time of turn calls in this thread
   */
  last_updated: string;

  /**
   * 50th percentile (median) of turn durations in milliseconds within this thread
   */
  p50_turn_duration_ms: number | null;

  /**
   * 99th percentile of turn durations in milliseconds within this thread
   */
  p99_turn_duration_ms: number | null;

  /**
   * Earliest start time of turn calls in this thread
   */
  start_time: string;

  thread_id: string;

  /**
   * Number of turn calls in this thread
   */
  turn_count: number;
}

export interface ThreadStreamQueryParams {
  /**
   * The ID of the project
   */
  project_id: string;

  /**
   * Filter criteria for the threads query
   */
  filter?: ThreadStreamQueryParams.Filter | null;

  /**
   * Maximum number of threads to return
   */
  limit?: number | null;

  /**
   * Number of threads to skip
   */
  offset?: number | null;

  /**
   * Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count',
   * 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.
   */
  sort_by?: Array<ThreadStreamQueryParams.SortBy> | null;
}

export namespace ThreadStreamQueryParams {
  /**
   * Filter criteria for the threads query
   */
  export interface Filter {
    /**
     * Only include threads with start_time after this timestamp
     */
    after_datetime?: string | null;

    /**
     * Only include threads with last_updated before this timestamp
     */
    before_datetime?: string | null;

    /**
     * Only include threads with thread_ids in this list
     */
    thread_ids?: Array<string> | null;
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export declare namespace Threads {
  export {
    type ThreadStreamQueryResponse as ThreadStreamQueryResponse,
    type ThreadStreamQueryParams as ThreadStreamQueryParams,
  };
}
