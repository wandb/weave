// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Evaluations extends APIResource {
  /**
   * Create an evaluation object.
   */
  create(
    project: string,
    params: V2EvaluationCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/evaluations`, { body, ...options });
  }

  /**
   * List evaluation objects.
   */
  list(
    project: string,
    params: V2EvaluationListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2EvaluationListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/evaluations`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/x-ndjson' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2EvaluationListResponse>
    >;
  }

  /**
   * Delete an evaluation object.
   */
  delete(
    objectID: string,
    params: V2EvaluationDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationDeleteResponse> {
    const { entity, project, digests } = params;
    return this._client.delete(path`/v2/${entity}/${project}/evaluations/${objectID}`, {
      query: { digests },
      ...options,
    });
  }

  /**
   * Get an evaluation object.
   */
  read(
    digest: string,
    params: V2EvaluationReadParams,
    options?: RequestOptions,
  ): APIPromise<V2EvaluationReadResponse> {
    const { entity, project, object_id } = params;
    return this._client.get(
      path`/v2/${entity}/${project}/evaluations/${object_id}/versions/${digest}`,
      options,
    );
  }
}

export interface V2EvaluationCreateResponse {
  /**
   * The digest of the created evaluation
   */
  digest: string;

  /**
   * Full reference to the created evaluation
   */
  evaluation_ref: string;

  /**
   * The ID of the created evaluation
   */
  object_id: string;

  /**
   * The version index of the created evaluation
   */
  version_index: number;
}

export interface V2EvaluationListResponse {
  /**
   * When the evaluation was created
   */
  created_at: string;

  /**
   * Dataset reference (weave:// URI)
   */
  dataset: string;

  /**
   * The digest of the evaluation
   */
  digest: string;

  /**
   * The name of the evaluation
   */
  name: string;

  /**
   * The evaluation ID
   */
  object_id: string;

  /**
   * List of scorer references (weave:// URIs)
   */
  scorers: Array<string>;

  /**
   * Number of trials
   */
  trials: number;

  /**
   * The version index of the evaluation
   */
  version_index: number;

  /**
   * A description of the evaluation
   */
  description?: string | null;

  /**
   * Evaluate op reference (weave:// URI)
   */
  evaluate_op?: string | null;

  /**
   * Name for the evaluation run
   */
  evaluation_name?: string | null;

  /**
   * Predict and score op reference (weave:// URI)
   */
  predict_and_score_op?: string | null;

  /**
   * Summarize op reference (weave:// URI)
   */
  summarize_op?: string | null;
}

export interface V2EvaluationDeleteResponse {
  /**
   * Number of evaluation versions deleted
   */
  num_deleted: number;
}

export interface V2EvaluationReadResponse {
  /**
   * When the evaluation was created
   */
  created_at: string;

  /**
   * Dataset reference (weave:// URI)
   */
  dataset: string;

  /**
   * The digest of the evaluation
   */
  digest: string;

  /**
   * The name of the evaluation
   */
  name: string;

  /**
   * The evaluation ID
   */
  object_id: string;

  /**
   * List of scorer references (weave:// URIs)
   */
  scorers: Array<string>;

  /**
   * Number of trials
   */
  trials: number;

  /**
   * The version index of the evaluation
   */
  version_index: number;

  /**
   * A description of the evaluation
   */
  description?: string | null;

  /**
   * Evaluate op reference (weave:// URI)
   */
  evaluate_op?: string | null;

  /**
   * Name for the evaluation run
   */
  evaluation_name?: string | null;

  /**
   * Predict and score op reference (weave:// URI)
   */
  predict_and_score_op?: string | null;

  /**
   * Summarize op reference (weave:// URI)
   */
  summarize_op?: string | null;
}

export interface V2EvaluationCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: Reference to the dataset (weave:// URI)
   */
  dataset: string;

  /**
   * Body param: The name of this evaluation. Evaluations with the same name will be
   * versioned together.
   */
  name: string;

  /**
   * Body param: A description of this evaluation
   */
  description?: string | null;

  /**
   * Body param: Optional attributes for the evaluation
   */
  eval_attributes?: { [key: string]: unknown } | null;

  /**
   * Body param: Name for the evaluation run
   */
  evaluation_name?: string | null;

  /**
   * Body param: List of scorer references (weave:// URIs)
   */
  scorers?: Array<string> | null;

  /**
   * Body param: Number of trials to run
   */
  trials?: number;
}

export interface V2EvaluationListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Maximum number of evaluations to return
   */
  limit?: number | null;

  /**
   * Query param: Number of evaluations to skip
   */
  offset?: number | null;
}

export interface V2EvaluationDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Path param
   */
  project: string;

  /**
   * Query param: List of digests to delete. If not provided, all digests for the
   * evaluation will be deleted.
   */
  digests?: Array<string> | null;
}

export interface V2EvaluationReadParams {
  entity: string;

  project: string;

  object_id: string;
}

export declare namespace V2Evaluations {
  export {
    type V2EvaluationCreateResponse as V2EvaluationCreateResponse,
    type V2EvaluationListResponse as V2EvaluationListResponse,
    type V2EvaluationDeleteResponse as V2EvaluationDeleteResponse,
    type V2EvaluationReadResponse as V2EvaluationReadResponse,
    type V2EvaluationCreateParams as V2EvaluationCreateParams,
    type V2EvaluationListParams as V2EvaluationListParams,
    type V2EvaluationDeleteParams as V2EvaluationDeleteParams,
    type V2EvaluationReadParams as V2EvaluationReadParams,
  };
}
