/**
 * chartDataProcessing.ts
 *
 * This file contains functions used for processing the data for the charts.
 * Functions are used to go from ExtractedCallData to ProcessedChartPoint.
 */
import {parseRefMaybe} from '@wandb/weave/react';
import React from 'react';

import {
  getFeedbackFieldValue,
  getInputOutputFieldValue,
  getOpNameDisplay,
} from './extractData';
import {COLOR_PALETTE, getGroupValues} from './format';
import {ChartAxisField, DataPoint, ExtractedCallData} from './types';

/**
 * Parse a weave reference and extract a meaningful display name.
 *
 * @param ref - A weave reference string or any other string
 * @returns The display name or the original string if not a weave reference
 *
 * @example
 * parseWeaveDisplayName("weave:///wandb/my-project/Model/my-model:v1") // returns "my-model"
 * parseWeaveDisplayName("weave:///wandb/project/object/abc123/attr/model_id") // returns "abc123.model_id"
 * parseWeaveDisplayName("some-other-string") // returns "some-other-string"
 */
const parseWeaveDisplayName = (ref: string): string => {
  const parsedRef = parseRefMaybe(ref);
  if (!parsedRef || parsedRef.scheme !== 'weave') {
    return ref;
  }
  if (parsedRef.artifactRefExtra) {
    const parts = parsedRef.artifactRefExtra.split('/');
    const attrIndex = parts.findIndex(part => part === 'attr');
    if (attrIndex !== -1 && attrIndex + 1 < parts.length) {
      return `${parsedRef.artifactName}.${parts[attrIndex + 1]}`;
    }
  }
  return parsedRef.artifactName;
};

export type ChartPointsOptions = {
  data: ExtractedCallData[];
  xAxis: string;
  yAxis: string;
  xField?: ChartAxisField;
  yField?: ChartAxisField;
  groupKeys?: string[];
};

export type ProcessedChartPoint = DataPoint & {
  display_name: string;
  callId?: string;
  traceId?: string;
  group?: string;
  color?: string;
};

export type DataRanges = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

export type GroupingResult = {
  colorGroups: string[];
  groupColorMap: Record<string, string>;
};

/**
 * Checks if there are multiple operation names in the data
 */
export const useMultipleOperations = (data: ExtractedCallData[]): boolean => {
  return React.useMemo(() => {
    const uniqueOpNames = new Set(
      data.map(d => getOpNameDisplay(d.op_name)).filter(Boolean)
    );
    return uniqueOpNames.size > 1;
  }, [data]);
};

/**
 * Creates color groups based on groupKeys
 */
export const useColorGroups = (
  data: ExtractedCallData[],
  groupKeys?: string[]
): string[] => {
  return React.useMemo(() => {
    if (!groupKeys || groupKeys.length === 0) {
      return [];
    }

    const groups = new Set<string>();
    data.forEach(d => {
      const groupParts: string[] = [];

      groupKeys.forEach(key => {
        let groupValue = '';

        if (key.startsWith('input.') || key.startsWith('output.')) {
          const value = getInputOutputFieldValue(d, key);
          const rawValue = (value as object)?.toString() || 'Unknown';
          groupValue = parseWeaveDisplayName(rawValue);
        } else if (key === 'op_name') {
          groupValue = getOpNameDisplay(d.op_name) || 'Unknown';
        } else {
          // Handle other field types
          const value = extractFieldValue(d, key);
          groupValue = (value as object)?.toString() || 'Unknown';
        }

        groupParts.push(groupValue);
      });

      // Join multiple group values with ' | ' separator
      const finalGroupValue = groupParts.join(' | ');
      groups.add(finalGroupValue);
    });

    return Array.from(groups).sort();
  }, [data, groupKeys]);
};

/**
 * Creates a color mapping for groups
 */
export const useGroupColorMap = (
  colorGroups: string[]
): Record<string, string> => {
  return React.useMemo(() => {
    const map: Record<string, string> = {};
    colorGroups.forEach((group, idx) => {
      map[group] = COLOR_PALETTE[idx % COLOR_PALETTE.length];
    });
    return map;
  }, [colorGroups]);
};

/**
 * Creates a group color function
 */
export const useGroupColor = (
  data: ExtractedCallData[],
  groupKeys?: string[],
  groupColorMap?: Record<string, string>
) => {
  return React.useCallback(
    (group: string) => {
      if (groupKeys && groupColorMap) {
        return groupColorMap[group] || '#000';
      }
      const groupValues = getGroupValues(data, groupKeys?.[0] || '');
      const idx = groupValues.indexOf(group);
      return COLOR_PALETTE[idx % COLOR_PALETTE.length];
    },
    [groupKeys, groupColorMap, data]
  );
};

/**
 * Extracts field value from data, handling both built-in and input/output fields
 */
export const extractFieldValue = (
  data: ExtractedCallData,
  fieldKey: string
): unknown => {
  if (fieldKey.startsWith('input.') || fieldKey.startsWith('output.')) {
    return getInputOutputFieldValue(data, fieldKey);
  }
  if (
    fieldKey.startsWith('annotations.') ||
    fieldKey.startsWith('scores.') ||
    fieldKey.startsWith('reactions.')
  ) {
    return getFeedbackFieldValue(data, fieldKey);
  }
  return data[fieldKey as keyof ExtractedCallData];
};

