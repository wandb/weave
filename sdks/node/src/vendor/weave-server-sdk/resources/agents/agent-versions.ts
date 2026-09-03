// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class AgentVersions extends APIResource {
  /**
   * Genai Agent Versions Query
   */
  query(body: AgentVersionQueryParams, options?: RequestOptions): APIPromise<AgentVersionQueryResponse> {
    return this._client.post('/agents/agent-versions/query', { body, ...options });
  }
}

/**
 * Response containing agent version stats.
 */
export interface AgentVersionQueryResponse {
  total_count: number;

  versions: Array<AgentVersionQueryResponse.Version>;
}

export namespace AgentVersionQueryResponse {
  /**
   * Aggregated per-version stats from the agent_versions AMT.
   */
  export interface Version {
    agent_name: string;

    agent_version: string;

    error_count: number;

    first_seen: string | null;

    invocation_count: number;

    last_seen: string | null;

    project_id: string;

    span_count: number;

    total_cost_usd: number | null;

    total_duration_ms: number;

    total_input_tokens: number;

    total_output_tokens: number;
  }
}

export interface AgentVersionQueryParams {
  agent_name: string;

  project_id: string;

  include_costs?: boolean;

  limit?: number;

  offset?: number;

  sort_by?: Array<AgentVersionQueryParams.SortBy> | null;
}

export namespace AgentVersionQueryParams {
  /**
   * Sort specification for agent query endpoints.
   */
  export interface SortBy {
    field: string;

    direction?: 'asc' | 'desc';
  }
}

export declare namespace AgentVersions {
  export {
    type AgentVersionQueryResponse as AgentVersionQueryResponse,
    type AgentVersionQueryParams as AgentVersionQueryParams,
  };
}
