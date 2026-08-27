// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { buildHeaders } from '../internal/headers';
import { RequestOptions } from '../internal/request-options';
import { JSONLDecoder } from '../internal/decoders/jsonl';
import { path } from '../internal/utils/path';

export class V2Scores extends APIResource {
  /**
   * Create a score.
   */
  create(
    project: string,
    params: V2ScoreCreateParams,
    options?: RequestOptions,
  ): APIPromise<V2ScoreCreateResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/scores`, { body, ...options });
  }

  /**
   * List scores.
   */
  list(
    project: string,
    params: V2ScoreListParams,
    options?: RequestOptions,
  ): APIPromise<JSONLDecoder<V2ScoreListResponse>> {
    const { entity, ...query } = params;
    return this._client
      .get(path`/v2/${entity}/${project}/scores`, {
        query,
        ...options,
        headers: buildHeaders([{ Accept: 'application/jsonl' }, options?.headers]),
        stream: true,
        __binaryResponse: true,
      })
      ._thenUnwrap((_, props) => JSONLDecoder.fromResponse(props.response, props.controller)) as APIPromise<
      JSONLDecoder<V2ScoreListResponse>
    >;
  }

  /**
   * Delete scores.
   */
  delete(
    project: string,
    params: V2ScoreDeleteParams,
    options?: RequestOptions,
  ): APIPromise<V2ScoreDeleteResponse> {
    const { entity, score_ids } = params;
    return this._client.delete(path`/v2/${entity}/${project}/scores`, { query: { score_ids }, ...options });
  }

  /**
   * Read a score.
   */
  read(
    scoreID: string,
    params: V2ScoreReadParams,
    options?: RequestOptions,
  ): APIPromise<V2ScoreReadResponse> {
    const { entity, project } = params;
    return this._client.get(path`/v2/${entity}/${project}/scores/${scoreID}`, options);
  }
}

export interface V2ScoreCreateResponse {
  /**
   * The score ID
   */
  score_id: string;
}

export interface V2ScoreListResponse {
  /**
   * The score ID
   */
  score_id: string;

  /**
   * The scorer reference (weave:// URI)
   */
  scorer: string;

  /**
   * The raw output of the scorer
   */
  value: unknown;

  /**
   * Evaluation run ID if this score is linked to one
   */
  evaluation_run_id?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface V2ScoreDeleteResponse {
  /**
   * Number of scores deleted
   */
  num_deleted: number;
}

export interface V2ScoreReadResponse {
  /**
   * The score ID
   */
  score_id: string;

  /**
   * The scorer reference (weave:// URI)
   */
  scorer: string;

  /**
   * The raw output of the scorer
   */
  value: unknown;

  /**
   * Evaluation run ID if this score is linked to one
   */
  evaluation_run_id?: string | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export interface V2ScoreCreateParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: The prediction ID
   */
  prediction_id: string;

  /**
   * Body param: The scorer reference (weave:// URI)
   */
  scorer: string;

  /**
   * Body param: The raw output of the scorer
   */
  value: unknown;

  /**
   * Body param: Optional evaluation run ID to link this score as a child call
   */
  evaluation_run_id?: string | null;
}

export interface V2ScoreListParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: Filter by evaluation run ID
   */
  evaluation_run_id?: string | null;

  /**
   * Query param: Maximum number of scores to return
   */
  limit?: number | null;

  /**
   * Query param: Number of scores to skip
   */
  offset?: number | null;
}

export interface V2ScoreDeleteParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Query param: List of score IDs to delete
   */
  score_ids: Array<string>;
}

export interface V2ScoreReadParams {
  entity: string;

  project: string;
}

export declare namespace V2Scores {
  export {
    type V2ScoreCreateResponse as V2ScoreCreateResponse,
    type V2ScoreListResponse as V2ScoreListResponse,
    type V2ScoreDeleteResponse as V2ScoreDeleteResponse,
    type V2ScoreReadResponse as V2ScoreReadResponse,
    type V2ScoreCreateParams as V2ScoreCreateParams,
    type V2ScoreListParams as V2ScoreListParams,
    type V2ScoreDeleteParams as V2ScoreDeleteParams,
    type V2ScoreReadParams as V2ScoreReadParams,
  };
}
