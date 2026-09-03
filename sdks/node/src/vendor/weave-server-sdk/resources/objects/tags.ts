// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Tags extends APIResource {
  /**
   * List all tags in a project.
   *
   * @example
   * ```ts
   * const tags = await client.objects.tags.list({
   *   project_id: 'project_id',
   * });
   * ```
   */
  list(query: TagListParams, options?: RequestOptions): APIPromise<TagListResponse> {
    return this._client.get('/tags', { query, ...options });
  }

  /**
   * Add tags to an object version.
   *
   * @example
   * ```ts
   * const response = await client.objects.tags.add('digest', {
   *   object_id: 'object_id',
   *   project_id: 'entity/project',
   *   tags: ['production', 'reviewed'],
   * });
   * ```
   */
  add(digest: string, params: TagAddParams, options?: RequestOptions): APIPromise<unknown> {
    const { object_id, ...body } = params;
    return this._client.put(path`/objs/${object_id}/versions/${digest}/tags`, { body, ...options });
  }

  /**
   * Remove tags from an object version.
   *
   * @example
   * ```ts
   * const tag = await client.objects.tags.remove('digest', {
   *   object_id: 'object_id',
   *   project_id: 'entity/project',
   *   tags: ['production', 'reviewed'],
   * });
   * ```
   */
  remove(digest: string, params: TagRemoveParams, options?: RequestOptions): APIPromise<unknown> {
    const { object_id, ...body } = params;
    return this._client.post(path`/objs/${object_id}/versions/${digest}/tags/remove`, { body, ...options });
  }
}

export interface TagListResponse {
  tags: Array<string>;
}

export type TagAddResponse = unknown;

export type TagRemoveResponse = unknown;

export interface TagListParams {
  project_id: string;
}

export interface TagAddParams {
  /**
   * Path param
   */
  object_id: string;

  /**
   * Body param
   */
  project_id: string;

  /**
   * Body param
   */
  tags: Array<string>;
}

export interface TagRemoveParams {
  /**
   * Path param
   */
  object_id: string;

  /**
   * Body param
   */
  project_id: string;

  /**
   * Body param
   */
  tags: Array<string>;
}

export declare namespace Tags {
  export {
    type TagListResponse as TagListResponse,
    type TagAddResponse as TagAddResponse,
    type TagRemoveResponse as TagRemoveResponse,
    type TagListParams as TagListParams,
    type TagAddParams as TagAddParams,
    type TagRemoveParams as TagRemoveParams,
  };
}
