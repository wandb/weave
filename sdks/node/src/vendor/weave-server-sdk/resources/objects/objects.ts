// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as AliasesAPI from './aliases';
import {
  AliasListParams,
  AliasListResponse,
  AliasRemoveParams,
  AliasRemoveResponse,
  AliasSetParams,
  AliasSetResponse,
  Aliases,
} from './aliases';
import * as TagsAPI from './tags';
import {
  TagAddParams,
  TagAddResponse,
  TagListParams,
  TagListResponse,
  TagRemoveParams,
  TagRemoveResponse,
  Tags,
} from './tags';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Objects extends APIResource {
  tags: TagsAPI.Tags = new TagsAPI.Tags(this._client);
  aliases: AliasesAPI.Aliases = new AliasesAPI.Aliases(this._client);

  /**
   * Obj Create
   *
   * @example
   * ```ts
   * const object = await client.objects.create({
   *   obj: {
   *     object_id: 'object_id',
   *     project_id: 'project_id',
   *     val: {},
   *   },
   * });
   * ```
   */
  create(body: ObjectCreateParams, options?: RequestOptions): APIPromise<ObjectCreateResponse> {
    return this._client.post('/obj/create', { body, ...options });
  }

  /**
   * Obj Delete
   *
   * @example
   * ```ts
   * const object = await client.objects.delete({
   *   object_id: 'object_id',
   *   project_id: 'project_id',
   * });
   * ```
   */
  delete(body: ObjectDeleteParams, options?: RequestOptions): APIPromise<ObjectDeleteResponse> {
    return this._client.post('/obj/delete', { body, ...options });
  }

  /**
   * Objs Query
   *
   * @example
   * ```ts
   * const response = await client.objects.query({
   *   project_id: 'user/project',
   * });
   * ```
   */
  query(body: ObjectQueryParams, options?: RequestOptions): APIPromise<ObjectQueryResponse> {
    return this._client.post('/objs/query', { body, ...options });
  }

  /**
   * Obj Read
   *
   * @example
   * ```ts
   * const response = await client.objects.read({
   *   digest: 'digest',
   *   object_id: 'object_id',
   *   project_id: 'project_id',
   * });
   * ```
   */
  read(body: ObjectReadParams, options?: RequestOptions): APIPromise<ObjectReadResponse> {
    return this._client.post('/obj/read', { body, ...options });
  }
}

export interface ObjectCreateResponse {
  digest: string;

  object_id?: string | null;
}

export interface ObjectDeleteResponse {
  num_deleted: number;

  /**
   * Metadata for each deleted object version, with digest aliases resolved to
   * content digests. None when the backing server does not report it.
   */
  deleted_versions?: Array<ObjectDeleteResponse.DeletedVersion> | null;
}

export namespace ObjectDeleteResponse {
  export interface DeletedVersion {
    digest: string;

    base_object_class?: string | null;

    leaf_object_class?: string | null;
  }
}

export interface ObjectQueryResponse {
  objs: Array<ObjectQueryResponse.Obj>;
}

export namespace ObjectQueryResponse {
  export interface Obj {
    base_object_class: string | null;

    created_at: string;

    digest: string;

    is_latest: number;

    kind: string;

    object_id: string;

    project_id: string;

    val: unknown;

    version_index: number;

    aliases?: Array<string> | null;

    deleted_at?: string | null;

    leaf_object_class?: string | null;

    size_bytes?: number | null;

    tags?: Array<string> | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }
}

export interface ObjectReadResponse {
  obj: ObjectReadResponse.Obj;
}

export namespace ObjectReadResponse {
  export interface Obj {
    base_object_class: string | null;

    created_at: string;

    digest: string;

    is_latest: number;

    kind: string;

    object_id: string;

    project_id: string;

    val: unknown;

    version_index: number;

    aliases?: Array<string> | null;

    deleted_at?: string | null;

    leaf_object_class?: string | null;

    size_bytes?: number | null;

    tags?: Array<string> | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }
}

export interface ObjectCreateParams {
  obj: ObjectCreateParams.Obj;
}

export namespace ObjectCreateParams {
  export interface Obj {
    object_id: string;

    project_id: string;

    val: unknown;

    builtin_object_class?: string | null;

