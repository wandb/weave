// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import * as Shared from './shared';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Costs extends APIResource {
  /**
   * Cost Create
   *
   * @example
   * ```ts
   * const cost = await client.costs.create({
   *   costs: {
   *     foo: { completion_token_cost: 0, prompt_token_cost: 0 },
   *   },
   *   project_id: 'entity/project',
   * });
   * ```
   */
  create(body: CostCreateParams, options?: RequestOptions): APIPromise<CostCreateResponse> {
    return this._client.post('/cost/create', { body, ...options });
  }

  /**
   * Cost Purge
   *
   * @example
   * ```ts
   * const response = await client.costs.purge({
   *   project_id: 'entity/project',
   *   query: { $expr: { $and: [{ $literal: 'string' }] } },
   * });
   * ```
   */
  purge(body: CostPurgeParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/cost/purge', { body, ...options });
  }

  /**
   * Cost Query
   *
   * @example
   * ```ts
   * const response = await client.costs.query({
   *   project_id: 'entity/project',
   * });
   * ```
   */
  query(body: CostQueryParams, options?: RequestOptions): APIPromise<CostQueryResponse> {
    return this._client.post('/cost/query', { body, ...options });
  }
}

export interface CostCreateResponse {
  ids: Array<Array<unknown>>;
}

export type CostPurgeResponse = unknown;

export interface CostQueryResponse {
  results: Array<CostQueryResponse.Result>;
}

export namespace CostQueryResponse {
  export interface Result {
    id?: string | null;

    cache_creation_input_token_cost?: number | null;

    cache_read_input_token_cost?: number | null;

    completion_token_cost?: number | null;

    completion_token_cost_unit?: string | null;

    effective_date?: string | null;

    llm_id?: string | null;

    prompt_token_cost?: number | null;

    prompt_token_cost_unit?: string | null;

    provider_id?: string | null;
  }
}

export interface CostCreateParams {
  costs: { [key: string]: CostCreateParams.Costs };

  project_id: string;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export namespace CostCreateParams {
  export interface Costs {
    completion_token_cost: number;

    prompt_token_cost: number;

    cache_creation_input_token_cost?: number;

    cache_read_input_token_cost?: number;

    /**
     * The unit of the cost for the completion tokens
     */
    completion_token_cost_unit?: string | null;

    /**
     * The date after which the cost is effective for, will default to the current date
     * if not provided
     */
    effective_date?: string | null;

    /**
     * The unit of the cost for the prompt tokens
     */
    prompt_token_cost_unit?: string | null;

    /**
     * The provider of the LLM, e.g. 'openai' or 'mistral'. If not provided, the
     * provider_id will be set to 'default'
     */
    provider_id?: string | null;
  }
}

export interface CostPurgeParams {
  project_id: string;

  query: CostPurgeParams.Query;
}

export namespace CostPurgeParams {
  export interface Query {
    /**
     * Logical AND. All conditions must evaluate to true.
     *
     * Example:
     * ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
     */
    $expr:
      | Shared.AndOperation
      | Shared.OrOperation
      | Shared.NotOperation
      | Shared.EqOperation
      | Shared.GtOperation
      | Query.LtOperation
      | Shared.GteOperation
      | Query.LteOperation
      | Shared.InOperation
      | Shared.ContainsOperation;
  }

  export namespace Query {
    /**
     * Less than comparison.
     *
     * Example:
     * ` { "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LtOperation {
      $lt: Array<unknown>;
    }

    /**
     * Less than or equal comparison.
     *
     * Example:
     * ` { "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LteOperation {
      $lte: Array<unknown>;
    }
  }
}

export interface CostQueryParams {
  project_id: string;

  fields?: Array<string> | null;

  limit?: number | null;

  offset?: number | null;

  query?: CostQueryParams.Query | null;

  sort_by?: Array<CostQueryParams.SortBy> | null;
}

export namespace CostQueryParams {
  export interface Query {
    /**
     * Logical AND. All conditions must evaluate to true.
     *
     * Example:
     * ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
     */
    $expr:
      | Shared.AndOperation
      | Shared.OrOperation
      | Shared.NotOperation
      | Shared.EqOperation
      | Shared.GtOperation
      | Query.LtOperation
      | Shared.GteOperation
      | Query.LteOperation
      | Shared.InOperation
      | Shared.ContainsOperation;
  }

  export namespace Query {
    /**
     * Less than comparison.
     *
     * Example:
     * ` { "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LtOperation {
      $lt: Array<unknown>;
    }

    /**
     * Less than or equal comparison.
     *
     * Example:
     * ` { "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
     */
    export interface LteOperation {
      $lte: Array<unknown>;
    }
  }

  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;
  }
}

export declare namespace Costs {
  export {
    type CostCreateResponse as CostCreateResponse,
    type CostPurgeResponse as CostPurgeResponse,
    type CostQueryResponse as CostQueryResponse,
    type CostCreateParams as CostCreateParams,
    type CostPurgeParams as CostPurgeParams,
    type CostQueryParams as CostQueryParams,
  };
}
