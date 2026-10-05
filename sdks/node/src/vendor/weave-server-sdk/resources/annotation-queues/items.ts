// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Items extends APIResource {
  /**
   * Add calls to an annotation queue.
   *
   * @example
   * ```ts
   * const response = await client.annotationQueues.items.add(
   *   'queue_id',
   *   {
   *     call_ids: ['call-1', 'call-2', 'call-3'],
   *     display_fields: ['input.prompt', 'output.text'],
   *     project_id: 'entity/project',
   *   },
   * );
   * ```
   */
  add(queueID: string, body: ItemAddParams, options?: RequestOptions): APIPromise<ItemAddResponse> {
    return this._client.post(path`/annotation_queues/${queueID}/items`, { body, ...options });
  }

  /**
   * Query items in an annotation queue with pagination and sorting.
   *
   * @example
   * ```ts
   * const response = await client.annotationQueues.items.query(
   *   'queue_id',
   *   { project_id: 'entity/project' },
   * );
   * ```
   */
  query(queueID: string, body: ItemQueryParams, options?: RequestOptions): APIPromise<ItemQueryResponse> {
    return this._client.post(path`/annotation_queues/${queueID}/items/query`, { body, ...options });
  }

  /**
   * Update the annotation state of a queue item for the current annotator.
   *
   * @example
   * ```ts
   * const response =
   *   await client.annotationQueues.items.updateProgress(
   *     'item_id',
   *     {
   *       queue_id: 'queue_id',
   *       annotation_state: 'in_progress',
   *       project_id: 'entity/project',
   *     },
   *   );
   * ```
   */
  updateProgress(
    itemID: string,
    params: ItemUpdateProgressParams,
    options?: RequestOptions,
  ): APIPromise<ItemUpdateProgressResponse> {
    const { queue_id, ...body } = params;
    return this._client.post(path`/annotation_queues/${queue_id}/items/${itemID}/progress`, {
      body,
      ...options,
    });
  }
}

/**
 * Response from adding calls to a queue.
 */
export interface ItemAddResponse {
  added_count: number;

  duplicates: number;
}

/**
 * Response from querying annotation queue items.
 */
export interface ItemQueryResponse {
  items: Array<ItemQueryResponse.Item>;
}

export namespace ItemQueryResponse {
  /**
   * Schema for annotation queue item responses.
   */
  export interface Item {
    id: string;

    annotation_state: 'unstarted' | 'in_progress' | 'completed' | 'skipped';

    call_id: string;

    call_op_name: string;

    call_started_at: string;

    call_trace_id: string;

    created_at: string;

    created_by: string;

    display_fields: Array<string>;

    project_id: string;

    queue_id: string;

    updated_at: string;

    added_by?: string | null;

    annotator_user_id?: string | null;

    call_ended_at?: string | null;

    deleted_at?: string | null;

    position_in_queue?: number | null;
  }
}

/**
 * Response from updating annotation state.
 */
export interface ItemUpdateProgressResponse {
  /**
   * Schema for annotation queue item responses.
   */
  item: ItemUpdateProgressResponse.Item;
}

export namespace ItemUpdateProgressResponse {
  /**
   * Schema for annotation queue item responses.
   */
  export interface Item {
    id: string;

    annotation_state: 'unstarted' | 'in_progress' | 'completed' | 'skipped';

    call_id: string;

    call_op_name: string;

    call_started_at: string;

    call_trace_id: string;

    created_at: string;

    created_by: string;

    display_fields: Array<string>;

    project_id: string;

    queue_id: string;

    updated_at: string;

    added_by?: string | null;

    annotator_user_id?: string | null;

    call_ended_at?: string | null;

    deleted_at?: string | null;

    position_in_queue?: number | null;
  }
}

export interface ItemAddParams {
  call_ids: Array<string>;

  /**
   * JSON paths to display to annotators
   */
  display_fields: Array<string>;

  project_id: string;
}

export interface ItemQueryParams {
  project_id: string;

  /**
   * Simple filter for annotation queue items.
   *
   * Supports equality filtering on call metadata fields and IN filtering on
   * annotation state.
   */
  filter?: ItemQueryParams.Filter | null;

  /**
   * Include position_in_queue field (1-based index in full queue)
   */
  include_position?: boolean;

  limit?: number | null;

  offset?: number | null;

  /**
   * Sort by multiple fields (e.g., created_at, updated_at)
   */
  sort_by?: Array<ItemQueryParams.SortBy> | null;
}

export namespace ItemQueryParams {
  /**
   * Simple filter for annotation queue items.
   *
   * Supports equality filtering on call metadata fields and IN filtering on
   * annotation state.
   */
  export interface Filter {
    /**
     * Filter by exact queue item ID
     */
    id?: string | null;

    /**
     * Filter by W&B user ID who added the call
     */
    added_by?: string | null;

    /**
     * Filter by annotation states (unstarted, in_progress, completed, skipped)
     */
    annotation_states?: Array<'unstarted' | 'in_progress' | 'completed' | 'skipped'> | null;

    /**
     * Filter by exact call ID
     */
    call_id?: string | null;

    /**
     * Filter by exact operation name
     */
    call_op_name?: string | null;

    /**
     * Filter by exact trace ID
     */
    call_trace_id?: string | null;
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export interface ItemUpdateProgressParams {
  /**
   * Path param
   */
  queue_id: string;

  /**
   * Body param: New state: 'in_progress', 'completed', or 'skipped'
   */
  annotation_state: string;

  /**
   * Body param
   */
  project_id: string;
}

export declare namespace Items {
  export {
    type ItemAddResponse as ItemAddResponse,
    type ItemQueryResponse as ItemQueryResponse,
    type ItemUpdateProgressResponse as ItemUpdateProgressResponse,
    type ItemAddParams as ItemAddParams,
    type ItemQueryParams as ItemQueryParams,
    type ItemUpdateProgressParams as ItemUpdateProgressParams,
  };
}
