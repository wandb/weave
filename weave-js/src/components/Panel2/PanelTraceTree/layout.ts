// Lays out a trace
//
// We compute the y level of a span so that contiguous spans are on the same
// level. If there is parallelism within a span, we will render the parallel
// spans on different levels, accounting for the height of the parallel spans'
// children.

import * as _ from 'lodash';
import {SpanType} from '@wandb/weave/core/model/media/traceTree';

export type LayedOutSpanType = SpanType & {
  // x position and width in fraction of total width
  xStartFrac: number;
  xWidthFrac: number;

  // y position and height in number of levels
  yLevel: number;
  yHeight: number;

  child_spans?: LayedOutSpanType[] | undefined;
};

function layoutSpan(
  s: SpanType,
  xUnitOffset: number,
  xTotalWidth: number,
  parentYLevel: number
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
  let level = 0;
  let lastEndTime = -1;
  let lastHeight = 1;
  const childSpansLayout = childSpans.map((childSpan, i) => {
    const childSpanLayout = layoutSpan(
      childSpan,
      xUnitOffset,
      xTotalWidth,
      parentYLevel + 1
    );
    const childSpanStartTime = childSpanLayout.start_time_ms ?? lastEndTime + 1;
    const childSpanEndTime =
      childSpanLayout.end_time_ms ?? childSpanStartTime + 1;
    if (childSpanStartTime < lastEndTime) {
      level += lastHeight;
    } else {
      level = 0;
    }
    lastEndTime = childSpanEndTime;
    lastHeight = childSpanLayout.yHeight;
    return {
      ...childSpanLayout,
      xUnit: (childSpanStartTime + xUnitOffset) / xTotalWidth,
      xUnitWidth: (childSpanEndTime - childSpanStartTime) / xTotalWidth,
      yLevel: level + parentYLevel,
    };
  });

  const yHeight =
    (_.max(
      childSpansLayout.map(
        childSpanLayout => childSpanLayout.yLevel + childSpanLayout.yHeight
      )
    ) ?? 1) + 1;

  return {
    ...s,
    xStartFrac: (startTime + xUnitOffset) / xTotalWidth,
    xWidthFrac: (endTime - startTime) / xTotalWidth,
    yLevel: 0,
    yHeight,
    child_spans: childSpansLayout,
  };
}

export function layoutTree(root: SpanType): LayedOutSpanType {
  const traceStartTime = root.start_time_ms ?? 0;
  const traceEndTime = root.end_time_ms ?? traceStartTime + 1;
  return layoutSpan(root, -traceStartTime, traceEndTime - traceStartTime, 1);
}
