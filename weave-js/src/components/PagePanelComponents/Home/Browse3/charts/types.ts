/**
 * Shared types for the charts system.
 * This file contains type definitions that are used across multiple chart helper files
 * to avoid circular dependencies and keep helper files independent.
 */

// Chart axis field definition
export type ChartAxisField = {
  key: string;
  label: string;
  type: 'number' | 'string' | 'date' | 'boolean';
  units?: string;
  render?: (value: any) => string;
};

// Basic data point for chart visualization
export type DataPoint = {
  x: number;
  y: number;
  group?: string;
  [key: string]: any;
};

// Binned data point used in aggregation
export type BinnedPoint = {
  x: number;
  y: number;
  originalValue: number;
};

// Aggregation methods for line and bar charts
export type AggregationMethod =
  | 'average'
  | 'sum'
  | 'min'
  | 'max'
  | 'p95'
  | 'p99';

// Extracted call data structure
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
  prediction_index?: number;
  // Raw inputs and outputs for accessing input/output field values
  inputs?: {[key: string]: any};
  output?: {[key: string]: any};
};

// Field type enumeration for schema extraction
export type FieldType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'object'
  | 'array'
  | 'null'
  | 'undefined';

// Field schema for input/output field extraction
export type FieldSchema = {
  key: string;
  types: Set<FieldType>;
  label: string;
  source: 'input' | 'output';
  fullPath: string; // For nested objects, e.g., "input.message", "output.response.text"
};

// Input/output schema container
export type InputOutputSchema = {
  inputFields: Map<string, FieldSchema>;
  outputFields: Map<string, FieldSchema>;
};

// Chart configuration type
export type ChartConfig = {
  id: string;
  xAxis: string;
  yAxis: string;
  plotType?: 'scatter' | 'line' | 'bar';
  binCount?: number; // For line plots and bar charts
  aggregation?: AggregationMethod; // For line plots and bar charts
  xDomain?: [number, number]; // Refined x domain from painting
  yDomain?: [number, number]; // Refined y domain from painting
  colorGroupKey?: string; // For color grouping by input/output fields (scatter plots and line plots)
};

// Page context type
export type PageType = 'traces' | 'evaluations' | 'unknown';

// Chart styling types
export type ChartMargins = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type AxisPadding = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type ChartDimensions = {
  width: number;
  height: number;
};

// Processed chart point (extends DataPoint with additional metadata)
export type ProcessedChartPoint = DataPoint & {
  display_name: string;
  callId?: string;
  traceId?: string;
  group?: string;
  color?: string;
};

// Data ranges for chart domains
export type DataRanges = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};
