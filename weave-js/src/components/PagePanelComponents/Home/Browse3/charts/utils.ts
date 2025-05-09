import {Layout} from 'plotly.js';

import {
  ChartConfig,
  ChartDataErrors,
  ChartDataLatency,
  ChartDataPoint,
  ChartDataUsage,
  ChartUnits,
  TimestampPoint,
  YAxisInfo,
} from './ChartTypes';

// Common chart layout config
export const getBaseLayout = (height: number): Partial<Layout> => ({
  height,
  margin: {
    l: 60,
    r: 20,
    t: 35,
    b: 50,
  },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: {
    family: 'Arial, sans-serif',
    size: 10,
    color: '#6e7191', // MOON_500
  },
  showlegend: false,
  hovermode: 'closest' as const,
  xaxis: {
    title: 'Time',
    tickformat: '%H:%M',
    gridcolor: 'rgba(0,0,0,0.05)',
    tickfont: {
      size: 10,
      color: '#6e7191', // MOON_500
    },
  },
  yaxis: {
    gridcolor: 'rgba(0,0,0,0.05)',
    tickfont: {
      size: 10,
      color: '#6e7191', // MOON_500
    },
  },
});

// Process timestamp data into consistent format
export function processTimestampData<T extends TimestampPoint>(
  data: T[]
): ChartDataPoint[] {
  return data
    .map(d => {
      // Get the y value based on data type
      let yValue = 0;
      if ('latency' in d) {
        yValue = (d as ChartDataLatency).latency;
      } else if ('usage' in d && (d as ChartDataUsage).usage != null) {
        yValue = (d as ChartDataUsage).usage!;
      } else if ('tokens' in d && (d as ChartDataUsage).tokens != null) {
        yValue = (d as ChartDataUsage).tokens!;
      } else if (
        'total_tokens' in d &&
        (d as ChartDataUsage).total_tokens != null
      ) {
        yValue = (d as ChartDataUsage).total_tokens!;
      } else if ('isError' in d) {
        yValue = (d as ChartDataErrors).isError ? 1 : 0;
      }

      // Process x value
      let xValue: Date | number;
      // If x is already a Date or timestamp string, convert to Date
      if (d.started_at instanceof Date) {
        xValue = d.started_at;
      } else if (
        typeof d.started_at === 'string' &&
        d.started_at.includes('-')
      ) {
        xValue = new Date(d.started_at);
      } else {
        // Otherwise treat as a number
        xValue =
          typeof d.started_at === 'number'
            ? d.started_at
            : Number(d.started_at);
      }

      return {
        x: xValue,
        y: yValue,
        isTimeX: xValue instanceof Date,
      };
    })
    .sort((a, b) => {
      const aTime = a.x instanceof Date ? a.x.getTime() : Number(a.x);
      const bTime = b.x instanceof Date ? b.x.getTime() : Number(b.x);
      return aTime - bTime;
    });
}

// Calculate y-axis information based on data and config
export function getYAxisInfo(
  processedData: ChartDataPoint[],
  units?: ChartUnits
): YAxisInfo {
  // Case: if a specific unit is provided, use it
  if (units) {
    if (units.includes('tokens')) {
      // Capitalize the token type
      const tokenType = units
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      return {isTokenData: true, title: tokenType, units: 'tokens'};
    } else if (units === 'ms') {
      return {isTokenData: false, title: 'Latency', units: 'ms'};
    } else if (units === '$') {
      return {isTokenData: false, title: 'Cost', units: '$'};
    }
  }

  // Fallback: Try to infer from the data
  if (processedData.length > 0) {
    // Token counts are typically integers and often much larger than typical latency values
    if (Number.isInteger(processedData[0].y) && processedData[0].y > 1000) {
      return {isTokenData: true, title: 'Tokens', units: 'tokens'};
    }
  }

  return {isTokenData: false, title: 'Latency', units: 'ms'};
}

// Get y-axis number format
export function getYAxisFormat(isTokenData: boolean, units?: string): string {
  if (isTokenData || units === 'tokens') {
    return ',.0f'; // Integer with commas (e.g., 1,234)
  } else if (units === '$') {
    return '$,.2f'; // Currency with 2 decimal places (e.g., $12.34)
  } else if (units === 'ms') {
    return ',.1f'; // 1 decimal place for milliseconds (e.g., 123.4)
  }
  return ',.2f'; // Default format with 2 decimal places
}

// Get x-axis format
export function getXAxisFormat(isTimeBasedX: boolean): string {
  return isTimeBasedX ? '%b %d, %H:%M' : ',.1f';
}