    /**
     * Client-computed digest for server-side validation. If provided, the server will
     * verify it matches the server-computed digest.
     */
    expected_digest?: string | null;

    /**
     * @deprecated
     */
    set_base_object_class?: string | null;

    /**
     * Do not set directly. Server will automatically populate this field.
     */
    wb_user_id?: string | null;
  }
}

export interface ObjectDeleteParams {
  object_id: string;

  project_id: string;

  /**
   * List of digests to delete. If not provided, all digests for the object will be
   * deleted.
   */
  digests?: Array<string> | null;
}

export interface ObjectQueryParams {
  /**
   * The ID of the project to query
   */
  project_id: string;

  /**
   * Filter criteria for the query. See `ObjectVersionFilter`
   */
  filter?: ObjectQueryParams.Filter | null;

  /**
   * If true, the `size_bytes` column is returned.
   */
  include_storage_size?: boolean | null;

  /**
   * If true, tags and aliases are fetched and included in the response.
   */
  include_tags_and_aliases?: boolean | null;

  /**
   * Maximum number of results to return
   */
  limit?: number | null;

  /**
   * If true, the `val` column is not read from the database and is empty.All other
   * fields are returned.
   */
  metadata_only?: boolean | null;

  /**
   * Number of results to skip before returning
   */
  offset?: number | null;

  /**
   * Sorting criteria for the query results. Currently only supports 'object_id' and
   * 'created_at'.
   */
  sort_by?: Array<ObjectQueryParams.SortBy> | null;
}

export namespace ObjectQueryParams {
  /**
   * Filter criteria for the query. See `ObjectVersionFilter`
   */
  export interface Filter {
    /**
     * Filter objects that have any of the specified aliases
     */
    aliases?: Array<string> | null;

    /**
     * Filter objects by their base classes
     */
    base_object_classes?: Array<string> | null;

    /**
     * Exclude objects by their base classes
     */
    exclude_base_object_classes?: Array<string> | null;

    /**
     * Filter objects based on whether they are weave.ops or not. `True` will only
     * return ops, `False` will return non-ops, and `None` will return all objects
     */
    is_op?: boolean | null;

    /**
     * If True, return only the latest version of each object. `False` and `None` will
     * return all versions
     */
    latest_only?: boolean | null;

    /**
     * Filter objects by their leaf classes
     */
    leaf_object_classes?: Array<string> | null;

    /**
     * Filter objects by their IDs
     */
    object_ids?: Array<string> | null;

    /**
     * Filter object versions that have any of the specified tags
     */
    tags?: Array<string> | null;
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export interface ObjectReadParams {
  digest: string;

  object_id: string;

  project_id: string;

  /**
   * If true, tags and aliases are fetched and included in the response.
   */
  include_tags_and_aliases?: boolean | null;

  /**
   * If true, the `val` column is not read from the database and is empty.All other
   * fields are returned.
   */
  metadata_only?: boolean | null;
}

Objects.Tags = Tags;
Objects.Aliases = Aliases;

export declare namespace Objects {
  export {
    type ObjectCreateResponse as ObjectCreateResponse,
    type ObjectDeleteResponse as ObjectDeleteResponse,
    type ObjectQueryResponse as ObjectQueryResponse,
    type ObjectReadResponse as ObjectReadResponse,
    type ObjectCreateParams as ObjectCreateParams,
    type ObjectDeleteParams as ObjectDeleteParams,
    type ObjectQueryParams as ObjectQueryParams,
    type ObjectReadParams as ObjectReadParams,
  };

  export {
    Tags as Tags,
    type TagListResponse as TagListResponse,
    type TagAddResponse as TagAddResponse,
    type TagRemoveResponse as TagRemoveResponse,
    type TagListParams as TagListParams,
    type TagAddParams as TagAddParams,
    type TagRemoveParams as TagRemoveParams,
  };

  export {
    Aliases as Aliases,
    type AliasListResponse as AliasListResponse,
    type AliasRemoveResponse as AliasRemoveResponse,
    type AliasSetResponse as AliasSetResponse,
    type AliasListParams as AliasListParams,
    type AliasRemoveParams as AliasRemoveParams,
    type AliasSetParams as AliasSetParams,
  };
}
