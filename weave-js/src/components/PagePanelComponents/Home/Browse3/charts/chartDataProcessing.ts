/**
 * This file contains functions used for processing the data for the charts.
 * Functions are used to go from ExtractedCallData to ProcessedChartPoint.
 */
import {parseRefMaybe} from '@wandb/weave/react';
import React from 'react';

import {getInputOutputFieldValue, getOpNameDisplay} from './extractData';
import {COLOR_PALETTE, getGroupValues} from './format';
import {
  ChartAxisField,
  DataRanges,
  ExtractedCallData,
  ProcessedChartPoint,
} from './types';

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
  groupBy?: string;
  colorGroupKey?: string;
  hasMultipleOperations?: boolean;
  groupByTraceId?: boolean;
};

export type GroupingResult = {
  colorGroups: string[];
  groupColorMap: Record<string, string>;
  hasMultipleOperations: boolean;
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
 * Creates color groups based on colorGroupKey and optionally nested with op_name
 */
export const useColorGroups = (
  data: ExtractedCallData[],
  groupBy?: string,
  colorGroupKey?: string,
  hasMultipleOperations?: boolean
): string[] => {
  return React.useMemo(() => {
    if (!colorGroupKey) {
      return getGroupValues(data, groupBy);
    }

    const groups = new Set<string>();
    data.forEach(d => {
      let colorGroupValue = '';

      if (
        colorGroupKey.startsWith('input.') ||
        colorGroupKey.startsWith('output.')
      ) {
        const value = getInputOutputFieldValue(d, colorGroupKey);
        const rawValue = value?.toString() || 'Unknown';
        // Apply weave reference parsing to the group value
        colorGroupValue = parseWeaveDisplayName(rawValue);
      } else if (colorGroupKey === 'op_name') {
        colorGroupValue = getOpNameDisplay(d.op_name) || 'Unknown';
      }

      if (hasMultipleOperations && colorGroupKey !== 'op_name') {
        const opName = getOpNameDisplay(d.op_name) || 'Unknown';
        groups.add(`${opName} | ${colorGroupValue}`);
      } else {
        groups.add(colorGroupValue);
      }
    });

    return Array.from(groups).sort();
  }, [data, groupBy, colorGroupKey, hasMultipleOperations]);
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
  groupBy?: string,
  colorGroupKey?: string,
  groupColorMap?: Record<string, string>
) => {
  return React.useCallback(
    (group: string) => {
      if (colorGroupKey && groupColorMap) {
        return groupColorMap[group] || '#000';
      }
      const groupValues = getGroupValues(data, groupBy);
      const idx = groupValues.indexOf(group);
      return COLOR_PALETTE[idx % COLOR_PALETTE.length];
    },
    [colorGroupKey, groupColorMap, data, groupBy]
  );
};

/**
 * Extracts field value from data, handling both built-in and input/output fields
 */
export const extractFieldValue = (
  data: ExtractedCallData,
  fieldKey: string
): any => {
  if (fieldKey.startsWith('input.') || fieldKey.startsWith('output.')) {
    return getInputOutputFieldValue(data, fieldKey);
  }
  return data[fieldKey as keyof ExtractedCallData];
};

/**
 * Converts field value to appropriate numeric value for charts
 */
export const convertFieldValue = (
  value: any,
  field?: ChartAxisField
): number => {
  // Handle undefined/null values by returning NaN so they get filtered out
  if (value === undefined || value === null) {
    return NaN;
  }

  if (field?.type === 'date') {
    return new Date(value as any).getTime();
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
  colorGroupKey?: string,
  hasMultipleOperations?: boolean
): string => {
  const opNameGroup = getOpNameDisplay(data.op_name);

  if (!colorGroupKey) {
    return opNameGroup || '';
  }

  let colorGroup = '';
  if (
    colorGroupKey.startsWith('input.') ||
    colorGroupKey.startsWith('output.')
  ) {
    const value = getInputOutputFieldValue(data, colorGroupKey);
    const rawValue = value?.toString() || 'Unknown';
    // Apply weave reference parsing to the group value
    colorGroup = parseWeaveDisplayName(rawValue);
  } else if (colorGroupKey === 'op_name') {
    colorGroup = getOpNameDisplay(data.op_name) || 'Unknown';
  }

  if (hasMultipleOperations && colorGroupKey !== 'op_name' && opNameGroup) {
    return `${opNameGroup} | ${colorGroup}`;
  }

  return colorGroup;
};

/**
 * Converts raw data to chart points with all transformations applied
 */
export const useChartPoints = (
  options: ChartPointsOptions
): ProcessedChartPoint[] => {
  const {
    data,
    xAxis,
    yAxis,
    xField,
    yField,
    groupBy,
    colorGroupKey,
    hasMultipleOperations,
    groupByTraceId,
  } = options;

  return React.useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // Special handling for evaluations when x-axis is start time
    if (groupByTraceId && xAxis === 'started_at') {
      // Group data by traceId
      const groupedByTrace = new Map<string, ExtractedCallData[]>();

      data.forEach(d => {
        if (!groupedByTrace.has(d.traceId)) {
          groupedByTrace.set(d.traceId, []);
        }
        groupedByTrace.get(d.traceId)!.push(d);
      });

      const result: ProcessedChartPoint[] = [];

      // Process each trace group
      groupedByTrace.forEach(traceData => {
        // Sort by start time within each trace
        const sortedTraceData = [...traceData].sort(
          (a, b) =>
            new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
        );

        // Assign index-based x coordinates
        sortedTraceData.forEach((d, index) => {
          const colorGroup = determineColorGroup(
            d,
            colorGroupKey,
            hasMultipleOperations
          );
          const yValue = extractFieldValue(d, yAxis);

          const point = {
            x: index, // Use index instead of timestamp
            y: convertFieldValue(yValue, yField),
            display_name: d.display_name || '',
            callId: d.callId,
            traceId: d.traceId,
            group:
              colorGroup || (groupBy ? getOpNameDisplay(d.op_name) : undefined),
          };

          // Only include valid points
          if (
            point.y !== undefined &&
            typeof point.y === 'number' &&
            !isNaN(point.y)
          ) {
            result.push(point);
          }
        });
      });

      return result;
    }

    // Standard processing for non-evaluation cases
    const result = data
      .map(d => {
        const colorGroup = determineColorGroup(
          d,
          colorGroupKey,
          hasMultipleOperations
        );
        const opNameGroup = getOpNameDisplay(d.op_name);

        const xValue = extractFieldValue(d, xAxis);
        const yValue = extractFieldValue(d, yAxis);

        return {
          x: convertFieldValue(xValue, xField),
          y: convertFieldValue(yValue, yField),
          display_name: d.display_name || '',
          callId: d.callId,
          traceId: d.traceId,
          group: colorGroup || (groupBy ? opNameGroup : undefined),
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
  }, [
    data,
    xAxis,
    yAxis,
    xField,
    yField,
    groupBy,
    colorGroupKey,
    hasMultipleOperations,
    groupByTraceId,
  ]);
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
  groupBy?: string,
  colorGroupKey?: string,
  groupByTraceId?: boolean
) => {
  const hasMultipleOperations = useMultipleOperations(data);
  const colorGroups = useColorGroups(
    data,
    groupBy,
    colorGroupKey,
    hasMultipleOperations
  );
  const groupColorMap = useGroupColorMap(colorGroups);
  const groupColor = useGroupColor(data, groupBy, colorGroupKey, groupColorMap);

  const points = useChartPoints({
    data,
    xAxis,
    yAxis,
    xField,
    yField,
    groupBy,
    colorGroupKey,
    hasMultipleOperations,
    groupByTraceId,
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
