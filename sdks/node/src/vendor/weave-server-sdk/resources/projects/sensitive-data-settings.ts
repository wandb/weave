// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class SensitiveDataSettings extends APIResource {
  /**
   * Read the owning organization's sensitive-data policy for a project.
   */
  read(
    query: SensitiveDataSettingReadParams,
    options?: RequestOptions,
  ): APIPromise<SensitiveDataSettingReadResponse> {
    return this._client.get('/project/sensitive_data_settings', { query, ...options });
  }
}

export interface SensitiveDataSettingReadResponse {
  policy: 'off' | 'pii-v1';
}

export interface SensitiveDataSettingReadParams {
  project_id: string;
}

export declare namespace SensitiveDataSettings {
  export {
    type SensitiveDataSettingReadResponse as SensitiveDataSettingReadResponse,
    type SensitiveDataSettingReadParams as SensitiveDataSettingReadParams,
  };
}
