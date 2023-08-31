import * as _ from 'lodash';
import {FlatSpan, SpanType} from '@wandb/weave/core/model/media/traceTree';

export const flatToTrees = (flat: FlatSpan[]): SpanType[] => {
  const roots: SpanType[] = [];
  const unrooted: SpanType[] = [];
  const map: {[id: string]: SpanType} = {};
  flat.forEach((span, index) => {
    map[span.span_id] = {
      name: span.name,
      start_time_ms: span.start_time_ms,
      end_time_ms: span.end_time_ms,
      attributes: span.attributes,
      child_spans: [],
      '_span_index': index,
    };
  });
  flat.forEach(span => {
    // We use '' as the parent_id for root spans for now, reading null columns
    // is currently broken for StreamTable liveset.
    if (span.parent_id === '' || span.parent_id == null) {
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

export const unifyRoots = (roots: SpanType[]): SpanType => {
  if (roots.length === 1) {
    return roots[0];
  }
  const traceStartTime = _.min(roots.map(r => r.start_time_ms ?? 0)) ?? 0;
  const traceEndTime =
    _.max(roots.map(r => r.end_time_ms ?? r.start_time_ms ?? 0)) ??
    traceStartTime + 1;
  return {
    name: 'root',
    start_time_ms: traceStartTime,
    end_time_ms: traceEndTime,
    child_spans: roots,
  };
};
