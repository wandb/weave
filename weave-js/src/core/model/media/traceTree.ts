type StatusCodeType = 'SUCCESS' | 'ERROR';
export type SpanKindType = 'LLM' | 'CHAIN' | 'AGENT' | 'TOOL';

type ResultType = {
  inputs?: {[key: string]: any};
  outputs?: {[key: string]: any};
};

// This maps to the weave1 trace_tree.Span ObjectType
export type SpanType = {
  trace_id?: string;
  span_id?: string;
  parent_id?: string;
  name?: string;
  _name?: string; // need in Weave1 where we can't use name because of collision
  start_time_ms?: number;
  end_time_ms?: number;
  status_code?: StatusCodeType;
  status_message?: string;
  attributes?: {[key: string]: any};
  // results is not standard and not representation by OpenTelemetry
  results?: ResultType[];
  child_spans?: SpanType[];
  span_kind?: SpanKindType;
  _span_index?: number; // special field to unmap the span
};

// Flat representation of a span, this is a TypedDict
export interface FlatSpan {
  name: string;
  start_time_ms: number;
  end_time_ms?: number;
  attributes: any;
  trace_id: string;
  span_id: string;
  parent_id?: string;
}

export type WBTraceTree = {
  _type: 'wb_trace_tree';
  root_span_dumps: string; // SpanType
  model_hash?: string;
  model_dict_dumps?: string; // {[key: string]: any};
};
