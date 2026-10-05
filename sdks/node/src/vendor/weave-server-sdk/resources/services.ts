// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Services extends APIResource {
  /**
   * Read Root
   *
   * @example
   * ```ts
   * const response = await client.services.healthCheck();
   * ```
   */
  healthCheck(options?: RequestOptions): APIPromise<unknown> {
    return this._client.get('/health', options);
  }

  /**
   * Projects Info
   *
   * @example
   * ```ts
   * const response = await client.services.projectsInfo({
   *   project_ids: ['entity-a/project-a', 'entity-b/project-b'],
   * });
   * ```
   */
  projectsInfo(
    body: ServiceProjectsInfoParams,
    options?: RequestOptions,
  ): APIPromise<ServiceProjectsInfoResponse> {
    return this._client.post('/service/projects_info', { body, ...options });
  }

  /**
   * Server Info
   *
   * @example
   * ```ts
   * const serverInfoRes = await client.services.serverInfo();
   * ```
   */
  serverInfo(options?: RequestOptions): APIPromise<ServerInfoRes> {
    return this._client.get('/server_info', options);
  }
}

export interface ServerInfoRes {
  min_required_weave_python_version: string;

  trace_server_version: string;
}

export type ServiceHealthCheckResponse = unknown;

export type ServiceProjectsInfoResponse = Array<ServiceProjectsInfoResponse.ServiceProjectsInfoResponseItem>;

export namespace ServiceProjectsInfoResponse {
  export interface ServiceProjectsInfoResponseItem {
    /**
     * External project ID in 'entity/project' format.
     */
    external_project_id: string;

    /**
     * Internal project ID.
     */
    internal_project_id: string;
  }
}

export interface ServiceProjectsInfoParams {
  /**
   * External project IDs in 'entity/project' format.
   */
  project_ids: Array<string>;
}

export declare namespace Services {
  export {
    type ServerInfoRes as ServerInfoRes,
    type ServiceHealthCheckResponse as ServiceHealthCheckResponse,
    type ServiceProjectsInfoResponse as ServiceProjectsInfoResponse,
    type ServiceProjectsInfoParams as ServiceProjectsInfoParams,
  };
}
