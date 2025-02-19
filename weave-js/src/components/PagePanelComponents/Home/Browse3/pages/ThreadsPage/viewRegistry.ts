import {FC} from 'react';

import {IconName} from '../../../../../Icon';
import {ThreadListView, ThreadTimelineView} from './components/ThreadViews';
import {
  TraceListView,
  TraceTableView,
  TraceTimelineView,
  TraceTreeView,
} from './components/TraceViews';
import {TraceTreeFlat} from './types';

export interface ThreadViewProps {
  onTraceSelect: (traceId: string) => void;
  traces: string[];
  loading: boolean;
  error: Error | null;
}

export interface TraceViewProps {
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}

export interface ViewDefinition<T> {
  id: string;
  label: string;
  icon: IconName;
  component: FC<T>;
}

export type ThreadViewRegistry = Array<ViewDefinition<ThreadViewProps>>;
export type TraceViewRegistry = Array<ViewDefinition<TraceViewProps>>;

export const threadViews: ThreadViewRegistry = [
  {
    id: 'list',
    label: 'List',
    icon: 'list',
    component: ThreadListView,
  },
  {
    id: 'timeline',
    label: 'Timeline',
    icon: 'chart-horizontal-bars',
    component: ThreadTimelineView,
  },
];

export const traceViews: TraceViewRegistry = [
  {
    id: 'list',
    label: 'List',
    icon: 'list',
    component: TraceListView,
  },
  {
    id: 'timeline',
    label: 'Timeline',
    icon: 'chart-horizontal-bars',
    component: TraceTimelineView,
  },
  {
    id: 'tree',
    label: 'Tree',
    icon: 'miller-columns',
    component: TraceTreeView,
  },
  {
    id: 'table',
    label: 'Table',
    icon: 'table',
    component: TraceTableView,
  },
];

export const getThreadView = (viewId: string) =>
  threadViews.find(view => view.id === viewId) ?? threadViews[0];

export const getTraceView = (viewId: string) =>
  traceViews.find(view => view.id === viewId) ?? traceViews[0];
