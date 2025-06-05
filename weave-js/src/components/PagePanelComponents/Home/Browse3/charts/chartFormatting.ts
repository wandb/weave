import {
  ChartAxisField,
  ExtractedCallData,
  getOpNameDisplay,
} from './extractData';

export type AggregationMethod =
  | 'average'
  | 'sum'
  | 'min'
  | 'max'
  | 'p95'
  | 'p99';

export type DataPoint = {
  x: number;
  y: number;
  group?: string;
  [key: string]: any;
};

export type BinnedPoint = {
  x: number;
  y: number;
  originalValue: number;
};

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

export const formatTooltipDate = (value: number) => {
  const date = new Date(value);
  if (isNaN(date.getTime())) {
    return formatTooltipValue(value);
  }

  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
  }

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

export const formatTooltipValue = (value: any, unit?: string) => {
  if (typeof value !== 'number' || isNaN(value)) {
    return String(value);
  }

  if (
    Math.abs(value) >= 1e6 ||
    (Math.abs(value) > 0 && Math.abs(value) < 1e-3)
  ) {
    return `${value.toExponential(2)}${unit ? ` ${unit}` : ''}`;
  }

  const valueStr =
    Math.abs(value) >= 1000 ? value.toFixed(0) : value.toFixed(3);

  if (valueStr.length > 7) {
    return `${value.toPrecision(3)}${unit ? ` ${unit}` : ''}`;
  }

  return `${valueStr}${unit ? ` ${unit}` : ''}`;
};

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

export const formatDateTick = (value: number): string => {
  const date = new Date(value);
  return isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
};

export const formatAxisTick = (value: any, field?: ChartAxisField): string => {
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

export const getGroupColor = (group: string, groupValues: string[]): string => {
  const idx = groupValues.indexOf(group);
  return COLOR_PALETTE[idx % COLOR_PALETTE.length];
};
