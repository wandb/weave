import {FC} from 'react';

import {IconName} from '../../../../../Icon';
import {ThreadListView, ThreadTimelineView} from './components/ThreadViews';
import {FlameGraphView, TreeView} from './components/TraceViews';
import {ThreadViewProps, TraceViewProps} from './types';

/**
 * Definition for a view component and its metadata
 */
export interface ViewDefinition<T> {
  /** Unique identifier for the view */
  id: string;
  /** Display label for the view */
  label: string;
  /** Icon to show in the view selector */
  icon: IconName;
  /** The React component that implements the view */
  component: FC<T>;
}

/** Registry of available thread views */
export type ThreadViewRegistry = Array<ViewDefinition<ThreadViewProps>>;
/** Registry of available trace views */
export type TraceViewRegistry = Array<ViewDefinition<TraceViewProps>>;

/** Available thread visualization views */
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

/** Available trace visualization views */
export const traceViews: TraceViewRegistry = [
  {
    id: 'tree',
    label: 'Tree',
    icon: 'layout-tabs',
    component: TreeView,
  },
  {
    id: 'flamegraph',
    label: 'Flame Graph',
    icon: 'chart-horizontal-bars',
    component: FlameGraphView,
  },
];

/**
 * Get a thread view by ID, falling back to the first view if not found
 */
export const getThreadView = (viewId: string) =>
  threadViews.find(view => view.id === viewId) ?? threadViews[0];

/**
 * Get a trace view by ID, falling back to the first view if not found
 */
export const getTraceView = (viewId: string) =>
  traceViews.find(view => view.id === viewId) ?? traceViews[0];
