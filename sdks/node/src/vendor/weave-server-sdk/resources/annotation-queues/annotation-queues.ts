// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as ItemsAPI from './items';
import {
  ItemAddParams,
  ItemAddResponse,
  ItemQueryParams,
  ItemQueryResponse,
  ItemUpdateProgressParams,
  ItemUpdateProgressResponse,
  Items,
} from './items';
import { APIPromise } from '../../core/api-promise';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';
import { JSONLDecoder } from '../../internal/decoders/jsonl';
import { path } from '../../internal/utils/path';

export class AnnotationQueues extends APIResource {
  items: ItemsAPI.Items = new ItemsAPI.Items(this._client);

  /**
   * Create a new annotation queue.
   *
   * @example
   * ```ts
   * const annotationQueue =
   *   await client.annotationQueues.create({
   *     name: 'Error Review Queue',
   *     project_id: 'entity/project',
   *     scorer_refs: [
   *       'weave:///entity/project/scorer/error_severity:abc123',
   *       'weave:///entity/project/scorer/resolution_quality:def456',
   *     ],
   *   });
   * ```
   */
  create(
    body: AnnotationQueueCreateParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueCreateResponse> {
    return this._client.post('/annotation_queues', { body, ...options });
  }

  /**
   * Update an annotation queue's metadata (name, description, scorer_refs).
   *
   * @example
   * ```ts
   * const annotationQueue =
   *   await client.annotationQueues.update('queue_id', {
   *     project_id: 'entity/project',
   *   });
   * ```
   */
  update(
    queueID: string,
    body: AnnotationQueueUpdateParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueUpdateResponse> {
    return this._client.put(path`/annotation_queues/${queueID}`, { body, ...options });
  }

  /**
   * Delete (soft-delete) an annotation queue.
   *
   * @example
   * ```ts
   * const annotationQueue =
   *   await client.annotationQueues.delete('queue_id', {
   *     project_id: 'project_id',
   *   });
   * ```
   */
  delete(
    queueID: string,
    params: AnnotationQueueDeleteParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueDeleteResponse> {
    const { project_id } = params;
    return this._client.delete(path`/annotation_queues/${queueID}`, { query: { project_id }, ...options });
  }

  /**
   * Query annotation queues for a project (streaming NDJSON response).
   *
   * @example
   * ```ts
   * const annotationQueueSchema =
   *   await client.annotationQueues.query({
   *     project_id: 'entity/project',
   *   });
   * ```
   */
  query(
    body: AnnotationQueueQueryParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<AnnotationQueueSchema>> {
    return this._client
      .post('/annotation_queues/query', {
        body,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<AnnotationQueueSchema>
    >;
  }

  /**
   * Read a specific annotation queue.
   *
   * @example
   * ```ts
   * const response = await client.annotationQueues.read(
   *   'queue_id',
   *   { project_id: 'project_id' },
   * );
   * ```
   */
  read(
    queueID: string,
    query: AnnotationQueueReadParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueReadResponse> {
    return this._client.get(path`/annotation_queues/${queueID}`, { query, ...options });
  }

  /**
   * Get stats for multiple annotation queues.
   *
   * @example
   * ```ts
   * const response = await client.annotationQueues.stats({
   *   project_id: 'entity/project',
   *   queue_ids: [
   *     '550e8400-e29b-41d4-a716-446655440000',
   *     '550e8400-e29b-41d4-a716-446655440001',
   *   ],
   * });
   * ```
   */
  stats(
    body: AnnotationQueueStatsParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueStatsResponse> {
    return this._client.post('/annotation_queues/stats', { body, ...options });
  }
}

/**
 * Schema for annotation queue responses.
 */
export interface AnnotationQueueSchema {
  id: string;

  created_at: string;

  created_by: string;

  description: string;

  name: string;

  project_id: string;

  scorer_refs: Array<string>;

  updated_at: string;

  deleted_at?: string | null;
}

/**
 * Response from creating an annotation queue.
 */
export interface AnnotationQueueCreateResponse {
  id: string;
}

/**
 * Response from updating an annotation queue.
 */
export interface AnnotationQueueUpdateResponse {
  /**
   * Schema for annotation queue responses.
   */
  queue: AnnotationQueueSchema;
}

/**
 * Response from deleting an annotation queue.
 */
export interface AnnotationQueueDeleteResponse {
  /**
   * Schema for annotation queue responses.
   */
  queue: AnnotationQueueSchema;
}

/**
 * Response from reading an annotation queue.
 */
export interface AnnotationQueueReadResponse {
  /**
   * Schema for annotation queue responses.
   */
  queue: AnnotationQueueSchema;
}

/**
 * Response with stats for multiple annotation queues.
 */
export interface AnnotationQueueStatsResponse {
  stats: Array<AnnotationQueueStatsResponse.Stat>;
}

export namespace AnnotationQueueStatsResponse {
  /**
   * Statistics for a single annotation queue.
   */
  export interface Stat {
    /**
     * Number of items completed or skipped by at least one annotator
     */
    completed_items: number;

    /**
     * The queue ID
     */
    queue_id: string;

    /**
     * Total number of items in the queue
     */
    total_items: number;
  }
}

export interface AnnotationQueueCreateParams {
  name: string;

  project_id: string;

  scorer_refs: Array<string>;

  description?: string;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface AnnotationQueueUpdateParams {
  project_id: string;

  description?: string | null;

  name?: string | null;

  scorer_refs?: Array<string> | null;
}

export interface AnnotationQueueDeleteParams {
  project_id: string;
}

export interface AnnotationQueueQueryParams {
  project_id: string;

  limit?: number | null;

  /**
   * Filter by queue name (case-insensitive partial match)
   */
  name?: string | null;

  offset?: number | null;

  /**
   * Sort by multiple fields (e.g., created_at, updated_at, name)
   */
  sort_by?: Array<AnnotationQueueQueryParams.SortBy> | null;
}

export namespace AnnotationQueueQueryParams {
  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export interface AnnotationQueueReadParams {
  project_id: string;
}

export interface AnnotationQueueStatsParams {
  project_id: string;

  /**
   * List of queue IDs to get stats for
   */
  queue_ids: Array<string>;
}

AnnotationQueues.Items = Items;

export declare namespace AnnotationQueues {
  export {
    type AnnotationQueueSchema as AnnotationQueueSchema,
    type AnnotationQueueCreateResponse as AnnotationQueueCreateResponse,
    type AnnotationQueueUpdateResponse as AnnotationQueueUpdateResponse,
    type AnnotationQueueDeleteResponse as AnnotationQueueDeleteResponse,
    type AnnotationQueueReadResponse as AnnotationQueueReadResponse,
    type AnnotationQueueStatsResponse as AnnotationQueueStatsResponse,
    type AnnotationQueueCreateParams as AnnotationQueueCreateParams,
    type AnnotationQueueUpdateParams as AnnotationQueueUpdateParams,
    type AnnotationQueueDeleteParams as AnnotationQueueDeleteParams,
    type AnnotationQueueQueryParams as AnnotationQueueQueryParams,
    type AnnotationQueueReadParams as AnnotationQueueReadParams,
    type AnnotationQueueStatsParams as AnnotationQueueStatsParams,
  };

  export {
    Items as Items,
    type ItemAddResponse as ItemAddResponse,
    type ItemQueryResponse as ItemQueryResponse,
    type ItemUpdateProgressResponse as ItemUpdateProgressResponse,
    type ItemAddParams as ItemAddParams,
    type ItemQueryParams as ItemQueryParams,
    type ItemUpdateProgressParams as ItemUpdateProgressParams,
  };
}
