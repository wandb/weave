// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Ops extends APIResource {
  /**
   * Create an op object.
   */
  create(
    project: string,
    params: V2OpCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2OpCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/ops`, { body, ...options });
  }

  /**
   * List op objects.
   */
  list(
    project: string,
    params: V2OpListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2OpListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/ops`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2OpListResponse>
    >;
  }

  /**
   * Delete an op object. If digests are provided, only those versions are deleted.
   * Otherwise, all versions are deleted.
   */
  delete(
    objectID: string,
    params: V2OpDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2OpDeleteResponse> {
    const { entity, project, digests } = params;
    return this._client.delete(path`/v2/${entity}/${project}/ops/${objectID}`, {
      query: { digests },
      ...options,
    });
  }

  /**
   * Get an op object.
   */
  read(digest: string, params: V2OpReadParams, options?: RequestOptions): APIPromise<V2OpReadResponse> {
    const { entity, project, object_id, ...query } = params;
    return this._client.get(path`/v2/${entity}/${project}/ops/${object_id}/versions/${digest}`, {
      query,
      ...options,
    });
  }
}

/**
 * Response model for creating an Op object.
 */
export interface V2OpCreateResponse {
  /**
   * The digest of the created op
   */
  digest: string;

  /**
   * The ID of the created op
   */
  object_id: string;

  /**
   * The version index of the created op
   */
  version_index: number;
}

/**
 * Response model for reading an Op object.
 *
 * The code field contains the actual source code of the op.
 */
export interface V2OpListResponse {
  /**
   * The actual op source code
   */
  code: string;

  /**
   * When this op was created
   */
  created_at: string;

  /**
   * The digest of the op
   */
  digest: string;

  /**
   * The op ID
   */
  object_id: string;

  /**
   * The version index of this op
   */
  version_index: number;
}

export interface V2OpDeleteResponse {
  /**
   * Number of op versions deleted from this op
   */
  num_deleted: number;
}

/**
 * Response model for reading an Op object.
 *
 * The code field contains the actual source code of the op.
 */
export interface V2OpReadResponse {
  /**
   * The actual op source code
   */
  code: string;

  /**
   * When this op was created
   */
  created_at: string;

  /**
   * The digest of the op
   */
  digest: string;

  /**
   * The op ID
   */
  object_id: string;

  /**
   * The version index of this op
   */
  version_index: number;
}

export interface V2OpCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: The name of this op. Ops with the same name will be versioned
   * together.
   */
  name?: string | null;

  /**
   * Body param: Complete source code for this op, including imports
   */
  source_code?: string | null;
}

export interface V2OpListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Maximum number of ops to return
   */
  limit?: number | null;

  /**
   * Query param: Number of ops to skip
   */
  offset?: number | null;
}

export interface V2OpDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Query param: List of digests to delete. If not provided, all digests for the op
   * will be deleted.
   */
  digests?: Array<string> | null;
}

export interface V2OpReadParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Path param
   */
  object_id: string;

  /**
   * Query param: Whether to eagerly load the op code
   */
  eager?: boolean;
}

export declare namespace V2Ops {
  export {
    type V2OpCreateResponse as V2OpCreateResponse,
    type V2OpListResponse as V2OpListResponse,
    type V2OpDeleteResponse as V2OpDeleteResponse,
    type V2OpReadResponse as V2OpReadResponse,
    type V2OpCreateParams as V2OpCreateParams,
    type V2OpListParams as V2OpListParams,
    type V2OpDeleteParams as V2OpDeleteParams,
    type V2OpReadParams as V2OpReadParams,
  };
}
