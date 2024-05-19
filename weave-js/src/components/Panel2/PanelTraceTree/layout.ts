// Lays out a trace
//
// We compute the y level of a span so that contiguous spans are on the same
// level. If there is parallelism within a span, we will render the parallel
// spans on different levels, accounting for the height of the parallel spans'
// children.

import {SpanType} from '@wandb/weave/core/model/media/traceTree';
import * as _ from 'lodash';

export type LayedOutSpanType = SpanType & {
  // x position and width in fraction of total width
  xStartFrac: number;
  xWidthFrac: number;

  // y position and height in number of levels
  yLevel: number;
  yHeight: number;

  child_spans?: LayedOutSpanType[] | undefined;
};

export type LayedOutSpanWithParentYLevel = LayedOutSpanType & {
  parentYLevel: number;
};

function layoutSpan(
  s: SpanType,
  xUnitOffset: number,
  xTotalWidth: number
): LayedOutSpanType {
  const startTime = s.start_time_ms ?? 0;
  const endTime = s.end_time_ms ?? startTime + 1;
  const childSpans = s.child_spans ?? [];
  if (childSpans.length === 0) {
    return {
      ...s,
      xStartFrac: (startTime + xUnitOffset) / xTotalWidth,
      xWidthFrac: (endTime - startTime) / xTotalWidth,
      yLevel: 0,
      yHeight: 1,
      child_spans: undefined,
    };
  }
  // level is the offset within parent
  let level = 0;
  let lastStartTime = Number.MAX_VALUE;
  let lastHeight = 1;
  const sortedChildSpans = _.sortBy(childSpans, cs => {
    return cs.start_time_ms ?? 0;
  });
  // walk backwards ordered by start time
  const childSpansLayout = sortedChildSpans.reverse().map(childSpan => {
    const childSpanLayout = layoutSpan(childSpan, xUnitOffset, xTotalWidth);
    const childSpanStartTime = childSpanLayout.start_time_ms ?? 0;
    const childSpanEndTime =
      childSpanLayout.end_time_ms ?? childSpanStartTime + 1;
    if (childSpanEndTime > lastStartTime) {
      level += lastHeight;
    } else {
      level = 0;
    }
    lastStartTime = childSpanStartTime;
    lastHeight = childSpanLayout.yHeight;
    return {
      ...childSpanLayout,
      xUnit: (childSpanStartTime + xUnitOffset) / xTotalWidth,
      xUnitWidth: (childSpanEndTime - childSpanStartTime) / xTotalWidth,
      yLevel: level,
    };
  });

  const yHeight =
    (_.max(childSpansLayout.map(childSpanLayout => childSpanLayout.yHeight)) ??
      1) + 1;

  return {
    ...s,
    xStartFrac: (startTime + xUnitOffset) / xTotalWidth,
    xWidthFrac: (endTime - startTime) / xTotalWidth,
    yLevel: 0,
    yHeight,
    child_spans: childSpansLayout,
  };
}

function makeYAbsolute(
  s: LayedOutSpanType,
  level: number = 0
): LayedOutSpanWithParentYLevel {
  return {
    ...s,
    parentYLevel: level - 1,
    yLevel: s.yLevel + level,
    child_spans: s.child_spans?.map(childSpan =>
      makeYAbsolute(childSpan as any, s.yLevel + level + 1)
    ),
  };
}

export function layoutTree(root: SpanType): LayedOutSpanWithParentYLevel {
  const traceStartTime = root.start_time_ms ?? 0;
  const traceEndTime = root.end_time_ms ?? traceStartTime + 1;
  const layedOutWithYOffsets = layoutSpan(
    root,
    -traceStartTime,
    traceEndTime - traceStartTime
  );
  return makeYAbsolute(layedOutWithYOffsets);
}

export function layoutTrees(roots: SpanType[]): LayedOutSpanWithParentYLevel {
  const traceStartTime = _.min(roots.map(r => r.start_time_ms ?? 0)) ?? 0;
  const traceEndTime =
    _.max(roots.map(r => r.end_time_ms ?? r.start_time_ms ?? 0)) ??
    traceStartTime + 1;
  const root = {
    name: 'root',
    start_time_ms: traceStartTime,
    end_time_ms: traceEndTime,
    child_spans: roots,
  };
  return layoutTree(root);
}