// Group data points by time interval (for binning/aggregation)
export function groupDataByTimeInterval(
  data: ChartDataPoint[],
  intervalMinutes: number = 60,
  aggregationMethod: 'sum' | 'avg' | 'max' | 'min' | 'count' = 'avg'
): ChartDataPoint[] {
  // Skip if data is not time-based
  if (data.length === 0 || !data[0].isTimeX) {
    return data;
  }

  const intervalMs = intervalMinutes * 60 * 1000;
  const groups = new Map<number, number[]>();

  // Group data points
  data.forEach(point => {
    if (point.x instanceof Date) {
      // Round to nearest interval
      const timestamp = point.x.getTime();
      const intervalKey = Math.floor(timestamp / intervalMs) * intervalMs;

      if (!groups.has(intervalKey)) {
        groups.set(intervalKey, []);
      }

      groups.get(intervalKey)!.push(point.y);
    }
  });

  // Apply aggregation method to each group
  return Array.from(groups.entries())
    .map(([timestamp, values]) => {
      let aggregatedValue: number;

      switch (aggregationMethod) {
        case 'sum':
          aggregatedValue = values.reduce((sum, val) => sum + val, 0);
          break;
        case 'max':
          aggregatedValue = Math.max(...values);
          break;
        case 'min':
          aggregatedValue = Math.min(...values);
          break;
        case 'count':
          aggregatedValue = values.length;
          break;
        case 'avg':
        default:
          aggregatedValue =
            values.reduce((sum, val) => sum + val, 0) / values.length;
          break;
      }

      return {
        x: new Date(timestamp),
        y: aggregatedValue,
        isTimeX: true,
      };
    })
    .sort((a, b) => {
      const aTime = a.x instanceof Date ? a.x.getTime() : Number(a.x);
      const bTime = b.x instanceof Date ? b.x.getTime() : Number(b.x);
      return aTime - bTime;
    });
}

// Remove groupDataByTimeInterval and add groupDataByMinBins
export function groupDataByMinBins(
  data: ChartDataPoint[],
  minBins: number = 10,
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max' = 'sum'
): ChartDataPoint[] {
  if (data.length === 0) return data;

  const isTimeX = data[0].isTimeX;
  const getX = (d: ChartDataPoint) =>
    isTimeX && d.x instanceof Date ? d.x.getTime() : Number(d.x);

  const xs = data.map(getX);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  if (minX === maxX) {
    // All x are the same, just return a single bin
    return [
      {
        x: isTimeX ? new Date(minX) : minX,
        y: data.reduce((sum, d) => sum + d.y, 0),
        isTimeX,
      },
    ];
  }
  const binWidth = (maxX - minX) / minBins;
  const bins: {values: number[]; x: number; count: number}[] = Array.from(
    {length: minBins},
    (_, i) => ({values: [], x: minX + i * binWidth + binWidth / 2, count: 0})
  );
  data.forEach(d => {
    const xVal = getX(d);
    let binIdx = Math.floor((xVal - minX) / binWidth);
    if (binIdx < 0) binIdx = 0;
    if (binIdx >= minBins) binIdx = minBins - 1;
    bins[binIdx].values.push(d.y);
    bins[binIdx].count += 1;
  });
  return bins.map(b => {
    let y: number;
    if (b.values.length === 0) {
      y = 0;
    } else {
      switch (aggregation) {
        case 'sum':
          y = b.values.reduce((sum, v) => sum + v, 0);
          break;
        case 'avg':
          y = b.values.reduce((sum, v) => sum + v, 0) / b.values.length;
          break;
        case 'count':
          y = b.values.length;
          break;
        case 'min':
          y = Math.min(...b.values);
          break;
        case 'max':
          y = Math.max(...b.values);
          break;
        default:
          y = b.values.reduce((sum, v) => sum + v, 0);
      }
    }
    return {
      x: isTimeX ? new Date(b.x) : b.x,
      y,
      isTimeX,
      binSize: b.values.length,
      numCalls: b.count,
    };
  });
}

// Serialization helpers for chart configs
export type SerializedChartConfigs = {
  version: number;
  data: ChartConfig[];
  [key: string]: any;
};

export function serializeChartConfigs(
  configs: ChartConfig[]
): SerializedChartConfigs {
  // Ensure layout fields are included
  return {
    version: 1,
    data: configs.map(cfg => ({
      ...cfg,
      x: cfg.x ?? 0,
      y: cfg.y ?? 0,
      w: cfg.w ?? 4,
      h: cfg.h ?? 4,
    })),
  };
}

export function deserializeChartConfigs(obj: any): ChartConfig[] {
  if (!obj || !Array.isArray(obj.data)) return [];
  return obj.data.map((cfg: any) => ({
    ...cfg,
    x: cfg.x ?? 0,
    y: cfg.y ?? 0,
    w: cfg.w ?? 4,
    h: cfg.h ?? 4,
  }));
}
