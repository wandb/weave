// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as Shared from '../shared';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Spans extends APIResource {
  /**
   * Discover typed custom attribute keys on matching agent spans.
   */
  customAttrsSchema(
    body: SpanCustomAttrsSchemaParams,
    options?: RequestOptions,
  ): APIPromise<SpanCustomAttrsSchemaResponse> {
    return this._client.post('/agents/spans/custom-attrs/schema', { body, ...options });
  }

  /**
   * Query agent spans, either as raw rows or grouped aggregates.
   */
  query(body: SpanQueryParams, options?: RequestOptions): APIPromise<SpanQueryResponse> {
    return this._client.post('/agents/spans/query', { body, ...options });
  }

  /**
   * Query chart-ready aggregations over agent spans.
   */
  stats(body: SpanStatsParams, options?: RequestOptions): APIPromise<SpanStatsResponse> {
    return this._client.post('/agents/spans/stats', { body, ...options });
  }
}

/**
 * Typed custom attribute keys available for spans query/group/stats APIs.
 */
export interface SpanCustomAttrsSchemaResponse {
  attributes: Array<SpanCustomAttrsSchemaResponse.Attribute>;

  has_more: boolean;

  limit: number;

  offset: number;
}

export namespace SpanCustomAttrsSchemaResponse {
  /**
   * One custom attribute key/type observed in the matching spans.
   */
  export interface Attribute {
    key: string;

    source: 'custom_attrs_string' | 'custom_attrs_int' | 'custom_attrs_float' | 'custom_attrs_bool';

    span_count: number;

    value_type: 'string' | 'int' | 'float' | 'bool';
  }
}

/**
 * Response from a spans query.
 *
 * Exactly one of `spans` or `groups` will be populated, based on whether the
 * request specified `group_by`.
 */
export interface SpanQueryResponse {
  groups: Array<SpanQueryResponse.Group>;

  spans: Array<SpanQueryResponse.Span>;

  total_count: number;
}

export namespace SpanQueryResponse {
  /**
   * A single row in a grouped spans query response.
   *
   * `group_keys` maps each group_by ref's alias to its value for this row. The
   * remaining fields are a fixed aggregate bundle computed per group.
   */
  export interface Group {
    agent_names: Array<string>;

    agent_versions: Array<string>;

    conversation_count: number;

    conversation_names: Array<string>;

    distributions: { [key: string]: Group.Distributions };

    error_count: number;

    /**
     * A truncated first/last message snippet for a grouped conversation row.
     *
     * `role` is the chat-timeline message type (e.g. "user_message",
     * "assistant_message") so clients can style it consistently with the full chat
     * view; `text` is the trimmed, length-capped preview content.
     */
    first_message: Group.FirstMessage | null;

    first_seen: string | null;

    group_keys: { [key: string]: string | number | boolean | null };

    invocation_count: number;

    /**
     * A truncated first/last message snippet for a grouped conversation row.
     *
     * `role` is the chat-timeline message type (e.g. "user_message",
     * "assistant_message") so clients can style it consistently with the full chat
     * view; `text` is the trimmed, length-capped preview content.
     */
    last_message: Group.LastMessage | null;

    last_seen: string | null;

    metrics: { [key: string]: (string & {}) | string | number | boolean | null };

    provider_names: Array<string>;

    request_models: Array<string>;

    span_count: number;

    total_cache_creation_input_tokens: number;

    total_cache_read_input_tokens: number;

    total_cost_usd: number | null;

    total_duration_ms: number;

    total_input_cost_usd: number | null;

    total_input_tokens: number;

    total_output_cost_usd: number | null;

    total_output_tokens: number;

    total_reasoning_tokens: number;
  }

  export namespace Group {
    /**
     * Distribution data for one span-group/custom-attribute pair.
     */
    export interface Distributions {
      alias: string;

      bins: Array<Distributions.Bin>;

      key: string;

      missing_count: number;

      other_count: number;

      present_count: number;

      source: 'custom_attrs_string' | 'custom_attrs_int' | 'custom_attrs_float' | 'custom_attrs_bool';

      total_count: number;

      value_type: 'string' | 'int' | 'float' | 'bool';

      values: Array<Distributions.Value>;
    }

    export namespace Distributions {
      /**
       * One numeric histogram bin for a custom attribute in a span group.
       */
      export interface Bin {
        count: number;

        index: number;

        max: number;

        min: number;
      }

