import {FC} from 'react';

import {IconName} from '../../../../../Icon';
import {DetailsView} from './components/CallViews/DetailsView';
import {CallJsonView} from './components/CallViews/JsonView';
import {ConnectedThreadView, StaticThreadView} from './components/ThreadViews';
import {FlameGraphView, GraphView, TreeView} from './components/TraceViews';
import {CodeView} from './components/TraceViews/CodeView';
import {CallViewProps, ThreadViewProps, TraceViewProps} from './types';

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
  /** Whether to show the scrubber for this view */
  showScrubber?: boolean;
}

/** Registry of available thread views */
export type ThreadViewRegistry = Array<ViewDefinition<ThreadViewProps>>;
/** Registry of available trace views */
export type TraceViewRegistry = Array<ViewDefinition<TraceViewProps>>;
/** Registry of available call views */
export type CallViewRegistry = Array<ViewDefinition<CallViewProps>>;

/** Available thread visualization views */
export const threadViews: ThreadViewRegistry = [
  {
    id: 'static',
    label: 'History',
    icon: 'history',
    component: StaticThreadView,
  },
  {
    id: 'connected',
    label: 'Connected',
    icon: 'forum-chat-bubble',
    component: ConnectedThreadView,
  },
];

/** Available trace visualization views */
export const traceViews: TraceViewRegistry = [
  {
    id: 'tree',
    label: 'Tree',
    icon: 'layout-tabs',
    component: TreeView,
    showScrubber: true,
  },
  {
    id: 'code',
    label: 'Code',
    icon: 'code-alt',
    component: CodeView,
    showScrubber: false,
  },
  {
    id: 'flamegraph',
    label: 'Flame Graph',
    icon: 'chart-horizontal-bars',
    component: FlameGraphView,
    showScrubber: true,
  },
  {
    id: 'graph',
    label: 'Graph',
    icon: 'chart-scatterplot',
    component: GraphView,
    showScrubber: true,
  },
];

/** Available call visualization views */
export const callViews: CallViewRegistry = [
  {
    id: 'details',
    label: 'Details',
    icon: 'list-bullets',
    component: DetailsView,
  },
  {
    id: 'json',
    label: 'JSON',
    icon: 'code-alt',
    component: CallJsonView,
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

/**
 * Get a call view by ID, falling back to the first view if not found
 */
export const getCallView = (viewId: string) =>
  callViews.find(view => view.id === viewId) ?? callViews[0];
