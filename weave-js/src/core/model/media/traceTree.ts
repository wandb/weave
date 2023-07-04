type StatusCodeType = 'SUCCESS' | 'ERROR';
export type SpanKindType = 'LLM' | 'CHAIN' | 'AGENT' | 'TOOL';

type ResultType = {
  inputs?: {[key: string]: any};
  outputs?: {[key: string]: any};
};

export type SpanType = {
  span_id?: string;
  name?: string;
  _name?: string; // need in Weave1 where we can't use name because of collision
  start_time_ms?: number;
  end_time_ms?: number;
  status_code?: StatusCodeType;
  status_message?: string;
  attributes?: {[key: string]: any};
  results?: ResultType[];
  child_spans?: SpanType[];
  span_kind?: SpanKindType;
};

export type WBTraceTree = {
  _type: 'wb_trace_tree';
  root_span_dumps: string; // SpanType
  model_hash?: string;
  model_dict_dumps?: string; // {[key: string]: any};
};
