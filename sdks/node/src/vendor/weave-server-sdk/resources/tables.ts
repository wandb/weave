// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Tables extends APIResource {
  /**
   * Table Create
   *
   * @example
   * ```ts
   * const table = await client.tables.create({
   *   table: {
   *     project_id: 'project_id',
   *     rows: [{ foo: 'bar' }],
   *   },
   * });
   * ```
   */
  create(body: TableCreateParams, options?: RequestOptions): APIPromise<TableCreateResponse> {
    return this._client.post('/table/create', { body, ...options });
  }

  /**
   * Table Update
   *
   * @example
   * ```ts
   * const table = await client.tables.update({
   *   base_digest: 'base_digest',
   *   project_id: 'project_id',
   *   updates: [{ append: { row: { foo: 'bar' } } }],
   * });
   * ```
   */
  update(body: TableUpdateParams, options?: RequestOptions): APIPromise<TableUpdateResponse> {
    return this._client.post('/table/update', { body, ...options });
  }

  /**
   * Table Create From Digests
   *
   * @example
   * ```ts
   * const response = await client.tables.createFromDigests({
   *   project_id: 'project_id',
   *   row_digests: ['string'],
   * });
   * ```
   */
  createFromDigests(
    body: TableCreateFromDigestsParams,
    options?: RequestOptions,
  ): APIPromise<TableCreateFromDigestsResponse> {
    return this._client.post('/table/create_from_digests', { body, ...options });
  }

  /**
   * Table Query
   *
   * @example
   * ```ts
   * const response = await client.tables.query({
   *   digest:
   *     'aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims',
   *   project_id: 'my_entity/my_project',
   * });
   * ```
   */
  query(body: TableQueryParams, options?: RequestOptions): APIPromise<TableQueryResponse> {
    return this._client.post('/table/query', { body, ...options });
  }

  /**
   * Table Query Stats
   *
   * @example
   * ```ts
   * const response = await client.tables.queryStats({
   *   digest: 'digest',
   *   project_id: 'my_entity/my_project',
   * });
   * ```
   */
  queryStats(body: TableQueryStatsParams, options?: RequestOptions): APIPromise<TableQueryStatsResponse> {
    return this._client.post('/table/query_stats', { body, ...options });
  }

  /**
   * Table Query Stats Batch
   *
   * @example
   * ```ts
   * const response = await client.tables.queryStatsBatch({
   *   project_id: 'my_entity/my_project',
   * });
   * ```
   */
  queryStatsBatch(
    body: TableQueryStatsBatchParams,
    options?: RequestOptions,
  ): APIPromise<TableQueryStatsBatchResponse> {
    return this._client.post('/table/query_stats_batch', { body, ...options });
  }
}

export interface TableCreateResponse {
  digest: string;

  /**
   * The digests of the rows that were created
   */
  row_digests?: Array<string>;
}

export interface TableUpdateResponse {
  digest: string;

  /**
   * The digests of the rows that were updated
   */
  updated_row_digests?: Array<string>;
}

export interface TableCreateFromDigestsResponse {
  digest: string;
}

export interface TableQueryResponse {
  rows: Array<TableQueryResponse.Row>;
}

export namespace TableQueryResponse {
  export interface Row {
    digest: string;

    val: unknown;

    original_index?: number | null;
  }
}

export interface TableQueryStatsResponse {
  count: number;
}

export interface TableQueryStatsBatchResponse {
  tables: Array<TableQueryStatsBatchResponse.Table>;
}

export namespace TableQueryStatsBatchResponse {
  export interface Table {
    count: number;

    digest: string;

    storage_size_bytes?: number | null;
  }
}

export interface TableCreateParams {
  table: TableCreateParams.Table;
}

export namespace TableCreateParams {
  export interface Table {
    project_id: string;

    rows: Array<{ [key: string]: unknown }>;

    /**
     * Client-computed table digest for server-side validation.
     */
    expected_digest?: string | null;
  }
}

export interface TableUpdateParams {
  base_digest: string;

  project_id: string;

  updates: Array<
    TableUpdateParams.TableAppendSpec | TableUpdateParams.TablePopSpec | TableUpdateParams.TableInsertSpec
  >;
}

export namespace TableUpdateParams {
  export interface TableAppendSpec {
    append: TableAppendSpec.Append;
  }

  export namespace TableAppendSpec {
    export interface Append {
      row: { [key: string]: unknown };
    }
  }

  export interface TablePopSpec {
    pop: TablePopSpec.Pop;
  }

  export namespace TablePopSpec {
    export interface Pop {
      index: number;
    }
  }

  export interface TableInsertSpec {
    insert: TableInsertSpec.Insert;
  }

  export namespace TableInsertSpec {
    export interface Insert {
      index: number;

      row: { [key: string]: unknown };
    }
  }
}

export interface TableCreateFromDigestsParams {
  project_id: string;

  row_digests: Array<string>;

  /**
   * Client-computed table digest for server-side validation.
   */
  expected_digest?: string | null;
}

export interface TableQueryParams {
  /**
   * The digest of the table to query
   */
  digest: string;

  /**
   * The ID of the project
   */
  project_id: string;

  /**
   * Optional filter to apply to the query. See `TableRowFilter` for more details.
   */
  filter?: TableQueryParams.Filter | null;

  /**
   * Maximum number of rows to return
   */
  limit?: number | null;

  /**
   * Number of rows to skip before starting to return rows
   */
  offset?: number | null;

  /**
   * List of fields to sort by. Fields can be dot-separated to access dictionary
   * values. No sorting uses the default table order (insertion order).
   */
  sort_by?: Array<TableQueryParams.SortBy> | null;
}

export namespace TableQueryParams {
  /**
   * Optional filter to apply to the query. See `TableRowFilter` for more details.
   */
  export interface Filter {
    /**
     * List of row digests to filter by
     */
    row_digests?: Array<string> | null;
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export interface TableQueryStatsParams {
  /**
   * The digest of the table to query
   */
  digest: string;

  /**
   * The ID of the project
   */
  project_id: string;
}

export interface TableQueryStatsBatchParams {
  /**
   * The ID of the project
   */
  project_id: string;

  /**
   * The digests of the tables to query
   */
  digests?: Array<string> | null;

  /**
   * If true, the `storage_size_bytes` column is returned.
   */
  include_storage_size?: boolean | null;
}

export declare namespace Tables {
  export {
    type TableCreateResponse as TableCreateResponse,
    type TableUpdateResponse as TableUpdateResponse,
    type TableCreateFromDigestsResponse as TableCreateFromDigestsResponse,
    type TableQueryResponse as TableQueryResponse,
    type TableQueryStatsResponse as TableQueryStatsResponse,
    type TableQueryStatsBatchResponse as TableQueryStatsBatchResponse,
    type TableCreateParams as TableCreateParams,
    type TableUpdateParams as TableUpdateParams,
    type TableCreateFromDigestsParams as TableCreateFromDigestsParams,
    type TableQueryParams as TableQueryParams,
    type TableQueryStatsParams as TableQueryStatsParams,
    type TableQueryStatsBatchParams as TableQueryStatsBatchParams,
  };
}
