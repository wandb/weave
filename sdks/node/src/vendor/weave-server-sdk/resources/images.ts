// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Images extends APIResource {
  /**
   * Image Create
   */
  create(body: ImageCreateParams, options?: RequestOptions): APIPromise<ImageCreateResponse> {
    return this._client.post('/image/create', { body, ...options });
  }
}

export interface ImageCreateResponse {
  response: { [key: string]: unknown };

  weave_call_id?: string | null;
}

export interface ImageCreateParams {
  inputs: ImageCreateParams.Inputs;

  project_id: string;

  /**
   * Whether to track this image generation call in the trace server
   */
  track_llm_call?: boolean | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export namespace ImageCreateParams {
  export interface Inputs {
    model: string;

    prompt: string;

    n?: number | null;
  }
}

export declare namespace Images {
  export { type ImageCreateResponse as ImageCreateResponse, type ImageCreateParams as ImageCreateParams };
}
