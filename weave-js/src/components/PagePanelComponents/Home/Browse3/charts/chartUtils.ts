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
  justifyContent: 'flex-start' as const,
  alignItems: 'flex-start' as const,
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
export const tooltipContainerStyle = (isFullscreen?: boolean) => ({
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  border: '1px solid #ddd',
  borderRadius: '3px',
  padding: isFullscreen ? '8px 12px' : '2px 4px',
  fontSize: isFullscreen ? '16px' : '11px',
  fontFamily: 'Source Sans Pro, sans-serif',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  minWidth: isFullscreen ? '200px' : 'auto',
});

export const tooltipHeaderStyle = (isFullscreen?: boolean) => ({
  color: '#666',
  fontWeight: 500,
  fontFamily: 'Source Sans Pro, sans-serif',
  marginBottom: isFullscreen ? '6px' : '1px',
  fontSize: isFullscreen ? '16px' : 'inherit',
});

export const tooltipRowStyle = (isFullscreen?: boolean) => ({
  color: '#333',
  fontFamily: 'Source Sans Pro, sans-serif',
  display: 'flex',
  justifyContent: 'space-between',
  gap: isFullscreen ? '12px' : '4px',
  lineHeight: isFullscreen ? '1.4' : '1.2',
  fontSize: isFullscreen ? '14px' : 'inherit',
  marginBottom: isFullscreen ? '2px' : '0px',
});

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
      fractionalSecondDigits: 3,
    });
  }

  // If the date is this year, don't show year
  if (date.getFullYear() === today.getFullYear()) {
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
  }

  // Otherwise show full date
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
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
 * Enhanced date tick formatter that adapts format based on domain range
 * This replaces the simple formatDateTick with more sophisticated formatting
 */
export const createDateTickFormatter = (domain: [number, number]) => {
  const range = domain[1] - domain[0];
  const oneDay = 24 * 60 * 60 * 1000;
  const oneHour = 60 * 60 * 1000;
  const oneMinute = 60 * 1000;

  if (range <= oneMinute) {
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      });
  } else if (range <= oneHour) {
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
  } else if (range <= oneDay) {
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      });
  } else if (range <= 7 * oneDay) {
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
  } else if (range <= 30 * oneDay) {
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
      });
  } else {
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        year: 'numeric',
      });
  }
};

/**
 * Creates unified axis tick formatters for both X and Y axes
 * @param xField The X-axis field configuration
 * @param yField The Y-axis field configuration
 * @param xDomain Optional X-axis domain for enhanced date formatting
 * @param yDomain Optional Y-axis domain for enhanced date formatting
 * @returns Object with xTickFormatter and yTickFormatter functions
 */
export const createAxisTickFormatters = (
  xField?: AxisFieldType,
  yField?: AxisFieldType,
  xDomain?: [number, number],
  yDomain?: [number, number]
) => {
  const xTickFormatter = (value: any) => {
    if (xField?.type === 'date' && xDomain) {
      const formatter = createDateTickFormatter(xDomain);
      return formatter(value);
    }
    return formatAxisTick(value, xField);
  };

  const yTickFormatter = (value: any) => {
    if (yField?.type === 'date' && yDomain) {
      const formatter = createDateTickFormatter(yDomain);
      return formatter(value);
    }
    return formatAxisTick(value, yField);
  };

  return {xTickFormatter, yTickFormatter};
};

/**
 * Calculates optimal tick count to prevent overlapping based on field type and domain
 * @param chartDimensions Chart width and height
 * @param chartMargins Chart margins
 * @param field The axis field configuration
 * @param domain The current axis domain
 * @param axis Which axis ('x' or 'y')
 * @returns Optimal number of ticks
 */
