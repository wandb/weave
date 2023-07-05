import {SpanType} from '@wandb/weave/core/model/media/traceTree';

export interface Span {
  name: string;
  start_time_ns: number;
  duration_ns: number;
  attributes: any;
  trace_id: string;
  span_id: string;
  parent_id: string;
}

export const flatToTrees = (flat: Span[]): SpanType[] => {
  const roots: SpanType[] = [];
  const unrooted: SpanType[] = [];
  const map: {[id: string]: SpanType} = {};
  flat.forEach(span => {
    map[span.span_id] = {
      name: span.name,
      start_time_ms: span.start_time_ns / 1000000,
      end_time_ms: (span.start_time_ns + span.duration_ns) / 1000000,
      attributes: span.attributes,
      child_spans: [],
    };
  });
  flat.forEach(span => {
    // TODO: None cause we string encoded it...
    if (span.parent_id === 'None') {
      roots.push(map[span.span_id]);
    } else if (map[span.parent_id] == null) {
      unrooted.push(map[span.span_id]);
    } else {
      map[span.parent_id].child_spans?.push(map[span.span_id]);
    }
  });
  return roots;
};

export const treesToFlat = <S extends SpanType>(trees: S[]): S[] => {
  const flat: S[] = trees;
  let i = 0;
  while (i < flat.length) {
    const span = flat[i];
    if (span.child_spans?.length) {
      flat.splice(i + 1, 0, ...(span.child_spans as any));
    }
    i++;
  }
  return flat;
};
