// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class IngestSamplingSettings extends APIResource {
  /**
   * Project Ingest Sampling Settings Read
   */
  read(
    body: IngestSamplingSettingReadParams,
    options?: RequestOptions,
  ): APIPromise<IngestSamplingSettingReadResponse> {
    return this._client.post('/project/ingest_sampling_settings/read', { body, ...options });
  }
}

export interface IngestSamplingSettingReadResponse {
  dry_run: boolean;

  sample_rate: number;
}

export interface IngestSamplingSettingReadParams {
  project_id: string;
}

export declare namespace IngestSamplingSettings {
  export {
    type IngestSamplingSettingReadResponse as IngestSamplingSettingReadResponse,
    type IngestSamplingSettingReadParams as IngestSamplingSettingReadParams,
  };
}
