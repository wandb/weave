import * as _ from 'lodash';

import {Type} from '../../../core';
import {FlatSpan, SpanType} from '../../../core/model/media/traceTree';

export const SpanWeaveType = {
  type: 'typedDict' as const,
  propertyTypes: {
    trace_id: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
    span_id: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
    parent_id: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
    name: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
    start_time_s: {
      type: 'union' as const,
      members: ['number' as const, 'none' as const],
    },
    end_time_s: {
      type: 'union' as const,
      members: ['number' as const, 'none' as const],
    },
    attributes: {
      type: 'union' as const,
      members: [
        {type: 'typedDict' as const, propertyTypes: {}},
        'none' as const,
      ],
    },
    summary: {
      type: 'union' as const,
      members: [
        {type: 'typedDict' as const, propertyTypes: {}},
        'none' as const,
      ],
    },
    inputs: {
      type: 'union' as const,
      members: [
        {type: 'typedDict' as const, propertyTypes: {}},
        'none' as const,
      ],
    },
    output: 'any' as const,
    status_code: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
    exception: {
      type: 'union' as const,
      members: ['string' as const, 'none' as const],
    },
  },
  notRequiredKeys: [
    'status_code',
    'inputs',
    'output',
    'exception',
    'attributes',
    'summary',
    'parent_id',
  ],
};
export const SpanWeaveWithTimestampType: Type = {
  type: 'typedDict' as const,
  propertyTypes: {
    ...SpanWeaveType.propertyTypes,
    timestamp: {
      type: 'union' as const,
      members: [
        {
          type: 'timestamp',
        },
        'none' as const,
      ],
    },
  },
};

export const flatToTrees = (flat: FlatSpan[]): SpanType[] => {
  const roots: SpanType[] = [];
  const unrooted: SpanType[] = [];
  const map: {[id: string]: SpanType} = {};
  flat.forEach((span, index) => {
    map[span.span_id] = {
      ...span,
      name: span.name,
      start_time_ms: span.start_time_ms,
      end_time_ms: span.end_time_ms,
      attributes: span.attributes,
      child_spans: [],
      _span_index: index,
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
