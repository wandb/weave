import {Layout, ScatterData} from 'plotly.js';

// Base type for all chart data points
export type TimestampPoint = {
  started_at: string | number | Date;
};

// Chart data types
export type ChartDataLatency = TimestampPoint & {
  latency: number;
};

export type ChartDataErrors = TimestampPoint & {
  isError: boolean;
};

export type ChartDataRequests = TimestampPoint;

export type ChartDataUsage = TimestampPoint & {
  usage?: number;
  tokens?: number;
  total_tokens?: number;
};

// Processed data point for internal use
export type ChartDataPoint = {
  x: Date | number;
  y: number;
  isTimeX: boolean;
  binSize?: number;
  numCalls?: number;
};

// Units for chart data
export type ChartUnits = 'tokens' | 'ms' | '$' | string;

// Chart configuration
export type ChartConfig = {
  id: string;
  xAxis: string;
  yAxis: string;
  plotType: string;
  height: number;
  units?: ChartUnits;
  xDomain?: any[];
  yDomain?: any[];
  title?: string;
  minBins?: number;
  aggregation?: 'sum' | 'avg' | 'count' | 'min' | 'max';
  xMin?: string | number;
  xMax?: string | number;
  yMin?: number;
  yMax?: number;
  intervalMinutes?: number;
  // Layout for react-grid-layout
  x?: number;
  y?: number;
  w?: number;
  h?: number;
};

// Y-axis information
export type YAxisInfo = {
  isTokenData: boolean;
  title: string;
  units?: string;
};

// Chart component props
export interface BaseChartProps {
  height: number;
  xDomain?: any[];
  yDomain?: any[];
}

// Chart trace generator type
export type TraceGenerator = (
  processedData: ChartDataPoint[]
) => Partial<ScatterData>;

// Layout generator type
export type LayoutGenerator = (
  baseLayout: Partial<Layout>,
  processedData: ChartDataPoint[]
) => Partial<Layout>;
