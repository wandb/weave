// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2EvaluationRuns extends APIResource {
  /**
   * Create an evaluation run.
   */
  create(
    project: string,
    params: V2EvaluationRunCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationRunCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/evaluation_runs`, { body, ...options });
  }

  /**
   * List evaluation runs.
   */
  list(
    project: string,
    params: V2EvaluationRunListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2EvaluationRunListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/evaluation_runs`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/jsonl' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2EvaluationRunListResponse>
    >;
  }

  /**
   * Delete evaluation runs.
   */
  delete(
    project: string,
    params: V2EvaluationRunDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationRunDeleteResponse> {
    const { entity, evaluation_run_ids } = params;
    return this._client.delete(path`/v2/${entity}/${project}/evaluation_runs`, {
      query: { evaluation_run_ids },
      ...options,
    });
  }

  /**
   * Finish an evaluation run.
   */
  finish(
    evaluationRunID: string,
    params: V2EvaluationRunFinishParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationRunFinishResponse> {
    const { entity, project, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/evaluation_runs/${evaluationRunID}/finish`, {
      body,
      ...options,
    });
  }

  /**
   * Read an evaluation run.
   */
  read(
    evaluationRunID: string,
    params: V2EvaluationRunReadParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationRunReadResponse> {
    const { entity, project } = params;
    return this._client.get(path`/v2/${entity}/${project}/evaluation_runs/${evaluationRunID}`, options);
  }
}

export interface V2EvaluationRunCreateResponse {
  /**
   * The ID of the created evaluation run
   */
  evaluation_run_id: string;
}

export interface V2EvaluationRunListResponse {
  /**
   * Reference to the evaluation (weave:// URI)
   */
  evaluation: string;

  /**
   * The evaluation run ID
   */
  evaluation_run_id: string;

  /**
   * Reference to the model (weave:// URI)
   */
  model: string;

  /**
   * When the evaluation run finished
   */
  finished_at?: string | null;

  /**
   * Source evaluation run ID if this run was created by rescoring
   */
  source_evaluation_run_id?: string | null;

  /**
   * When the evaluation run started
   */
  started_at?: string | null;

  /**
   * Status of the evaluation run
   */
  status?: string | null;

  /**
   * Summary data for the evaluation run
   */
  summary?: { [key: string]: unknown } | null;
}

export interface V2EvaluationRunDeleteResponse {
  /**
   * Number of evaluation runs deleted
   */
  num_deleted: number;
}

export interface V2EvaluationRunFinishResponse {
  /**
   * Whether the evaluation run was finished successfully
   */
  success: boolean;
}

export interface V2EvaluationRunReadResponse {
  /**
   * Reference to the evaluation (weave:// URI)
   */
  evaluation: string;

  /**
   * The evaluation run ID
   */
  evaluation_run_id: string;

  /**
   * Reference to the model (weave:// URI)
   */
  model: string;

  /**
   * When the evaluation run finished
   */
  finished_at?: string | null;

  /**
   * Source evaluation run ID if this run was created by rescoring
   */
  source_evaluation_run_id?: string | null;

  /**
   * When the evaluation run started
   */
  started_at?: string | null;

  /**
   * Status of the evaluation run
   */
  status?: string | null;

  /**
   * Summary data for the evaluation run
   */
  summary?: { [key: string]: unknown } | null;
}

export interface V2EvaluationRunCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: Reference to the evaluation (weave:// URI)
   */
  evaluation: string;

  /**
   * Body param: Reference to the model (weave:// URI)
   */
  model: string;

  /**
   * Body param: Source evaluation run ID if this run was created by rescoring —
   * provenance link
   */
  source_evaluation_run_id?: string | null;
}

export interface V2EvaluationRunListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Filter by evaluation run IDs
   */
  evaluation_run_ids?: Array<string> | null;

  /**
   * Query param: Filter by evaluation references
   */
  evaluations?: Array<string> | null;

  /**
   * Query param: Maximum number of evaluation runs to return
   */
  limit?: number | null;

  /**
   * Query param: Filter by model references
   */
  models?: Array<string> | null;

  /**
   * Query param: Number of evaluation runs to skip
   */
  offset?: number | null;
}

export interface V2EvaluationRunDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: List of evaluation run IDs to delete
   */
  evaluation_run_ids: Array<string>;
}

export interface V2EvaluationRunFinishParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Body param: Optional summary dictionary for the evaluation run
   */
  summary?: { [key: string]: unknown } | null;
}

export interface V2EvaluationRunReadParams {
  entity: string;

  project: string;
}

export declare namespace V2EvaluationRuns {
  export {
    type V2EvaluationRunCreateResponse as V2EvaluationRunCreateResponse,
    type V2EvaluationRunListResponse as V2EvaluationRunListResponse,
    type V2EvaluationRunDeleteResponse as V2EvaluationRunDeleteResponse,
    type V2EvaluationRunFinishResponse as V2EvaluationRunFinishResponse,
    type V2EvaluationRunReadResponse as V2EvaluationRunReadResponse,
    type V2EvaluationRunCreateParams as V2EvaluationRunCreateParams,
    type V2EvaluationRunListParams as V2EvaluationRunListParams,
    type V2EvaluationRunDeleteParams as V2EvaluationRunDeleteParams,
    type V2EvaluationRunFinishParams as V2EvaluationRunFinishParams,
    type V2EvaluationRunReadParams as V2EvaluationRunReadParams,
  };
}
