// Match the type from the chart components
import {
  ChartAxisField,
  ExtractedCallData,
  getOpNameDisplay,
} from './extractData';

// Use the shared ChartAxisField type
export type AxisFieldType = ChartAxisField;

// Define aggregation method type
export type AggregationMethod =
  | 'average'
  | 'sum'
  | 'min'
  | 'max'
  | 'p95'
  | 'p99';

// Type for data points
export type DataPoint = {
  x: number;
  y: number;
  group?: string;
  [key: string]: any;
};

// Type for binned data
export type BinnedPoint = {
  x: number;
  y: number;
  originalValue: number;
};

// Common constants
export const CHIP_HEIGHT = 18;

// Common color palette for chart grouping
export const COLOR_PALETTE = [
  '#0088FE',
  '#00C49F',
  '#FFBB28',
  '#FF8042',
  '#A28EFF',
  '#FF6699',
  '#33CC99',
  '#FF6666',
  '#FFB347',
  '#B6D7A8',
  '#F44336',
  '#2196F3',
  '#9C27B0',
  '#FF9800',
  '#607D8B',
  '#E91E63',
  '#00BCD4',
  '#795548',
  '#9E9E9E',
  '#673AB7',
  '#4CAF50',
  '#FF5722',
  '#009688',
];

// Common chart styles
export const chartContainerStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  height: '100%',
  width: '100%',
  minHeight: 0,
  flex: 1,
};

export const chartLegendStyle = {
  maxHeight: CHIP_HEIGHT * 2 + 12, // Two rows + padding
  marginBottom: 8,
  overflow: 'hidden',
  paddingRight: 10,
  flex: '0 0 auto' as const,
};

export const chartContentStyle = {
  flex: 1,
  minHeight: 0,
  display: 'flex' as const,
  flexDirection: 'column' as const,
  width: '100%',
  position: 'relative' as const,
  justifyContent: 'center' as const,
  alignItems: 'center' as const,
};

export const chartTooltipStyle = {
  cursor: {
    stroke: '#999',
    strokeWidth: 1,
    strokeDasharray: '5 5',
  },
  isAnimationActive: false,
};

// Common tooltip styles
export const tooltipContainerStyle = {
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  border: '1px solid #ddd',
  borderRadius: '3px',
  padding: '2px 4px',
  fontSize: '11px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
};

export const tooltipHeaderStyle = {
  color: '#666',
  fontWeight: 500,
  marginBottom: '1px',
};

export const tooltipRowStyle = {
  color: '#333',
  display: 'flex',
  justifyContent: 'space-between',
  gap: '4px',
  lineHeight: '1.2',
};

