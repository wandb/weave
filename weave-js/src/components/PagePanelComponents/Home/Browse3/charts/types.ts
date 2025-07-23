/**
 * types.ts
 *
 * This file contains all common type definitions for chart components and helpers.
 */
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';

import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';

/**
 * Structured feedback data that's easier to work with than the raw API format.
 * Parsed once during extraction to avoid repeated parsing.
 */
export type ProcessedFeedback = {
  /** Annotation values keyed by annotation type (e.g., { Quality: 8.5, Relevance: 0.8 }) */
  annotations: {[key: string]: unknown};
  /** Scorer values keyed by scorer name (e.g., { toxicity: 0.2, coherence: 0.9 }) */
  scorers: {[key: string]: unknown};
  /** Array of note strings */
  notes: string[];
  /** Array of reaction emojis */
  reactions: string[];
};

export type ExtractedCallData = {
  callId: string;
  traceId: string;
  started_at: string;
  ended_at?: string;
  latency?: number;
  exception?: number;
  op_name?: string;
  display_name?: string;
  cost?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  prompt_cost?: number;
  completion_cost?: number;
  // Raw inputs and outputs for accessing input/output field values
  inputs?: {[key: string]: unknown};
  output?: {[key: string]: unknown};
  /** Structured feedback data for easy access */
  feedback?: ProcessedFeedback;
};

export type ChartAxisField = {
  key: string;
  label: string;
  type: 'number' | 'string' | 'date' | 'boolean';
  units?: string;
  render?: (value: unknown) => string;
};

export type DataPoint = {
  x: number;
  y: number;
  group?: string;
  [key: string]: unknown;
};

export type BinnedPoint = {
  x: number;
  y: number;
  originalValue: number;
  binStart?: number;
  binEnd?: number;
};

// =============================================================================
// Schema Types (for input/output field extraction)
// =============================================================================

export type FieldType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'object'
  | 'array'
  | 'null'
  | 'undefined';

export type FieldSchema = {
  key: string;
  types: Set<FieldType>;
  label: string;
  source: 'input' | 'output' | 'annotations' | 'scores' | 'reactions';
  fullPath: string; // For nested objects, e.g., "input.message", "output.response.text"
};

export type DynamicFields = {
  inputFields: Map<string, FieldSchema>;
  outputFields: Map<string, FieldSchema>;
  annotationFields: Map<string, FieldSchema>;
  scoreFields: Map<string, FieldSchema>;
  reactionFields: Map<string, FieldSchema>;
};

// =============================================================================
// Chart Configuration Types
// =============================================================================

export type AggregationMethod =
  | 'average'
  | 'sum'
  | 'min'
  | 'max'
  | 'p95'
  | 'p99';

export type ChartConfig = {
  id: string;
  xAxis: string;
  yAxis: string;
  plotType?: 'scatter' | 'line' | 'bar';
  binCount?: number; // For line plots and bar charts
  aggregation?: AggregationMethod; // For line plots and bar charts
  groupKeys?: string[]; // For grouping by multiple keys (op_name and user-selected fields)
  customName?: string; // For custom chart names
};

export type ChartsState = {
  charts: ChartConfig[];
  openDrawerChartId: string | null;
};

export type ChartsAction =
  | {type: 'SET_CHARTS'; payload: ChartConfig[]}
  | {type: 'ADD_CHART'; payload?: Partial<ChartConfig>}
  | {type: 'REMOVE_CHART'; id: string}
  | {type: 'UPDATE_CHART'; id: string; payload: Partial<ChartConfig>}
  | {type: 'OPEN_DRAWER'; id: string}
  | {type: 'CLOSE_DRAWER'};

export type UseChartsDataParams = {
  entity: string;
  project: string;
  filter: WFHighLevelCallFilter;
  filterModelProp: GridFilterModel;
  pageSize?: number;
  sortModel?: GridSortModel;
};

export type UseChartsDataResult = {
  data: ExtractedCallData[];
  isLoading: boolean;
  error?: unknown;
  refetch?: () => void;
};
