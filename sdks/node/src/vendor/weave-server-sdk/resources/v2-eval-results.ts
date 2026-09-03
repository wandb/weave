// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import * as Shared from './shared';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';
import { path } from '../internal/utils/path';

export class V2EvalResults extends APIResource {
  /**
   * Read grouped evaluation result rows for one or more evaluations.
   */
  query(
    project: string,
    params: V2EvalResultQueryParams,
    options?: RequestOptions,
  ): APIPromise<V2EvalResultQueryResponse> {
    const { entity, ...body } = params;
    return this._client.post(path`/v2/${entity}/${project}/eval_results/query`, { body, ...options });
  }
}

export interface V2EvalResultQueryResponse {
  rows: Array<V2EvalResultQueryResponse.Row>;

  total_rows: number;

  summary?: V2EvalResultQueryResponse.Summary | null;

  /**
   * Non-fatal warnings (e.g. failed to resolve dataset row refs).
   */
  warnings?: Array<string>;
}

export namespace V2EvalResultQueryResponse {
  export interface Row {
    row_digest: string;

    evaluations?: Array<Row.Evaluation>;

    raw_data_row?: unknown;
  }

  export namespace Row {
    export interface Evaluation {
      evaluation_call_id: string;

      trials?: Array<Evaluation.Trial>;
    }

    export namespace Evaluation {
      export interface Trial {
        predict_and_score_call_id: string;

        genai_span_ref?: Array<Trial.GenaiSpanRef> | null;

        model_latency_seconds?: number | null;

        model_output?: unknown;

        predict_call_id?: string | null;

        scorer_call_ids?: { [key: string]: string };

        scores?: { [key: string]: unknown };

        total_cost?: number | null;

        total_tokens?: number | null;
      }

      export namespace Trial {
        export interface GenaiSpanRef {
          span_id: string;

          trace_id: string;
        }
      }
    }
  }

  export interface Summary {
    evaluations?: Array<Summary.Evaluation>;

    row_count?: number;
  }

  export namespace Summary {
    export interface Evaluation {
      evaluation_call_id: string;

      display_name?: string | null;

      evaluation_ref?: string | null;

      model_ref?: string | null;

      /**
       * Sum of per-trial predict-only cost for this evaluation (the model's predict()
       * cost only, excluding LLM-as-a-judge scorer cost); None when no trial reports
       * cost.
       */
      predict_total_cost?: number | null;

      /**
       * Sum of per-trial predict-only token usage for this evaluation (the model's
       * predict() tokens only, excluding LLM-as-a-judge scorer usage); None when no
       * trial reports usage.
       */
      predict_total_tokens?: number | null;

      scorer_stats?: Array<Evaluation.ScorerStat>;

      started_at?: string | null;

      trace_id?: string | null;

      trial_count?: number;
    }

    export namespace Evaluation {
      /**
       * Stats for a single flattened score dimension (scorer_key or
       * scorer_key.path.to.leaf).
       */
      export interface ScorerStat {
        scorer_key: string;

        numeric_count?: number;

        numeric_mean?: number | null;

        pass_known_count?: number;

        pass_rate?: number | null;

        pass_signal_coverage?: number | null;

        pass_true_count?: number;

        /**
         * Dot-joined subpath for nested dimensions, e.g. 'passed' for
         * token_distance.passed. None for root-level scalar scorers.
         */
        path?: string | null;

        trial_count?: number;

        /**
         * Type of the leaf value: binary (bool), continuous (number), or text (string).
         */
        value_type?: 'binary' | 'continuous' | 'text' | null;
      }
    }
  }
}

export interface V2EvalResultQueryParams {
  /**
   * Path param
   */
  entity: string;

  /**
   * Body param: Evaluation root call IDs to include.
   */
  evaluation_call_ids?: Array<string> | null;

  /**
   * Body param: Alias for evaluation call IDs from the Evaluation Runs API.
   */
  evaluation_run_ids?: Array<string> | null;

