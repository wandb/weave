// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { type Uploadable } from '../core/uploads';
import { RequestOptions } from '../internal/request-options';
import { multipartFormRequestOptions } from '../internal/uploads';

export class Files extends APIResource {
  /**
   * File Create
   */
  create(body: FileCreateParams, options?: RequestOptions): APIPromise<FileCreateResponse> {
    return this._client.post('/file/create', multipartFormRequestOptions({ body, ...options }, this._client));
  }

  /**
   * File Content
   */
  content(body: FileContentParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/file/content', { body, ...options });
  }

  /**
   * Files Stats
   */
  stats(body: FileStatsParams, options?: RequestOptions): APIPromise<FileStatsResponse> {
    return this._client.post('/files/query_stats', { body, ...options });
  }
}

export interface FileCreateResponse {
  digest: string;
}

export type FileContentResponse = unknown;

export interface FileStatsResponse {
  total_size_bytes: number;
}

export interface FileCreateParams {
  file: Uploadable;

  project_id: string;

  expected_digest?: string | null;
}

export interface FileContentParams {
  digest: string;

  project_id: string;
}

export interface FileStatsParams {
  project_id: string;
}

export declare namespace Files {
  export {
    type FileCreateResponse as FileCreateResponse,
    type FileContentResponse as FileContentResponse,
    type FileStatsResponse as FileStatsResponse,
    type FileCreateParams as FileCreateParams,
    type FileContentParams as FileContentParams,
    type FileStatsParams as FileStatsParams,
  };
}
