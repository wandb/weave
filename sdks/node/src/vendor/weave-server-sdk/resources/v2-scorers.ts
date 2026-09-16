// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Scorers extends APIResource {
  /**
   * Create a scorer object.
   */
  create(
    project: string,
    params: V2ScorerCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2ScorerCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/scorers`, { body, ...options });
  }

  /**
   * List scorer objects.
   */
  list(
    project: string,
    params: V2ScorerListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2ScorerListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/scorers`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2ScorerListResponse>
    >;
  }

  /**
   * Delete a scorer object.
   */
  delete(
    objectID: string,
    params: V2ScorerDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2ScorerDeleteResponse> {
    const { entity, project, digests } = params;
    return this._client.delete(path`/v2/${entity}/${project}/scorers/${objectID}`, {
      query: { digests },
      ...options,
    });
  }

  /**
   * Get a scorer object.
   */
  read(
    digest: string,
    params: V2ScorerReadParams,
    options?: RequestOptions,
  ): APIPromise<V2ScorerReadResponse> {
    const { entity, project, object_id } = params;
    return this._client.get(path`/v2/${entity}/${project}/scorers/${object_id}/versions/${digest}`, options);
  }
}

export interface V2ScorerCreateResponse {
  /**
   * The digest of the created scorer
   */
  digest: string;

  /**
   * The ID of the created scorer
   */
  object_id: string;

  /**
   * Full reference to the created scorer
   */
  scorer: string;

  /**
   * The version index of the created scorer
   */
  version_index: number;
}

export interface V2ScorerListResponse {
  /**
   * When the scorer was created
   */
  created_at: string;

  /**
   * The digest of the scorer
   */
  digest: string;

  /**
   * The name of the scorer
   */
  name: string;

  /**
   * The scorer ID
   */
  object_id: string;

  /**
   * The Scorer.score op reference
   */
  score_op: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Description of the scorer
   */
  description?: string | null;
}

export interface V2ScorerDeleteResponse {
  /**
   * Number of scorer versions deleted
   */
  num_deleted: number;
}

export interface V2ScorerReadResponse {
  /**
   * When the scorer was created
   */
  created_at: string;

  /**
   * The digest of the scorer
   */
  digest: string;

  /**
   * The name of the scorer
   */
  name: string;

  /**
   * The scorer ID
   */
  object_id: string;

  /**
   * The Scorer.score op reference
   */
  score_op: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Description of the scorer
   */
  description?: string | null;
}

export interface V2ScorerCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: The name of this scorer. Scorers with the same name will be
   * versioned together.
   */
  name: string;

  /**
   * Body param: Complete source code for the Scorer.score op including imports
   */
  op_source_code: string;

  /**
   * Body param: A description of this scorer
   */
  description?: string | null;
}

export interface V2ScorerListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Maximum number of scorers to return
   */
  limit?: number | null;

  /**
   * Query param: Number of scorers to skip
   */
  offset?: number | null;
}

export interface V2ScorerDeleteParams {
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
   * scorer will be deleted.
   */
  digests?: Array<string> | null;
}

export interface V2ScorerReadParams {
  entity: string;

  project: string;

  object_id: string;
}

export declare namespace V2Scorers {
  export {
    type V2ScorerCreateResponse as V2ScorerCreateResponse,
    type V2ScorerListResponse as V2ScorerListResponse,
    type V2ScorerDeleteResponse as V2ScorerDeleteResponse,
    type V2ScorerReadResponse as V2ScorerReadResponse,
    type V2ScorerCreateParams as V2ScorerCreateParams,
    type V2ScorerListParams as V2ScorerListParams,
    type V2ScorerDeleteParams as V2ScorerDeleteParams,
    type V2ScorerReadParams as V2ScorerReadParams,
  };
}
