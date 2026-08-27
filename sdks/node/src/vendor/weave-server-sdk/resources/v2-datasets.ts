// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Datasets extends APIResource {
  /**
   * Create a dataset object.
   */
  create(
    project: string,
    params: V2DatasetCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2DatasetCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/datasets`, { body, ...options });
  }

  /**
   * List dataset objects.
   */
  list(
    project: string,
    params: V2DatasetListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2DatasetListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/datasets`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2DatasetListResponse>
    >;
  }

  /**
   * Delete a dataset object. If digests are provided, only those versions are
   * deleted. Otherwise, all versions are deleted.
   */
  delete(
    objectID: string,
    params: V2DatasetDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2DatasetDeleteResponse> {
    const { entity, project, digests } = params;
    return this._client.delete(path`/v2/${entity}/${project}/datasets/${objectID}`, {
      query: { digests },
      ...options,
    });
  }

  /**
   * Get a dataset object.
   */
  read(
    digest: string,
    params: V2DatasetReadParams,
    options?: RequestOptions,
  ): APIPromise<V2DatasetReadResponse> {
    const { entity, project, object_id } = params;
    return this._client.get(path`/v2/${entity}/${project}/datasets/${object_id}/versions/${digest}`, options);
  }
}

export interface V2DatasetCreateResponse {
  /**
   * The digest of the created dataset
   */
  digest: string;

  /**
   * The ID of the created dataset
   */
  object_id: string;

  /**
   * The version index of the created dataset
   */
  version_index: number;
}

export interface V2DatasetListResponse {
  /**
   * When the object was created
   */
  created_at: string;

  /**
   * The digest of the dataset object
   */
  digest: string;

  /**
   * The name of the dataset
   */
  name: string;

  /**
   * The dataset ID
   */
  object_id: string;

  /**
   * Reference to the dataset rows data
   */
  rows: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Description of the dataset
   */
  description?: string | null;
}

export interface V2DatasetDeleteResponse {
  /**
   * Number of dataset versions deleted
   */
  num_deleted: number;
}

export interface V2DatasetReadResponse {
  /**
   * When the object was created
   */
  created_at: string;

  /**
   * The digest of the dataset object
   */
  digest: string;

  /**
   * The name of the dataset
   */
  name: string;

  /**
   * The dataset ID
   */
  object_id: string;

  /**
   * Reference to the dataset rows data
   */
  rows: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Description of the dataset
   */
  description?: string | null;
}

export interface V2DatasetCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: Dataset rows
   */
  rows: Array<{ [key: string]: unknown }>;

  /**
   * Body param: A description of this dataset
   */
  description?: string | null;

  /**
   * Body param: The name of this dataset. Datasets with the same name will be
   * versioned together.
   */
  name?: string | null;
}

export interface V2DatasetListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Maximum number of datasets to return
   */
  limit?: number | null;

  /**
   * Query param: Number of datasets to skip
   */
  offset?: number | null;
}

export interface V2DatasetDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Query param: List of digests to delete. If not provided, all digests for the
   * dataset will be deleted.
   */
  digests?: Array<string> | null;
}

export interface V2DatasetReadParams {
  entity: string;

  project: string;

  object_id: string;
}

export declare namespace V2Datasets {
  export {
    type V2DatasetCreateResponse as V2DatasetCreateResponse,
    type V2DatasetListResponse as V2DatasetListResponse,
    type V2DatasetDeleteResponse as V2DatasetDeleteResponse,
    type V2DatasetReadResponse as V2DatasetReadResponse,
    type V2DatasetCreateParams as V2DatasetCreateParams,
    type V2DatasetListParams as V2DatasetListParams,
    type V2DatasetDeleteParams as V2DatasetDeleteParams,
    type V2DatasetReadParams as V2DatasetReadParams,
  };
}
