// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class DatasetSources extends APIResource {
  /**
   * Link source calls/spans to dataset rows (batch, idempotent).
   *
   * @example
   * ```ts
   * const response = await client.datasetSources.link({
   *   dataset_digest: 'dataset_digest',
   *   dataset_object_id: 'dataset_object_id',
   *   links: [
   *     {
   *       row_digest: 'row_digest',
   *       sources: [
   *         {
   *           source_id: 'source_id',
   *           source_kind: 'call',
   *           source_trace_id: 'source_trace_id',
   *         },
   *       ],
   *     },
   *   ],
   *   project_id: 'entity/project',
   * });
   * ```
   */
  link(body: DatasetSourceLinkParams, options?: RequestOptions): APIPromise<DatasetSourceLinkResponse> {
    return this._client.post('/dataset_sources/link', { body, ...options });
  }

  /**
   * Forward provenance lookup: dataset (+ optional row digests) -> sources.
   *
   * @example
   * ```ts
   * const response = await client.datasetSources.query({
   *   dataset_object_id: 'dataset_object_id',
   *   project_id: 'entity/project',
   * });
   * ```
   */
  query(body: DatasetSourceQueryParams, options?: RequestOptions): APIPromise<DatasetSourceQueryResponse> {
    return this._client.post('/dataset_sources/query', { body, ...options });
  }

  /**
   * Reverse provenance lookup: sources -> datasets they appear in.
   *
   * @example
   * ```ts
   * const response =
   *   await client.datasetSources.sourceDatasetsQuery({
   *     project_id: 'entity/project',
   *     sources: [
   *       {
   *         source_id: 'source_id',
   *         source_kind: 'call',
   *         source_trace_id: 'source_trace_id',
   *       },
   *     ],
   *   });
   * ```
   */
  sourceDatasetsQuery(
    body: DatasetSourceSourceDatasetsQueryParams,
    options?: RequestOptions,
  ): APIPromise<DatasetSourceSourceDatasetsQueryResponse> {
    return this._client.post('/dataset_sources/source_datasets_query', { body, ...options });
  }
}

/**
 * Response from linking dataset rows to sources.
 *
 * One entry per flattened (row_digest, source) tuple, in input order.
 */
export interface DatasetSourceLinkResponse {
  entries: Array<DatasetSourceLinkResponse.Entry>;
}

export namespace DatasetSourceLinkResponse {
  /**
   * Result for a single flattened (row_digest, source) link.
   */
  export interface Entry {
    link_id: string;

    created?: boolean | null;
  }
}

/**
 * Response from the forward dataset -> sources query.
 */
export interface DatasetSourceQueryResponse {
  links: Array<DatasetSourceQueryResponse.Link>;
}

export namespace DatasetSourceQueryResponse {
  /**
   * Schema for a single dataset source link row.
   */
  export interface Link {
    id: string;

    created_at: string;

    row_digest: string;

    source_display_name: string;

    source_id: string;

    source_kind: 'call' | 'span' | 'conversation';

    source_started_at: string;

    source_trace_id: string;

    updated_at: string;

    added_by?: string | null;

    deleted_at?: string | null;

    link_metadata?: { [key: string]: unknown } | null;
  }
}

/**
 * Response from the reverse sources -> datasets query.
 */
export interface DatasetSourceSourceDatasetsQueryResponse {
  memberships: Array<DatasetSourceSourceDatasetsQueryResponse.Membership>;
}

export namespace DatasetSourceSourceDatasetsQueryResponse {
  /**
   * Membership of a single (source, dataset) pair in the reverse query.
   */
  export interface Membership {
    dataset_object_id: string;

    first_seen_at: string;

    row_digests: Array<string>;

    row_digests_total_count: number;

    row_digests_truncated: boolean;

    source_id: string;

    source_kind: 'call' | 'span' | 'conversation';

    source_trace_id: string;
  }
}

export interface DatasetSourceLinkParams {
  dataset_digest: string;

  dataset_object_id: string;

  links: Array<DatasetSourceLinkParams.Link>;

  project_id: string;

  include_created_status?: boolean;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export namespace DatasetSourceLinkParams {
  /**
   * A single dataset row and the sources to link to it.
   */
  export interface Link {
    row_digest: string;

    sources: Array<Link.Source>;

    link_metadata?: { [key: string]: unknown } | null;
  }

  export namespace Link {
    /**
     * Reference to a provenance source (a call, an agent span, or a conversation).
     */
    export interface Source {
      source_id: string;

      source_kind: 'call' | 'span' | 'conversation';

      source_trace_id: string;
    }
  }
}

export interface DatasetSourceQueryParams {
  dataset_object_id: string;

  project_id: string;

  include_deleted?: boolean;

  limit?: number | null;

  offset?: number | null;

  row_digests?: Array<string> | null;

  source_kinds?: Array<'call' | 'span' | 'conversation'> | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface DatasetSourceSourceDatasetsQueryParams {
  project_id: string;

  sources: Array<DatasetSourceSourceDatasetsQueryParams.Source>;

  include_deleted?: boolean;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export namespace DatasetSourceSourceDatasetsQueryParams {
  /**
   * Reference to a provenance source (a call, an agent span, or a conversation).
   */
  export interface Source {
    source_id: string;

    source_kind: 'call' | 'span' | 'conversation';

    source_trace_id: string;
  }
}

export declare namespace DatasetSources {
  export {
    type DatasetSourceLinkResponse as DatasetSourceLinkResponse,
    type DatasetSourceQueryResponse as DatasetSourceQueryResponse,
    type DatasetSourceSourceDatasetsQueryResponse as DatasetSourceSourceDatasetsQueryResponse,
    type DatasetSourceLinkParams as DatasetSourceLinkParams,
    type DatasetSourceQueryParams as DatasetSourceQueryParams,
    type DatasetSourceSourceDatasetsQueryParams as DatasetSourceSourceDatasetsQueryParams,
  };
}