      /**
       * One categorical custom attribute value count in a span group.
       */
      export interface Value {
        count: number;

        value: string;
      }
    }

    /**
     * A truncated first/last message snippet for a grouped conversation row.
     *
     * `role` is the chat-timeline message type (e.g. "user_message",
     * "assistant_message") so clients can style it consistently with the full chat
     * view; `text` is the trimmed, length-capped preview content.
     */
    export interface FirstMessage {
      role: 'user_message' | 'assistant_message';

      text: string;
    }

    /**
     * A truncated first/last message snippet for a grouped conversation row.
     *
     * `role` is the chat-timeline message type (e.g. "user_message",
     * "assistant_message") so clients can style it consistently with the full chat
     * view; `text` is the trimmed, length-capped preview content.
     */
    export interface LastMessage {
      role: 'user_message' | 'assistant_message';

      text: string;
    }
  }

  /**
   * A normalized agent span returned by query APIs.
   */
  export interface Span {
    agent_description: string | null;

    agent_id: string | null;

    agent_name: string | null;

    agent_version: string | null;

    artifact_refs: Array<string>;

    cache_creation_cost_usd: number | null;

    cache_creation_input_tokens: number | null;

    cache_read_cost_usd: number | null;

    cache_read_input_tokens: number | null;

    compaction_items_after: number | null;

    compaction_items_before: number | null;

    compaction_summary: string | null;

    content_refs: Array<string>;

    conversation_id: string | null;

    conversation_name: string | null;

    custom_attrs_bool: { [key: string]: boolean };

    custom_attrs_float: { [key: string]: number };

    custom_attrs_int: { [key: string]: number };

    custom_attrs_string: { [key: string]: string };

    ended_at: string | null;

    error_type: string | null;

    eval_evaluation_name: string | null;

    eval_example_id: string | null;

    eval_kind: string | null;

    eval_predict_and_score_call_id: string | null;

    eval_row_digest: string | null;

    eval_run_id: string | null;

    eval_trial_index: number | null;

    finish_reasons: Array<string>;

    input_cost_usd: number | null;

    input_messages: Array<Span.InputMessage>;

    input_tokens: number | null;

    object_refs: Array<string>;

    operation_name: string | null;

    output_cost_usd: number | null;

    output_messages: Array<Span.OutputMessage>;

    output_tokens: number | null;

    output_type: string | null;

    parent_call_id: string | null;

    parent_call_trace_id: string | null;

    parent_span_id: string | null;

    project_id: string;

    provider_name: string | null;

    raw_span_dump: string | null;

    reasoning_content: string | null;

    reasoning_tokens: number | null;

    request_choice_count: number | null;

    request_frequency_penalty: number | null;

    request_max_tokens: number | null;

    request_model: string | null;

    request_presence_penalty: number | null;

    request_seed: number | null;

    request_stop_sequences: Array<string>;

    request_temperature: number | null;

    request_top_p: number | null;

    response_id: string | null;

    response_model: string | null;

    server_address: string | null;

    server_port: number | null;

    span_id: string;

    span_kind: 'UNSPECIFIED' | 'INTERNAL' | 'SERVER' | 'CLIENT' | 'PRODUCER' | 'CONSUMER' | null;

    span_name: string | null;

    started_at: string | null;

    status_code: 'UNSET' | 'OK' | 'ERROR' | null;

    status_message: string | null;

    system_instructions: Array<string>;

    tool_call_arguments: string | null;

    tool_call_id: string | null;

    tool_call_result: string | null;

    tool_definitions: string | null;

    tool_description: string | null;

    tool_name: string | null;

    tool_type: string | null;

    total_cost_usd: number | null;

    trace_id: string;

    wb_run_id: string | null;

    wb_run_step: number | null;

    wb_run_step_end: number | null;

    wb_user_id: string | null;
  }

  export namespace Span {
    /**
     * A single message normalized from any provider format.
     *
     * Maps to ClickHouse `Tuple(role String, content String, finish_reason String)`.
     *
     * - role: message role (user, assistant, tool, system)
     * - content: plain text for simple messages, or JSON-serialized parts array for
     *   multimodal/structured messages
     * - finish_reason: per-message finish reason (output messages only)
     *
     * Serialization JSON Schema marks defaulted fields required. In the public OpenAPI
     * document this class appears only as an AgentSpanSchema message element. Ingest
     * validation is unchanged.
     */
    export interface InputMessage {
      content: string;