/**
 * Converts field value to appropriate numeric value for charts
 */
export const convertFieldValue = (
  value: unknown,
  field?: ChartAxisField
): number => {
  // Handle undefined/null values by returning NaN so they get filtered out
  if (value === undefined || value === null) {
    return NaN;
  }

  // Handle boolean values - convert to 0/1 for plotting
  if (field?.type === 'boolean' || typeof value === 'boolean') {
    return value === true ? 1 : 0;
  }

  if (field?.type === 'date') {
    return new Date(value as string).getTime();
  }

  // For numeric values, ensure we return a valid number
  const numericValue = Number(value);
  return isNaN(numericValue) ? NaN : numericValue;
};

/**
 * Determines the color group for a data point
 */
export const determineColorGroup = (
  data: ExtractedCallData,
  groupKeys?: string[]
): string => {
  if (!groupKeys || groupKeys.length === 0) {
    return '';
  }

  const groupParts: string[] = [];

  groupKeys.forEach(key => {
    let groupValue = '';

    if (key.startsWith('input.') || key.startsWith('output.')) {
      const value = getInputOutputFieldValue(data, key);
      const rawValue = (value as object)?.toString() || 'Unknown';
      groupValue = parseWeaveDisplayName(rawValue);
    } else if (key === 'op_name') {
      groupValue = getOpNameDisplay(data.op_name) || 'Unknown';
    } else {
      // Handle other field types
      const value = extractFieldValue(data, key);
      groupValue = (value as object)?.toString() || 'Unknown';
    }

    groupParts.push(groupValue);
  });

  // Join multiple group values with ' | ' separator
  return groupParts.join(' | ');
};

/**
 * Converts raw data to chart points with all transformations applied
 */
export const useChartPoints = (
  options: ChartPointsOptions
): ProcessedChartPoint[] => {
  const {data, xAxis, yAxis, xField, yField, groupKeys} = options;

  return React.useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }
    const result = data
      .map(d => {
        const colorGroup = determineColorGroup(d, groupKeys);

        const xValue = extractFieldValue(d, xAxis);
        const yValue = extractFieldValue(d, yAxis);

        return {
          x: convertFieldValue(xValue, xField),
          y: convertFieldValue(yValue, yField),
          display_name: d.display_name || '',
          callId: d.callId,
          traceId: d.traceId,
          group: colorGroup,
        };
      })
      .filter(
        pt =>
          pt.x !== undefined &&
          pt.y !== undefined &&
          typeof pt.x === 'number' &&
          typeof pt.y === 'number' &&
          !isNaN(pt.x) &&
          !isNaN(pt.y)
      ) as ProcessedChartPoint[];

    return result;
  }, [data, xAxis, yAxis, xField, yField, groupKeys]);
};

/**
 * Calculates data ranges for chart domains
 */
export const useDataRanges = (points: ProcessedChartPoint[]): DataRanges => {
  return React.useMemo(() => {
    if (points.length === 0) return {xMin: 0, xMax: 1, yMin: 0, yMax: 1};

    const xValues = points.map(p => p.x);
    const yValues = points.map(p => p.y);

    return {
      xMin: Math.min(...xValues),
      xMax: Math.max(...xValues),
      yMin: Math.min(...yValues),
      yMax: Math.max(...yValues),
    };
  }, [points]);
};

/**
 * Simple loading state check for chart data
 */
export const useChartDataReady = (
  data: ExtractedCallData[],
  points: ProcessedChartPoint[],
  xField?: ChartAxisField,
  yField?: ChartAxisField,
  dataRanges?: DataRanges
): boolean => {
  return React.useMemo(() => {
    return Boolean(
      data &&
        data.length > 0 &&
        points.length > 0 &&
        xField &&
        yField &&
        dataRanges
    );
  }, [data, points, xField, yField, dataRanges]);
};

/**
 * Hook that combines all chart data processing logic
 */
export const useChartData = (
  data: ExtractedCallData[],
  xAxis: string,
  yAxis: string,
  xField?: ChartAxisField,
  yField?: ChartAxisField,
  groupKeys?: string[]
) => {
  const hasMultipleOperations = useMultipleOperations(data);
  const colorGroups = useColorGroups(data, groupKeys);
  const groupColorMap = useGroupColorMap(colorGroups);
  const groupColor = useGroupColor(data, groupKeys, groupColorMap);

  const points = useChartPoints({
    data,
    xAxis,
    yAxis,
    xField,
    yField,
    groupKeys,
  });

  const dataRanges = useDataRanges(points);
  const isDataReady = useChartDataReady(
    data,
    points,
    xField,
    yField,
    dataRanges
  );

  return {
    points,
    dataRanges,
    isDataReady,
    hasMultipleOperations,
    colorGroups,
    groupColorMap,
    groupColor,
  };
};
