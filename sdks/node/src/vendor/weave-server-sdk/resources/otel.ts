// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Otel extends APIResource {
  /**
   * Export Trace
   */
  export(options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/otel/v1/traces', options);
  }
}

export type OtelExportResponse = unknown;

export declare namespace Otel {
  export { type OtelExportResponse as OtelExportResponse };
}