      finish_reason: string;

      role: string;
    }

    /**
     * A single message normalized from any provider format.
     *
     * Maps to ClickHouse `Tuple(role String, content String, finish_reason String)`.
     *
     * - role: message role (user, assistant, tool, system)
     * - content: plain text for simple messages, or JSON-serialized parts array for
     *   multimodal/structured messages
     * - finish_reason: per-message finish reason (output messages only)
     *
     * Serialization JSON Schema marks defaulted fields required. In the public OpenAPI
     * document this class appears only as an AgentSpanSchema message element. Ingest
     * validation is unchanged.
     */
    export interface OutputMessage {
      content: string;

      finish_reason: string;

      role: string;
    }
  }
}

/**
 * Response containing chart-ready agent span stats rows.
 */
export interface SpanStatsResponse {
  bucket_type: 'time' | 'number';

  columns: Array<SpanStatsResponse.Column>;

  end: string;

  granularity: number | null;

  rows: Array<{ [key: string]: (string & {}) | string | number | boolean | null }>;

  start: string;

  timezone: string;
}

export namespace SpanStatsResponse {
  /**
   * Metadata describing one column in an agent span stats result row.
   */
  export interface Column {
    aggregation: string | null;

    metric: string | null;

    name: string;

    role: 'time' | 'bucket' | 'group' | 'metric';

    value_type: 'datetime' | 'number' | 'boolean' | 'string';
  }
}

export interface SpanCustomAttrsSchemaParams {
  project_id: string;

  limit?: number;

  offset?: number;

  query?: SpanCustomAttrsSchemaParams.Query | null;

  started_after?: string | null;

  started_before?: string | null;
}

export namespace SpanCustomAttrsSchemaParams {
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

export interface SpanQueryParams {
  project_id: string;

  custom_attr_columns?: Array<SpanQueryParams.CustomAttrColumn>;

  group_by?: Array<SpanQueryParams.GroupBy> | null;

  group_distributions?: Array<SpanQueryParams.GroupDistribution>;

  group_filters?: Array<SpanQueryParams.GroupFilter>;

  include_costs?: boolean;

  include_details?: boolean;

  limit?: number;

  measures?: Array<SpanQueryParams.Measure>;

  offset?: number;

  query?: SpanQueryParams.Query | null;

  signal_filters?: SpanQueryParams.SignalFilters | null;

  sort_by?: Array<SpanQueryParams.SortBy> | null;

  started_after?: string | null;

  started_before?: string | null;
}

export namespace SpanQueryParams {
  /**
   * Reference to a span field or typed custom attribute map value.
   */
  export interface CustomAttrColumn {
    key: string;

    source?:
      | 'field'
      | 'derived'
      | 'custom_attrs_string'
      | 'custom_attrs_int'
      | 'custom_attrs_float'
      | 'custom_attrs_bool';
  }

  /**
   * Reference to a field or map-key that spans should be grouped by.
   *
   * `source="field"` targets a semantic span field (`agent.name`) or direct span
   * column (`agent_name`), allowlisted server-side. `source="column"` is accepted
   * for existing callers. The other sources target keys inside the typed custom
   * attribute Map columns, which accept arbitrary user-defined keys.
   */
  export interface GroupBy {
    key: string;

    alias?: string | null;

    source?:
      | 'field'
      | 'column'
      | 'custom_attrs_string'
      | 'custom_attrs_int'
      | 'custom_attrs_float'
      | 'custom_attrs_bool';
  }

  /**
   * One custom attribute distribution to compute per returned span group.
   */
  export interface GroupDistribution {
    alias: string;

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    value: GroupDistribution.Value;

    bins?: number;

    top_n?: number;
  }

  export namespace GroupDistribution {
    /**
     * Reference to a span field or typed custom attribute map value.
     */
    export interface Value {
      key: string;

      source?:
        | 'field'
        | 'derived'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

  /**
   * Range filter over one grouped span measure.
   */
  export interface GroupFilter {
    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    measure: GroupFilter.Measure;

    group_by?: Array<GroupFilter.GroupBy>;

    max?: number | string | null;

    min?: number | string | null;
  }

  export namespace GroupFilter {
    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    export interface Measure {
      aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'count_true' | 'count_false';

      alias: string;

      filter?: Measure.Filter | null;

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      value?: Measure.Value | null;

      value_type?: 'datetime' | 'number' | 'boolean' | 'string' | null;
    }

