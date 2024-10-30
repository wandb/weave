import {Query} from './traceServerClientInterface/query';
type ExtraKeysAllowed = {
  [key: string]: any;
};

type WeaveSummarySchema = {
  costs?: {[key: string]: LLMCostSchema};
  latency_ms?: number; // latency in milliseconds
} & ExtraKeysAllowed;

export type LLMUsageSchema = {
  // Should collapse prompt and input? Ideally yes, but
  // back compat is a concern.
  prompt_tokens?: number;
  input_tokens?: number;
  // Should collapse completion and output? Ideally yes, but
  // back compat is a concern.
  completion_tokens?: number;
  output_tokens?: number;
  requests?: number;
  total_tokens?: number;
} & ExtraKeysAllowed;

export type LLMCostSchema = LLMUsageSchema & {
  loading?: boolean;
  // Cost for request
  prompt_tokens_total_cost?: number;
  completion_tokens_total_cost?: number;

  // Cost per unit
  prompt_token_cost?: number;
  completion_token_cost?: number;
  prompt_token_cost_unit?: string;
  completion_token_cost_unit?: string;

  effective_date?: string;
  provider_id?: string;
  pricing_level?: string;
  pricing_level_id?: string;
  created_at?: string;
  created_by?: string;
};

type SummaryInsertMap = {
  usage?: {[key: string]: LLMUsageSchema};
} & ExtraKeysAllowed;

type SummaryMap = {
  weave?: WeaveSummarySchema;
} & SummaryInsertMap;

export type KeyedDictType = {
  [key: string]: any;
  _keys?: string[];
};
export type TraceCallSchema = {
  project_id: string;
  id: string;
  op_name: string;
  display_name?: string;
  trace_id: string;
  parent_id?: string;
  started_at: string;
  attributes: KeyedDictType;
  inputs: KeyedDictType;
  ended_at?: string;
  exception?: string;
  // Using `unknown` for `output` instead of an `any` so that the type checkers
  // force us to handle all possible types. When using `any`, this value can be
  // freely assigned to any other variable without any type checking. This way,
  // we can ensure that we handle all possible types.
  output?: unknown;
  summary?: SummaryMap;
  wb_run_id?: string;
  wb_user_id?: string;
};
export type TraceCallReadReq = {
  project_id: string;
  id: string;
  include_costs?: boolean;
};

export type TraceCallReadSuccess = {
  call: TraceCallSchema;
};
export type TraceCallReadError = {
  detail: string;
};
export type TraceCallReadRes = TraceCallReadSuccess | TraceCallReadError;
interface TraceCallsFilter {
  op_names?: string[];
  input_refs?: string[];
  output_refs?: string[];
  parent_ids?: string[];
  trace_ids?: string[];
  call_ids?: string[];
  trace_roots_only?: boolean;
  wb_run_ids?: string[];
  wb_user_ids?: string[];
}

export type SortBy = {field: string; direction: 'asc' | 'desc'};

export type TraceCallsQueryReq = {
  project_id: string;
  filter?: TraceCallsFilter;
  limit?: number;
  offset?: number;
  sort_by?: SortBy[];
  query?: Query;
  columns?: string[];
  expand_columns?: string[];
  include_costs?: boolean;
  include_feedback?: boolean;
};

export type TraceCallsQueryRes = {
  calls: TraceCallSchema[];
};

export type TraceCallsQueryStatsReq = {
  project_id: string;
  filter?: TraceCallsFilter;
  query?: Query;
};

export type TraceCallsQueryStatsRes = {
  count: number;
};

export type TraceCallsDeleteReq = {
  project_id: string;
  call_ids: string[];
};

export type TraceCallUpdateReq = {
  project_id: string;
  call_id: string;
  display_name: string;
};

export type FeedbackCreateReq = {
  project_id: string;
  weave_ref: string;
  feedback_type: string;
  payload: Record<string, any>;
};

export type FeedbackCreateSuccess = {
  id: string;
  created_at: string;
  wb_user_id: string;
  payload: Record<string, any>;
};
export type FeedbackCreateError = {
  detail: string;
};
export type FeedbackCreateRes = FeedbackCreateSuccess | FeedbackCreateError;

export type FeedbackQueryReq = {
  project_id: string;
  query?: Query;
  sort_by?: SortBy[];
};

export type Feedback = {
  id: string;
  weave_ref: string;
  wb_user_id: string; // authenticated creator username
  creator: string | null; // display name
  created_at: string;
  feedback_type: string;
  payload: Record<string, any>;
};

export type FeedbackQuerySuccess = {
  result: Feedback[];
};
export type FeedbackQueryError = {
  detail: string;
};
export type FeedbackQueryRes = FeedbackQuerySuccess | FeedbackQueryError;

export type FeedbackPurgeReq = {
  project_id: string;
  query: Query;
};
export type FeedbackPurgeSuccess = {};
export type FeedbackPurgeError = {
  detail: string;
};
export type FeedbackPurgeRes = FeedbackPurgeSuccess | FeedbackPurgeError;
interface TraceObjectsFilter {
  base_object_classes?: string[];
  object_ids?: string[];
  is_op?: boolean;
  latest_only?: boolean;
}
export type TraceObjQueryReq = {
  project_id: string;
  filter?: TraceObjectsFilter;
  limit?: number;
  offset?: number;
  sort_by?: SortBy[];
  metadata_only?: boolean;
};

export interface TraceObjSchema {
  project_id: string;
  object_id: string;
  created_at: string;
  digest: string;
  version_index: number;
  is_latest: number;
  kind: 'op' | 'object';
  base_object_class?: string;
  val: any;
}
export type TraceObjQueryRes = {
  objs: TraceObjSchema[];
};
export type TraceObjReadReq = {
  project_id: string;
  object_id: string;
  digest: string;
};

export type TraceObjReadRes = {
  obj: TraceObjSchema;
};

export type TraceRefsReadBatchReq = {
  refs: string[];
};

export type TraceRefsReadBatchRes = {
  vals: any[];
};

export type TraceTableQueryReq = {
  project_id: string;
  digest: string;
  filter?: {
    row_digests?: string[];
  };
  limit?: number;
  offset?: number;
  sort_by?: SortBy[];
};

export type TraceTableQueryStatsReq = {
  project_id: string;
  digest: string;
};

export type TraceTableQueryStatsRes = {
  count: number;
};

export type TraceTableQueryRes = {
  rows: Array<{
    digest: string;
    val: any;
  }>;
};

export type TraceFileContentReadReq = {
  project_id: string;
  digest: string;
};

export type TraceFileContentReadRes = {
  content: ArrayBuffer;
};

export enum ContentType {
  csv = 'text/csv',
  tsv = 'text/tab-separated-values',
  any = '*/*',
  jsonl = 'application/jsonl',
  json = 'application/json',
}

export const fileExtensions = {
  [ContentType.csv]: 'csv',
  [ContentType.tsv]: 'tsv',
  [ContentType.jsonl]: 'jsonl',
  [ContentType.any]: 'jsonl',
  [ContentType.json]: 'json',
};
