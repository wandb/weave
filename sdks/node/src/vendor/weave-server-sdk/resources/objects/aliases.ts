// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Aliases extends APIResource {
  /**
   * List all aliases in a project.
   *
   * @example
   * ```ts
   * const aliases = await client.objects.aliases.list({
   *   project_id: 'project_id',
   * });
   * ```
   */
  list(query: AliasListParams, options?: RequestOptions): APIPromise<AliasListResponse> {
    return this._client.get('/aliases', { query, ...options });
  }

  /**
   * Remove aliases from an object.
   *
   * @example
   * ```ts
   * const alias = await client.objects.aliases.remove(
   *   'object_id',
   *   { aliases: ['staging'], project_id: 'entity/project' },
   * );
   * ```
   */
  remove(objectID: string, body: AliasRemoveParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post(path`/objs/${objectID}/aliases/remove`, { body, ...options });
  }

  /**
   * Set aliases for an object version.
   *
   * @example
   * ```ts
   * const response = await client.objects.aliases.set(
   *   'object_id',
   *   {
   *     aliases: ['staging', 'v1-candidate'],
   *     digest: 'abc123def',
   *     project_id: 'entity/project',
   *   },
   * );
   * ```
   */
  set(objectID: string, body: AliasSetParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.put(path`/objs/${objectID}/aliases`, { body, ...options });
  }
}

export interface AliasListResponse {
  aliases: Array<string>;
}

export type AliasRemoveResponse = unknown;

export type AliasSetResponse = unknown;

export interface AliasListParams {
  project_id: string;
}

export interface AliasRemoveParams {
  aliases: Array<string>;

  project_id: string;
}

export interface AliasSetParams {
  aliases: Array<string>;

  digest: string;

  project_id: string;
}

export declare namespace Aliases {
  export {
    type AliasListResponse as AliasListResponse,
    type AliasRemoveResponse as AliasRemoveResponse,
    type AliasSetResponse as AliasSetResponse,
    type AliasListParams as AliasListParams,
    type AliasRemoveParams as AliasRemoveParams,
    type AliasSetParams as AliasSetParams,
  };
}
