// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as IngestSamplingSettingsAPI from './ingest-sampling-settings';
import {
  IngestSamplingSettingReadParams,
  IngestSamplingSettingReadResponse,
  IngestSamplingSettings,
} from './ingest-sampling-settings';
import * as SensitiveDataSettingsAPI from './sensitive-data-settings';
import {
  SensitiveDataSettingReadParams,
  SensitiveDataSettingReadResponse,
  SensitiveDataSettings,
} from './sensitive-data-settings';
import * as TtlSettingsAPI from './ttl-settings';
import {
  TtlSettingReadParams,
  TtlSettingReadResponse,
  TtlSettingUpdateParams,
  TtlSettingUpdateResponse,
  TtlSettings,
} from './ttl-settings';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Projects extends APIResource {
  ttlSettings: TtlSettingsAPI.TtlSettings = new TtlSettingsAPI.TtlSettings(this._client);
  ingestSamplingSettings: IngestSamplingSettingsAPI.IngestSamplingSettings =
    new IngestSamplingSettingsAPI.IngestSamplingSettings(this._client);
  sensitiveDataSettings: SensitiveDataSettingsAPI.SensitiveDataSettings =
    new SensitiveDataSettingsAPI.SensitiveDataSettings(this._client);

  /**
   * Project Stats
   */
  stats(body: ProjectStatsParams, options?: RequestOptions): APIPromise<ProjectStatsResponse> {
    return this._client.post('/project/stats', { body, ...options });
  }
}

export interface ProjectStatsResponse {
  files_storage_size_bytes: number;

  objects_storage_size_bytes: number;

  tables_storage_size_bytes: number;

  trace_storage_size_bytes: number;
}

export interface ProjectStatsParams {
  project_id: string;

  include_file_storage_size?: boolean | null;

  include_object_storage_size?: boolean | null;

  include_table_storage_size?: boolean | null;

  include_trace_storage_size?: boolean | null;
}

Projects.TtlSettings = TtlSettings;
Projects.IngestSamplingSettings = IngestSamplingSettings;
Projects.SensitiveDataSettings = SensitiveDataSettings;

export declare namespace Projects {
  export { type ProjectStatsResponse as ProjectStatsResponse, type ProjectStatsParams as ProjectStatsParams };

  export {
    TtlSettings as TtlSettings,
    type TtlSettingUpdateResponse as TtlSettingUpdateResponse,
    type TtlSettingReadResponse as TtlSettingReadResponse,
    type TtlSettingUpdateParams as TtlSettingUpdateParams,
    type TtlSettingReadParams as TtlSettingReadParams,
  };

  export {
    IngestSamplingSettings as IngestSamplingSettings,
    type IngestSamplingSettingReadResponse as IngestSamplingSettingReadResponse,
    type IngestSamplingSettingReadParams as IngestSamplingSettingReadParams,
  };

  export {
    SensitiveDataSettings as SensitiveDataSettings,
    type SensitiveDataSettingReadResponse as SensitiveDataSettingReadResponse,
    type SensitiveDataSettingReadParams as SensitiveDataSettingReadParams,
  };
}
