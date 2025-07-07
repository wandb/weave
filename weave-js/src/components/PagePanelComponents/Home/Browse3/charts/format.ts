/**
 * format.ts
 *
 * This file contains functions used for formatting text in the charts.
 */
import {format, isSameDay} from 'date-fns';

import {getOpNameDisplay} from './extractData';
import {ChartAxisField, ExtractedCallData} from './types';

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
    });
  }

  if (date.getFullYear() === today.getFullYear()) {
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

export const formatSmartDateRange = (
  startTimestamp: number,
  endTimestamp: number
): string => {
  const startDate = new Date(startTimestamp);
  const endDate = new Date(endTimestamp);

  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
    return `${formatTooltipValue(startTimestamp)} - ${formatTooltipValue(
      endTimestamp
    )}`;
  }

  const binDuration = endTimestamp - startTimestamp;

  // For day-level or larger ranges
  if (binDuration >= 24 * 60 * 60 * 1000) {
    if (isSameDay(startDate, endDate)) {
      return format(startDate, 'M/d/yyyy');
    }
    return `${format(startDate, 'M/d/yyyy')} - ${format(endDate, 'M/d/yyyy')}`;
  }

  // For same-day ranges
  if (isSameDay(startDate, endDate)) {
    const baseDate = format(startDate, 'M/d/yyyy');

    // Sub-second precision
    if (binDuration < 1000) {
      if (
        startDate.getHours() === endDate.getHours() &&
        startDate.getMinutes() === endDate.getMinutes() &&
        startDate.getSeconds() === endDate.getSeconds()
      ) {
        const startMs = startDate.getMilliseconds().toString().padStart(3, '0');
        const endMs = endDate.getMilliseconds().toString().padStart(3, '0');
        return `${baseDate} ${format(
          startDate,
          'HH:mm:ss'
        )}.${startMs}-${endMs}`;
      }
      return `${baseDate} ${format(startDate, 'HH:mm:ss.SSS')} - ${format(
        endDate,
        'HH:mm:ss.SSS'
      )}`;
    }

    // Sub-minute precision
    if (binDuration < 60 * 1000) {
      if (
        startDate.getHours() === endDate.getHours() &&
        startDate.getMinutes() === endDate.getMinutes()
      ) {
        return `${baseDate} ${format(startDate, 'HH:mm')}:${format(
          startDate,
          'ss'
        )}-${format(endDate, 'ss')}`;
      }
      return `${baseDate} ${format(startDate, 'HH:mm:ss')} - ${format(
        endDate,
        'HH:mm:ss'
      )}`;
    }

    // Sub-hour precision
    if (binDuration < 60 * 60 * 1000) {
      if (startDate.getHours() === endDate.getHours()) {
        return `${baseDate} ${format(startDate, 'HH')}:${format(
          startDate,
          'mm'
        )}-${format(endDate, 'mm')}`;
      }
      return `${baseDate} ${format(startDate, 'HH:mm')} - ${format(
        endDate,
        'HH:mm'
      )}`;
    }

    // Hour precision
    return `${baseDate} ${format(startDate, 'HH')}-${format(endDate, 'HH')}`;
  }

  // Different days - show full format for both
  if (binDuration < 1000) {
    return `${format(startDate, 'M/d/yyyy HH:mm:ss.SSS')} - ${format(
      endDate,
      'M/d/yyyy HH:mm:ss.SSS'
    )}`;
  } else if (binDuration < 60 * 1000) {
    return `${format(startDate, 'M/d/yyyy HH:mm:ss')} - ${format(
      endDate,
      'M/d/yyyy HH:mm:ss'
    )}`;
  } else if (binDuration < 60 * 60 * 1000) {
    return `${format(startDate, 'M/d/yyyy HH:mm')} - ${format(
      endDate,
      'M/d/yyyy HH:mm'
    )}`;
  } else {
    return `${format(startDate, 'M/d/yyyy HH')} - ${format(
      endDate,
      'M/d/yyyy HH'
    )}`;
  }
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
  const values = Array.from(
    new Set(
      data
        .map(d => {
          const value = d[groupBy as keyof ExtractedCallData] as string;
          if (groupBy === 'op_name') {
            return getOpNameDisplay(value);
          }
          return value;
        })
        .filter(Boolean)
    )
  );
  return values;
};

export const getGroupColor = (group: string, groupValues: string[]): string => {
  const idx = groupValues.indexOf(group);
  return COLOR_PALETTE[idx % COLOR_PALETTE.length];
};

export const createAxisTickFormatters = (
  xField?: ChartAxisField,
  yField?: ChartAxisField,
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
 * Intelligently truncates text with special handling for labels with " | " separator.
 *
 * Args:
 *     text (string): The text to truncate.
 *     maxLength (number): Maximum length of the truncated text. Defaults to 40.
 *
 * Returns:
 *     string: The truncated text with ellipsis if needed.
 *
 * Examples:
 *     >>> truncateText("short text", 50)
 *     "short text"
 *     >>> truncateText("very long text that exceeds limit", 20)
 *     "very long...imit"
 *     >>> truncateText("left part | right part", 15)
 *     "left... | ri..."
 */
export const truncateText = (text: string, maxLength: number = 40): string => {
  if (!text || text.length <= maxLength) return text || '';

  // Special handling for labels with " | " separator - truncate both parts
  if (text.includes(' | ')) {
    const parts = text.split(' | ');
    if (parts.length === 2) {
      const [leftPart, rightPart] = parts;
      const availableLength = maxLength - 3; // Reserve space for " | "
      const leftMaxLength = Math.floor(availableLength * 0.5);
      const rightMaxLength = Math.floor(availableLength * 0.5);

      const truncatedLeft =
        leftPart.length > leftMaxLength
          ? leftPart.substring(0, Math.max(1, leftMaxLength - 3)) + '...'
          : leftPart;

      const truncatedRight =
        rightPart.length > rightMaxLength
          ? rightPart.substring(0, Math.max(1, rightMaxLength - 3)) + '...'
          : rightPart;

      return `${truncatedLeft} | ${truncatedRight}`;
    }
  }

  // For other long text, show beginning and end
  if (maxLength < 10) return text.substring(0, maxLength) + '...';

  const startLength = Math.floor((maxLength - 3) * 0.6);
  const endLength = Math.floor((maxLength - 3) * 0.4);

  return (
    text.substring(0, startLength) +
    '...' +
    text.substring(text.length - endLength)
  );
};

/**
 * Formats bin width in a human-readable format.
 *
 * Args:
 *     start (number): Start value of the bin.
 *     end (number): End value of the bin.
 *     isDate (boolean): Whether the values represent dates/timestamps.
 *     units (string): Optional units for non-date values.
 *
 * Returns:
 *     string: Formatted bin width string.
 *
 * Examples:
 *     >>> formatBinWidth(1000, 2000, false, "ms")
 *     "1000 ms"
 *     >>> formatBinWidth(1609459200000, 1609462800000, true)
 *     "1h"
 */
export const formatBinWidth = (
  start: number,
  end: number,
  isDate: boolean,
  units?: string
): string => {
  const width = end - start;
  if (!isDate) {
    return formatTooltipValue(width, units);
  }

  // For time ranges, format as duration
  const seconds = width / 1000;
  if (seconds < 1) {
    return `${Math.round(width)}ms`;
  } else if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m`;
  } else if (seconds < 86400) {
    return `${Math.round(seconds / 3600)}h`;
  } else {
    return `${Math.round(seconds / 86400)}d`;
  }
};