// Common tooltip date formatter
export const formatTooltipDate = (value: number) => {
  const date = new Date(value);
  if (isNaN(date.getTime())) {
    return formatTooltipValue(value);
  }

  // If the date is today, only show time
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  // If the date is this year, don't show year
  if (date.getFullYear() === today.getFullYear()) {
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // Otherwise show full date
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// Common tooltip value formatter with units
export const formatTooltipValue = (value: any, unit?: string) => {
  if (typeof value !== 'number' || isNaN(value)) {
    return String(value);
  }

  // Use scientific notation for very large or very small numbers
  if (
    Math.abs(value) >= 1e6 ||
    (Math.abs(value) > 0 && Math.abs(value) < 1e-3)
  ) {
    return `${value.toExponential(2)}${unit ? ` ${unit}` : ''}`;
  }

  // For medium-sized numbers, limit decimal places
  const valueStr =
    Math.abs(value) >= 1000
      ? value.toFixed(0) // No decimals for large numbers
      : value.toFixed(3); // 3 decimal places for smaller numbers

  // If still too long, truncate further
  if (valueStr.length > 7) {
    return `${value.toPrecision(3)}${unit ? ` ${unit}` : ''}`;
  }

  return `${valueStr}${unit ? ` ${unit}` : ''}`;
};

// Common utility for getting group values from data
export const getGroupValues = (
  data: ExtractedCallData[],
  groupBy?: string
): string[] => {
  if (!groupBy) return [];
  const opNames = Array.from(
    new Set(
      data
        .map(d =>
          getOpNameDisplay(d[groupBy as keyof ExtractedCallData] as string)
        )
        .filter(Boolean)
    )
  );
  return opNames;
};

// Get a consistent color for a group based on the group name
export const getGroupColor = (group: string, groupValues: string[]): string => {
  const idx = groupValues.indexOf(group);
  return COLOR_PALETTE[idx % COLOR_PALETTE.length];
};

/**
 * Format tick values for numeric displays (adds K, M suffixes)
 */
export const formatNumericTick = (value: number): string => {
  if (
    Math.abs(value) >= 1e6 ||
    (Math.abs(value) > 0 && Math.abs(value) < 1e-3)
  ) {
    return value.toExponential(2);
  }
  if (Math.abs(value) >= 1e3) return (value / 1e3).toFixed(1) + 'K';
  if (typeof value === 'number') {
    return value.toString();
  }
  return value;
};

/**
 * Format date values for axis display
 */
export const formatDateTick = (value: number): string => {
  const date = new Date(value);
  return isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
};

// Common axis tick formatter with units
export const formatAxisTick = (value: any, field?: AxisFieldType): string => {
  if (field?.type === 'date') {
    return formatDateTick(value);
  }
  if (typeof value === 'number') {
    return `${formatNumericTick(value)}${
      field?.units ? ` ${field.units}` : ''
    }`;
  }
  return String(value).length > 8
    ? String(value).slice(0, 7) + '…'
    : String(value);
};

/**
 * Generates domain configuration for chart axes
 */
export const getAxisDomain = (): ['auto', 'auto'] => ['auto', 'auto'];

// Helper function for data processing and binning
export const aggregateValues = (
  values: number[],
  method: AggregationMethod = 'average'
): number => {
  if (values.length === 0) return NaN;
  switch (method) {
    case 'sum':
      return values.reduce((a, b) => a + b, 0);
    case 'min':
      return Math.min(...values);
    case 'max':
      return Math.max(...values);
    case 'p95': {
      const sorted = [...values].sort((a, b) => a - b);
      const idx = Math.floor(0.95 * (sorted.length - 1));
      return sorted[idx];
    }
    case 'p99': {
      const sorted = [...values].sort((a, b) => a - b);
      const idx = Math.floor(0.99 * (sorted.length - 1));
      return sorted[idx];
    }
    case 'average':
    default:
      return values.reduce((a, b) => a + b, 0) / values.length;
  }
};

/**
 * Bins data points for chart display, with optional grouping
 *
 * @param points Array of data points with x and y values
 * @param binCount Number of bins to create
 * @param aggregation Method to aggregate y values within each bin
 * @param useGroups Whether to bin by group
 * @returns Object with grouped binned points
 */
export const binDataPoints = (
  points: DataPoint[],
  binCount: number = 20,
  aggregation: AggregationMethod = 'average',
  useGroups: boolean = false
): Record<string, BinnedPoint[]> => {
  // If no binning requested or no points
  if (!binCount || binCount < 1 || points.length === 0) {
    if (!useGroups) {
      return {
        all: points.map(pt => ({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        })),
      };
    } else {
      // Group without binning
      const grouped: Record<string, BinnedPoint[]> = {};
      points.forEach(pt => {
        const group = pt.group || 'Other';
        if (!grouped[group]) grouped[group] = [];
        grouped[group].push({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        });
      });
      return grouped;
    }
  }

  if (!useGroups) {
    // No grouping, bin as before
    const xVals = points.map(pt => pt.x);
    if (xVals.length === 0) {
      return {
        all: points.map(pt => ({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        })),
      };
    }

    const xMin = Math.min(...xVals);
    const xMax = Math.max(...xVals);

    if (xMax === xMin) {
      return {
        all: points.map(pt => ({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        })),
      };
    }

    const binSize = (xMax - xMin) / binCount;
    // Create the specified number of bins
    const bins: {x: number; yVals: number[]; originalValues: number[]}[] =
      Array.from({length: binCount}, (_, i) => ({
        x: xMin + binSize * (i + 0.5),
        yVals: [],
        originalValues: [],
      }));

    // Assign points to bins
    points.forEach(pt => {
      const binIndex = Math.min(
        Math.floor((pt.x - xMin) / binSize),
        binCount - 1
      );
      bins[binIndex].yVals.push(pt.y);
      bins[binIndex].originalValues.push(pt.y);
    });

    // Aggregate values in each bin
    return {
      all: bins.map(bin => ({
        x: bin.x,
        y: aggregateValues(bin.yVals, aggregation),
        originalValue:
          bin.originalValues[0] ?? aggregateValues(bin.yVals, aggregation),
      })),
    };
  }

  // Group and bin
  const grouped: Record<string, BinnedPoint[]> = {};
  const groups = Array.from(new Set(points.map(pt => pt.group || 'Other')));

  groups.forEach(group => {
    const groupPoints = points.filter(pt => (pt.group || 'Other') === group);
    const xVals = groupPoints.map(pt => pt.x);
    if (xVals.length === 0) {
      grouped[group] = [];
      return;
    }

    const xMin = Math.min(...xVals);
    const xMax = Math.max(...xVals);

    if (xMax === xMin) {
      grouped[group] = groupPoints.map(pt => ({
        x: pt.x,
        y: pt.y,
        originalValue: pt.y,
      }));
      return;
    }

    const binSize = (xMax - xMin) / binCount;
    const bins: {x: number; yVals: number[]; originalValues: number[]}[] =
      Array.from({length: binCount}, (_, i) => ({
        x: xMin + binSize * (i + 0.5),
        yVals: [],
        originalValues: [],
      }));

    // Assign points to bins
    groupPoints.forEach(pt => {
      const binIndex = Math.min(
        Math.floor((pt.x - xMin) / binSize),
        binCount - 1
      );
      bins[binIndex].yVals.push(pt.y);
      bins[binIndex].originalValues.push(pt.y);
    });

    // Aggregate values in each bin
    grouped[group] = bins.map(bin => ({
      x: bin.x,
      y: aggregateValues(bin.yVals, aggregation),
      originalValue:
        bin.originalValues[0] ?? aggregateValues(bin.yVals, aggregation),
    }));
  });

  return grouped;
};
