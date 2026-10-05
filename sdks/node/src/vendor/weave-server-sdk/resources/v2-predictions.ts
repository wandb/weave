// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Predictions extends APIResource {
  /**
   * Create a prediction.
   */
  create(
    project: string,
    params: V2PredictionCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2PredictionCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/predictions`, { body, ...options });
  }

  /**
   * List predictions.
   */
  list(
    project: string,
    params: V2PredictionListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2PredictionListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/predictions`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/jsonl' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2PredictionListResponse>
    >;
  }

  /**
   * Delete predictions.
   */
  delete(
    project: string,
    params: V2PredictionDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2PredictionDeleteResponse> {
    const { entity, prediction_ids } = params;
    return this._client.delete(path`/v2/${entity}/${project}/predictions`, {
      query: { prediction_ids },
      ...options,
    });
  }

  /**
   * Finish a prediction.
   */
  finish(
    predictionID: string,
    params: V2PredictionFinishParams,
    options?: RequestOptions,
  ): APIPromise<V2PredictionFinishResponse> {
    const { entity, project } = params;
    return this._client.post(path`/v2/${entity}/${project}/predictions/${predictionID}/finish`, options);
  }

  /**
   * Read a prediction.
   */
  read(
    predictionID: string,
    params: V2PredictionReadParams,
    options?: RequestOptions,
  ): APIPromise<V2PredictionReadResponse> {
    const { entity, project } = params;
    return this._client.get(path`/v2/${entity}/${project}/predictions/${predictionID}`, options);
  }
}

export interface V2PredictionCreateResponse {
  /**
   * The prediction ID
   */
  prediction_id: string;
}

export interface V2PredictionListResponse {
  /**
   * The inputs to the prediction
   */
  inputs: { [key: string]: unknown };

  /**
   * The model reference (weave:// URI)
   */
  model: string;

  /**
   * The output of the prediction
   */
  output: unknown;

  /**
   * The prediction ID
   */
  prediction_id: string;

  /**
   * Evaluation run ID if this prediction is linked to one
   */
  evaluation_run_id?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface V2PredictionDeleteResponse {
  /**
   * Number of predictions deleted
   */
  num_deleted: number;
}

export interface V2PredictionFinishResponse {
  /**
   * Whether the prediction was finished successfully
   */
  success: boolean;
}

export interface V2PredictionReadResponse {
  /**
   * The inputs to the prediction
   */
  inputs: { [key: string]: unknown };

  /**
   * The model reference (weave:// URI)
   */
  model: string;

  /**
   * The output of the prediction
   */
  output: unknown;

  /**
   * The prediction ID
   */
  prediction_id: string;

  /**
   * Evaluation run ID if this prediction is linked to one
   */
  evaluation_run_id?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface V2PredictionCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: The inputs to the prediction
   */
  inputs: { [key: string]: unknown };

  /**
   * Body param: The model reference (weave:// URI)
   */
  model: string;

  /**
   * Body param: The output of the prediction
   */
  output: unknown;

  /**
   * Body param: Optional evaluation run ID to link this prediction as a child call
   */
  evaluation_run_id?: string | null;

  /**
   * Body param: Optional GenAI span reference(s) produced by this prediction.
   */
  genai_span_ref?: Array<V2PredictionCreateParams.GenaiSpanRef> | null;
}

export namespace V2PredictionCreateParams {
  export interface GenaiSpanRef {
    span_id: string;

    trace_id: string;
  }
}

export interface V2PredictionListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Filter by evaluation run ID
   */
  evaluation_run_id?: string | null;

  /**
   * Query param: Maximum number of predictions to return
   */
  limit?: number | null;

  /**
   * Query param: Number of predictions to skip
   */
  offset?: number | null;
}

export interface V2PredictionDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: List of prediction IDs to delete
   */
  prediction_ids: Array<string>;
}

export interface V2PredictionFinishParams {
  entity: string;

  project: string;
}

export interface V2PredictionReadParams {
  entity: string;

  project: string;
}

export declare namespace V2Predictions {
  export {
    type V2PredictionCreateResponse as V2PredictionCreateResponse,
    type V2PredictionListResponse as V2PredictionListResponse,
    type V2PredictionDeleteResponse as V2PredictionDeleteResponse,
    type V2PredictionFinishResponse as V2PredictionFinishResponse,
    type V2PredictionReadResponse as V2PredictionReadResponse,
    type V2PredictionCreateParams as V2PredictionCreateParams,
    type V2PredictionListParams as V2PredictionListParams,
    type V2PredictionDeleteParams as V2PredictionDeleteParams,
    type V2PredictionFinishParams as V2PredictionFinishParams,
    type V2PredictionReadParams as V2PredictionReadParams,
  };
}
