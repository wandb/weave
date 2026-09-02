// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';
import { path } from '../internal/utils/path';

export class V2Runtimes extends APIResource {
  /**
   * Create or replace a custom runtime configuration.
   */
  apply(
    runtimeName: string,
    params: V2RuntimeApplyParams,
    options?: RequestOptions,
  ): APIPromise<V2RuntimeApplyResponse> {
    const { entity, project, ...body } = params;
    return this._client.put(path`/v2/${entity}/${project}/runtimes/${runtimeName}`, { body, ...options });
  }
}

export interface V2RuntimeApplyResponse {
  api_key_secret: string | null;

  base_url: string;

  headers: { [key: string]: string };

  /**
   * Stable custom runtime name
   */
  name: string;

  runtime_ids: Array<V2RuntimeApplyResponse.RuntimeID>;
}

export namespace V2RuntimeApplyResponse {
  export interface RuntimeID {
    /**
     * Value sent in the OpenAI-compatible request model field
     */
    id: string;

    playground_id: string;

    /**
     * Maximum tokens supported by this runtime ID
     */
    max_tokens?: number;
  }
}

export interface V2RuntimeApplyParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Body param: Public OpenAI-compatible endpoint base URL
   */
  base_url: string;

  /**
   * Body param: Complete desired list of IDs exposed by the endpoint
   */
  runtime_ids: Array<V2RuntimeApplyParams.RuntimeID>;

  /**
   * Body param: Team secret name used as the endpoint API key; never the secret
   * value
   */
  api_key_secret?: string | null;

  /**
   * Body param: Literal headers forwarded to the endpoint
   */
  headers?: { [key: string]: string };
}

export namespace V2RuntimeApplyParams {
  export interface RuntimeID {
    /**
     * Value sent in the OpenAI-compatible request model field
     */
    id: string;

    /**
     * Maximum tokens supported by this runtime ID
     */
    max_tokens?: number;
  }
}

export declare namespace V2Runtimes {
  export {
    type V2RuntimeApplyResponse as V2RuntimeApplyResponse,
    type V2RuntimeApplyParams as V2RuntimeApplyParams,
  };
}
