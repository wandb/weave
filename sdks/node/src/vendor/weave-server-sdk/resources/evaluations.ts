// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Evaluations extends APIResource {
  /**
   * Evaluate Model
   */
  evaluateModel(
    body: EvaluationEvaluateModelParams,
    options?: RequestOptions,
  ): APIPromise<EvaluationEvaluateModelResponse> {
    return this._client.post('/evaluations/evaluate_model', { body, ...options });
  }

  /**
   * Rescore an existing evaluation run with different scorer(s).
   *
   * Applies the provided scorer(s) to the predictions from source_evaluation_run_id
   * and returns a new evaluation_run_id. Original prediction call IDs are preserved.
   */
  rescore(body: EvaluationRescoreParams, options?: RequestOptions): APIPromise<EvaluationRescoreResponse> {
    return this._client.post('/evaluations/rescore', { body, ...options });
  }

  /**
   * Evaluation Status
   */
  status(body: EvaluationStatusParams, options?: RequestOptions): APIPromise<EvaluationStatusResponse> {
    return this._client.post('/evaluations/status', { body, ...options });
  }
}

export interface EvaluationEvaluateModelResponse {
  call_id: string;
}

/**
 * Response for a rescore request.
 */
export interface EvaluationRescoreResponse {
  /**
   * Call ID for /evaluations/status polling
   */
  call_id: string;

  /**
   * The newly created EvaluationRun ID
   */
  evaluation_run_id: string;
}

export interface EvaluationStatusResponse {
  status:
    | EvaluationStatusResponse.EvaluationStatusNotFound
    | EvaluationStatusResponse.EvaluationStatusRunning
    | EvaluationStatusResponse.EvaluationStatusFailed
    | EvaluationStatusResponse.EvaluationStatusComplete;
}

export namespace EvaluationStatusResponse {
  export interface EvaluationStatusNotFound {
    code?: 'not_found';
  }

  export interface EvaluationStatusRunning {
    completed_rows: number;

    total_rows: number;

    code?: 'running';
  }

  export interface EvaluationStatusFailed {
    code?: 'failed';

    error?: string | null;
  }

  export interface EvaluationStatusComplete {
    output: { [key: string]: unknown };

    code?: 'complete';
  }
}

export interface EvaluationEvaluateModelParams {
  evaluation_ref: string;

  model_ref: string;

  project_id: string;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface EvaluationRescoreParams {
  project_id: string;

  /**
   * Scorer references (weave:// URIs) to apply; must be non-empty
   */
  scorer_refs: Array<string>;

  /**
   * The evaluation run whose predictions will be rescored
   */
  source_evaluation_run_id: string;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface EvaluationStatusParams {
  call_id: string;

  project_id: string;
}

export declare namespace Evaluations {
  export {
    type EvaluationEvaluateModelResponse as EvaluationEvaluateModelResponse,
    type EvaluationRescoreResponse as EvaluationRescoreResponse,
    type EvaluationStatusResponse as EvaluationStatusResponse,
    type EvaluationEvaluateModelParams as EvaluationEvaluateModelParams,
    type EvaluationRescoreParams as EvaluationRescoreParams,
    type EvaluationStatusParams as EvaluationStatusParams,
  };
}