export const calculateOptimalTickCount = (
  chartDimensions: ChartDimensions,
  chartMargins: ChartMargins,
  field?: AxisFieldType,
  domain?: [number, number],
  axis: 'x' | 'y' = 'x'
): number => {
  const plotWidth =
    chartDimensions.width - chartMargins.left - chartMargins.right;
  const plotHeight =
    chartDimensions.height - chartMargins.top - chartMargins.bottom;

  // Use appropriate dimension based on axis
  const availableSpace = axis === 'x' ? plotWidth : plotHeight;

  // Estimate average label width based on field type and current domain
  let estimatedLabelWidth = 60; // Default for numeric values

  if (field?.type === 'date' && domain) {
    const range = domain[1] - domain[0];
    const oneDay = 24 * 60 * 60 * 1000;
    const oneHour = 60 * 60 * 1000;
    const oneMinute = 60 * 1000;

    if (range <= oneMinute) {
      estimatedLabelWidth = 120; // "HH:MM:SS.sss" format
    } else if (range <= oneHour) {
      estimatedLabelWidth = 100; // "HH:MM:SS" format
    } else if (range <= oneDay) {
      estimatedLabelWidth = 70; // "HH:MM" format
    } else if (range <= 7 * oneDay) {
      estimatedLabelWidth = 90; // "Mon DD, HH:MM" format
    } else if (range <= 30 * oneDay) {
      estimatedLabelWidth = 70; // "Mon DD" format
    } else {
      estimatedLabelWidth = 80; // "Mon YYYY" format
    }
  } else if (domain) {
    // For numeric values, estimate based on the range and typical formatting
    const range = Math.abs(domain[1] - domain[0]);
    if (range < 1) {
      estimatedLabelWidth = 50; // Small decimals
    } else if (range < 1000) {
      estimatedLabelWidth = 40; // Regular numbers
    } else {
      estimatedLabelWidth = 60; // Large numbers
    }
  }

  // Add some padding between ticks (20px minimum spacing)
  const minTickSpacing = estimatedLabelWidth + 20;
  const maxTicks = Math.floor(availableSpace / minTickSpacing);

  // Ensure we have at least 2 ticks and at most 10 ticks
  return Math.max(2, Math.min(maxTicks, 10));
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

// Chart coordinate clamping utilities
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

/**
 * Creates a coordinate clamping function that constrains coordinates to within chart axes
 * @param chartDimensions The width and height of the chart container
 * @param margins The margins around the chart plotting area
 * @param axisPadding Additional padding to stay within the axis lines themselves
 * @returns A function that clamps coordinates to the chart axes area
 */
export const createCoordinateClamp = (
  chartDimensions: ChartDimensions,
  margins: ChartMargins,
  axisPadding: AxisPadding = {left: 0, right: 0, top: 0, bottom: 0}
) => {
  return (x: number, y: number) => {
    const clampedX = Math.max(
      margins.left + axisPadding.left,
      Math.min(x, chartDimensions.width - margins.right - axisPadding.right)
    );
    const clampedY = Math.max(
      margins.top + axisPadding.top,
      Math.min(y, chartDimensions.height - margins.bottom - axisPadding.bottom)
    );
    return {x: clampedX, y: clampedY};
  };
};

/**
 * Creates a screen-to-data coordinate conversion function
 * @param chartDimensions The width and height of the chart container
 * @param margins The margins around the chart plotting area
 * @param xDomain The current X-axis domain [min, max]
 * @param yDomain The current Y-axis domain [min, max]
 * @returns A function that converts screen coordinates to data coordinates
 */
export const createScreenToDataConverter = (
  chartDimensions: ChartDimensions,
  margins: ChartMargins,
  xDomain: [number, number],
  yDomain: [number, number]
) => {
  return (screenX: number, screenY: number) => {
    const plotWidth = chartDimensions.width - margins.left - margins.right;
    const plotHeight = chartDimensions.height - margins.top - margins.bottom;

    const xRatio = (screenX - margins.left) / plotWidth;
    const yRatio = (plotHeight - (screenY - margins.top)) / plotHeight;

    const dataX = xDomain[0] + xRatio * (xDomain[1] - xDomain[0]);
    const dataY = yDomain[0] + yRatio * (yDomain[1] - yDomain[0]);

    return {dataX, dataY};
  };
};

/**
 * Creates consistent chart margins for all chart types
 * @param isFullscreen Whether the chart is in fullscreen mode
 * @returns ChartMargins object with left, right, top, bottom values
 */
export const createChartMargins = (isFullscreen?: boolean): ChartMargins => ({
  left: isFullscreen ? 120 : 60,
  right: isFullscreen ? 60 : 30,
  top: isFullscreen ? 48 : 24,
  bottom: isFullscreen ? 72 : 36,
});

/**
 * Creates consistent axis padding for all chart types
 * @param isFullscreen Whether the chart is in fullscreen mode
 * @returns AxisPadding object with left, right, top, bottom values
 */
export const createAxisPadding = (isFullscreen?: boolean): AxisPadding => ({
  left: 0,
  right: 0,
  top: -20,
  bottom: isFullscreen ? 6 : 16,
});
