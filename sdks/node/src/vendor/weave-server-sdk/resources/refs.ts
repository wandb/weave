// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Refs extends APIResource {
  /**
   * Refs Read Batch
   */
  readBatch(body: RefReadBatchParams, options?: RequestOptions): APIPromise<RefReadBatchResponse> {
    return this._client.post('/refs/read_batch', { body, ...options });
  }
}

export interface RefReadBatchResponse {
  vals: Array<unknown>;
}

export interface RefReadBatchParams {
  refs: Array<string>;
}

export declare namespace Refs {
  export { type RefReadBatchResponse as RefReadBatchResponse, type RefReadBatchParams as RefReadBatchParams };
}
