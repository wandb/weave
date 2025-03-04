import {IconName} from '@wandb/weave/components/Icon';
import {FC} from 'react';

import {CodeView, FlameGraphView, GraphView, TreeView} from './TraceViews';
import {TraceViewProps} from './TraceViews/types';

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

/**
 * Get a trace view by ID, falling back to the first view if not found
 */
export const getTraceView = (viewId: string) =>
  traceViews.find(view => view.id === viewId) ?? traceViews[0];
/** Registry of available trace views */
export type TraceViewRegistry = Array<ViewDefinition<TraceViewProps>>;

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