    export namespace Measure {
      export interface Filter {
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
          | Filter.LtOperation
          | Shared.GteOperation
          | Filter.LteOperation
          | Shared.InOperation
          | Shared.ContainsOperation;
      }

      export namespace Filter {
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

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      export interface Value {
        key: string;

        source?:
          | 'field'
          | 'derived'
          | 'custom_attrs_string'
          | 'custom_attrs_int'
          | 'custom_attrs_float'
          | 'custom_attrs_bool';
      }
    }

    /**
     * Reference to a field or map-key that spans should be grouped by.
     *
     * `source="field"` targets a semantic span field (`agent.name`) or direct span
     * column (`agent_name`), allowlisted server-side. `source="column"` is accepted
     * for existing callers. The other sources target keys inside the typed custom
     * attribute Map columns, which accept arbitrary user-defined keys.
     */
    export interface GroupBy {
      key: string;

      alias?: string | null;

      source?:
        | 'field'
        | 'column'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

  /**
   * One aggregate measure computed over spans in a group or bucket.
   */
  export interface Measure {
    aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'count_true' | 'count_false';

    alias: string;

    filter?: Measure.Filter | null;

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    value?: Measure.Value | null;

    value_type?: 'datetime' | 'number' | 'boolean' | 'string' | null;
  }

  export namespace Measure {
    export interface Filter {
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
        | Filter.LtOperation
        | Shared.GteOperation
        | Filter.LteOperation
        | Shared.InOperation
        | Shared.ContainsOperation;
    }

    export namespace Filter {
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

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    export interface Value {
      key: string;

      source?:
        | 'field'
        | 'derived'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

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

  export interface SignalFilters {
    ratings?: Array<SignalFilters.Rating>;

    tags?: Array<string>;
  }

  export namespace SignalFilters {
    export interface Rating {
      op: 'gte' | 'gt' | 'lte' | 'lt' | 'eq';

      scorer_key: string;

      value: number;
    }
  }

  /**
   * Sort specification for agent query endpoints.
   */
  export interface SortBy {
    field: string;

    direction?: 'asc' | 'desc';
  }
}

export interface SpanStatsParams {
  project_id: string;

  start: string;

  /**
   * Bucket stats rows by started_at time intervals.
   */
  bucket_by?:
    | SpanStatsParams.AgentSpanStatsTimeBucketSpec
    | SpanStatsParams.AgentSpanStatsNumericBucketSpec
    | null;

  end?: string | null;

  granularity?: number | null;

  group_by?: Array<SpanStatsParams.GroupBy>;

  group_filters?: Array<SpanStatsParams.GroupFilter>;

  group_limit?: number;

  metrics?: Array<SpanStatsParams.Metric>;

  query?: SpanStatsParams.Query | null;

  signal_filters?: SpanStatsParams.SignalFilters | null;

  timezone?: string;
}

export namespace SpanStatsParams {
  /**
   * Bucket stats rows by started_at time intervals.
   */
  export interface AgentSpanStatsTimeBucketSpec {
    type?: 'time';
  }

  /**
   * Bucket stats rows by ranges of one numeric span or grouped value.
   */
  export interface AgentSpanStatsNumericBucketSpec {
    alias?: string;

    bins?: number;

    group_by?: Array<AgentSpanStatsNumericBucketSpec.GroupBy>;

    max?: number | null;

    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    measure?: AgentSpanStatsNumericBucketSpec.Measure | null;

    min?: number | null;

    type?: 'number';

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    value?: AgentSpanStatsNumericBucketSpec.Value | null;
  }

  export namespace AgentSpanStatsNumericBucketSpec {
    /**
     * Reference to a field or map-key that spans should be grouped by.
     *
     * `source="field"` targets a semantic span field (`agent.name`) or direct span
     * column (`agent_name`), allowlisted server-side. `source="column"` is accepted
     * for existing callers. The other sources target keys inside the typed custom
     * attribute Map columns, which accept arbitrary user-defined keys.
     */
    export interface GroupBy {
      key: string;

      alias?: string | null;

      source?:
        | 'field'
        | 'column'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }

    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    export interface Measure {
      aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'count_true' | 'count_false';

      alias: string;

      filter?: Measure.Filter | null;

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      value?: Measure.Value | null;

      value_type?: 'datetime' | 'number' | 'boolean' | 'string' | null;
    }