  /**
   * Body param: How to combine filters across evaluations: 'and' (Match All - row
   * must match in ALL evals) or 'or' (Match Any - row must match in ANY eval).
   * Defaults to 'or' (Match Any).
   */
  filter_logic_operator?: 'and' | 'or';

  /**
   * Body param: Filters applied to grouped rows. Multiple filters are AND'd
   * together.
   */
  filters?: Array<V2EvalResultQueryParams.Filter> | null;

  /**
   * Body param: When true, price each trial's predict call so rows and summary
   * report predict-only cost (`total_cost` / `predict_total_cost`); scorer costs are
   * excluded. Opt-in: other callers skip the cost computation.
   */
  include_costs?: boolean;

  /**
   * Body param: When true (default), fetch child calls (predict/score) of each
   * predict_and_score call to populate predict_call_id, scorer_call_ids, and more
   * precise latency/token data. When false, these fields are derived from the
   * predict_and_score call itself (predict_call_id and scorer_call_ids will be
   * null/empty).
   */
  include_predict_and_score_children?: boolean;

  /**
   * Body param: When true, populate raw_data_row on each result row. Inline rows are
   * returned as their dict value; dataset-referenced rows are returned as the ref
   * string unless resolve_row_refs is also true.
   */
  include_raw_data_rows?: boolean;

  /**
   * Body param: When true, include grouped row/trial data in `rows` and compute
   * `total_rows` for the requested row-level view.
   */
  include_rows?: boolean;

  /**
   * Body param: When true, include aggregated scorer/evaluation summary data in
   * `summary`.
   */
  include_summary?: boolean;

  /**
   * Body param: Optional row-level page size applied after grouping and
   * intersection.
   */
  limit?: number | null;

  /**
   * Body param: Optional row-level page offset applied after grouping and
   * intersection.
   */
  offset?: number;

  /**
   * Body param: When true, only include rows present in all requested evaluations.
   */
  require_intersection?: boolean;

  /**
   * Body param: When true (requires include_raw_data_rows=True), resolve dataset-row
   * reference strings to actual row data via a table lookup. When false, dataset-row
   * refs are returned as-is.
   */
  resolve_row_refs?: boolean;

  /**
   * Body param: Sort specification for result rows. Supported field prefixes:
   * scores.<name>, inputs.<path>, outputs.<path>. When null, rows are sorted by
   * row_digest ASC.
   */
  sort_by?: Array<V2EvalResultQueryParams.SortBy> | null;

  /**
   * Body param: Optional intersection behavior for the summary section. When null,
   * the value of `require_intersection` is used.
   */
  summary_require_intersection?: boolean | null;
}

export namespace V2EvalResultQueryParams {
  /**
   * A filter scoped to an optional evaluation.
   */
  export interface Filter {
    /**
     * Filter expression. Supported field prefixes: scores.<name>, inputs.<path>,
     * outputs.<path>.
     */
    query: Filter.Query;

    /**
     * When set, filter fields are scoped to this evaluation's data.
     */
    evaluation_call_id?: string | null;
  }

  export namespace Filter {
    /**
     * Filter expression. Supported field prefixes: scores.<name>, inputs.<path>,
     * outputs.<path>.
     */
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

  /**
   * Sort specification for evaluation results, extending SortBy
   */
  export interface SortBy {
    direction: 'asc' | 'desc';

    field: string;

    /**
     * Scope the sort to a specific evaluation's scores.
     */
    evaluation_call_id?: string | null;

    /**
     * When 'value', sort by the field value for the specified evaluation. When
     * 'difference', sort by max-min spread of the field across all evaluations
     * (evaluation_call_id is ignored).
     */
    mode?: 'value' | 'difference';
  }
}

export declare namespace V2EvalResults {
  export {
    type V2EvalResultQueryResponse as V2EvalResultQueryResponse,
    type V2EvalResultQueryParams as V2EvalResultQueryParams,
  };
}
