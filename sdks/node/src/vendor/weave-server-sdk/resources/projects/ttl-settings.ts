// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class TtlSettings extends APIResource {
  /**
   * Project Ttl Settings Update
   */
  update(body: TtlSettingUpdateParams, options?: RequestOptions): APIPromise<TtlSettingUpdateResponse> {
    return this._client.post('/project/ttl_settings/update', { body, ...options });
  }

  /**
   * Project Ttl Settings Read
   */
  read(body: TtlSettingReadParams, options?: RequestOptions): APIPromise<TtlSettingReadResponse> {
    return this._client.post('/project/ttl_settings/read', { body, ...options });
  }
}

export interface TtlSettingUpdateResponse {
  retention_days: number | null;
}

export interface TtlSettingReadResponse {
  /**
   * None = no TTL (infinite retention)
   */
  retention_days?: number | null;
}

export interface TtlSettingUpdateParams {
  project_id: string;

  /**
   * None disables TTL; must be None or >= 1
   */
  retention_days?: number | null;

  wb_user_id?: string | null;
}

export interface TtlSettingReadParams {
  project_id: string;
}

export declare namespace TtlSettings {
  export {
    type TtlSettingUpdateResponse as TtlSettingUpdateResponse,
    type TtlSettingReadResponse as TtlSettingReadResponse,
    type TtlSettingUpdateParams as TtlSettingUpdateParams,
    type TtlSettingReadParams as TtlSettingReadParams,
  };
}