    export namespace Measure {
      export interface Filter {
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
          | Filter.LtOperation
          | Shared.GteOperation
          | Filter.LteOperation
          | Shared.InOperation
          | Shared.ContainsOperation;
      }

      export namespace Filter {
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

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      export interface Value {
        key: string;

        source?:
          | 'field'
          | 'derived'
          | 'custom_attrs_string'
          | 'custom_attrs_int'
          | 'custom_attrs_float'
          | 'custom_attrs_bool';
      }
    }

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    export interface Value {
      key: string;

      source?:
        | 'field'
        | 'derived'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

  /**
   * Reference to a field or map-key that spans should be grouped by.
   *
   * `source="field"` targets a semantic span field (`agent.name`) or direct span
   * column (`agent_name`), allowlisted server-side. `source="column"` is accepted
   * for existing callers. The other sources target keys inside the typed custom
   * attribute Map columns, which accept arbitrary user-defined keys.
   */
  export interface GroupBy {
    key: string;

    alias?: string | null;

    source?:
      | 'field'
      | 'column'
      | 'custom_attrs_string'
      | 'custom_attrs_int'
      | 'custom_attrs_float'
      | 'custom_attrs_bool';
  }

  /**
   * Range filter over one grouped span measure.
   */
  export interface GroupFilter {
    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    measure: GroupFilter.Measure;

    group_by?: Array<GroupFilter.GroupBy>;

    max?: number | string | null;

    min?: number | string | null;
  }

  export namespace GroupFilter {
    /**
     * One aggregate measure computed over spans in a group or bucket.
     */
    export interface Measure {
      aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'count_true' | 'count_false';

      alias: string;

      filter?: Measure.Filter | null;

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      value?: Measure.Value | null;

      value_type?: 'datetime' | 'number' | 'boolean' | 'string' | null;
    }

    export namespace Measure {
      export interface Filter {
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
          | Filter.LtOperation
          | Shared.GteOperation
          | Filter.LteOperation
          | Shared.InOperation
          | Shared.ContainsOperation;
      }

      export namespace Filter {
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

      /**
       * Reference to a span field or typed custom attribute map value.
       */
      export interface Value {
        key: string;

        source?:
          | 'field'
          | 'derived'
          | 'custom_attrs_string'
          | 'custom_attrs_int'
          | 'custom_attrs_float'
          | 'custom_attrs_bool';
      }
    }

    /**
     * Reference to a field or map-key that spans should be grouped by.
     *
     * `source="field"` targets a semantic span field (`agent.name`) or direct span
     * column (`agent_name`), allowlisted server-side. `source="column"` is accepted
     * for existing callers. The other sources target keys inside the typed custom
     * attribute Map columns, which accept arbitrary user-defined keys.
     */
    export interface GroupBy {
      key: string;

      alias?: string | null;

      source?:
        | 'field'
        | 'column'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

  /**
   * Metric to extract from each matching span and aggregate into chart rows.
   */
  export interface Metric {
    alias: string;

    /**
     * Reference to a span field or typed custom attribute map value.
     */
    value: Metric.Value;

    value_type: 'datetime' | 'number' | 'boolean' | 'string';

    aggregations?: Array<
      'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'count_true' | 'count_false'
    >;

    percentiles?: Array<number>;
  }

  export namespace Metric {
    /**
     * Reference to a span field or typed custom attribute map value.
     */
    export interface Value {
      key: string;

      source?:
        | 'field'
        | 'derived'
        | 'custom_attrs_string'
        | 'custom_attrs_int'
        | 'custom_attrs_float'
        | 'custom_attrs_bool';
    }
  }

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

  export interface SignalFilters {
    ratings?: Array<SignalFilters.Rating>;

    tags?: Array<string>;
  }

  export namespace SignalFilters {
    export interface Rating {
      op: 'gte' | 'gt' | 'lte' | 'lt' | 'eq';

      scorer_key: string;

      value: number;
    }
  }
}

export declare namespace Spans {
  export {
    type SpanCustomAttrsSchemaResponse as SpanCustomAttrsSchemaResponse,
    type SpanQueryResponse as SpanQueryResponse,
    type SpanStatsResponse as SpanStatsResponse,
    type SpanCustomAttrsSchemaParams as SpanCustomAttrsSchemaParams,
    type SpanQueryParams as SpanQueryParams,
    type SpanStatsParams as SpanStatsParams,
  };
}
