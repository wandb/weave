import {IconName} from '@wandb/weave/components/Icon';
import {FC} from 'react';

import {CompositionView, FlameGraphView} from './TraceViews';
import {FilterableTreeView} from './TraceViews/TreeView';
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
  /** Maximum number of traces this view can handle before being disabled */
  maxTraces?: number;
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
    component: FilterableTreeView,
  },
  {
    id: 'code',
    label: 'Code Composition',
    icon: 'code-alt',
    component: CompositionView,
  },
  {
    id: 'flamegraph',
    label: 'Flame',
    icon: 'chart-horizontal-bars',
    component: FlameGraphView,
    maxTraces: 500,
  },
];
