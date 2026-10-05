// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Models extends APIResource {
  /**
   * Create a model object.
   */
  create(
    project: string,
    params: V2ModelCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2ModelCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/models`, { body, ...options });
  }

  /**
   * List model objects.
   */
  list(
    project: string,
    params: V2ModelListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2ModelListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/models`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2ModelListResponse>
    >;
  }

  /**
   * Delete a model object. If digests are provided, only those versions are deleted.
   * Otherwise, all versions are deleted.
   */
  delete(
    objectID: string,
    params: V2ModelDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2ModelDeleteResponse> {
    const { entity, project, digests } = params;
    return this._client.delete(path`/v2/${entity}/${project}/models/${objectID}`, {
      query: { digests },
      ...options,
    });
  }

  /**
   * Get a model object.
   */
  read(digest: string, params: V2ModelReadParams, options?: RequestOptions): APIPromise<V2ModelReadResponse> {
    const { entity, project, object_id } = params;
    return this._client.get(path`/v2/${entity}/${project}/models/${object_id}/versions/${digest}`, options);
  }
}

export interface V2ModelCreateResponse {
  /**
   * The digest of the created model
   */
  digest: string;

  /**
   * Full reference to the created model
   */
  model_ref: string;

  /**
   * The ID of the created model
   */
  object_id: string;

  /**
   * The version index of the created model
   */
  version_index: number;
}

export interface V2ModelListResponse {
  /**
   * When the model was created
   */
  created_at: string;

  /**
   * The digest of the model
   */
  digest: string;

  /**
   * The name of the model
   */
  name: string;

  /**
   * The model ID
   */
  object_id: string;

  /**
   * The source code of the model
   */
  source_code: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Additional attributes stored with the model
   */
  attributes?: { [key: string]: unknown } | null;

  /**
   * Description of the model
   */
  description?: string | null;
}

export interface V2ModelDeleteResponse {
  /**
   * Number of model versions deleted
   */
  num_deleted: number;
}

export interface V2ModelReadResponse {
  /**
   * When the model was created
   */
  created_at: string;

  /**
   * The digest of the model
   */
  digest: string;

  /**
   * The name of the model
   */
  name: string;

  /**
   * The model ID
   */
  object_id: string;

  /**
   * The source code of the model
   */
  source_code: string;

  /**
   * The version index of the object
   */
  version_index: number;

  /**
   * Additional attributes stored with the model
   */
  attributes?: { [key: string]: unknown } | null;

  /**
   * Description of the model
   */
  description?: string | null;
}

export interface V2ModelCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: The name of this model. Models with the same name will be versioned
   * together.
   */
  name: string;

  /**
   * Body param: Complete source code for the Model class including imports
   */
  source_code: string;

  /**
   * Body param: Additional attributes to be stored with the model
   */
  attributes?: { [key: string]: unknown } | null;

  /**
   * Body param: A description of this model
   */
  description?: string | null;
}

export interface V2ModelListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Maximum number of models to return
   */
  limit?: number | null;

  /**
   * Query param: Number of models to skip
   */
  offset?: number | null;
}

export interface V2ModelDeleteParams {
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
   * model will be deleted.
   */
  digests?: Array<string> | null;
}

export interface V2ModelReadParams {
  entity: string;

  project: string;

  object_id: string;
}

export declare namespace V2Models {
  export {
    type V2ModelCreateResponse as V2ModelCreateResponse,
    type V2ModelListResponse as V2ModelListResponse,
    type V2ModelDeleteResponse as V2ModelDeleteResponse,
    type V2ModelReadResponse as V2ModelReadResponse,
    type V2ModelCreateParams as V2ModelCreateParams,
    type V2ModelListParams as V2ModelListParams,
    type V2ModelDeleteParams as V2ModelDeleteParams,
    type V2ModelReadParams as V2ModelReadParams,
  };
}
