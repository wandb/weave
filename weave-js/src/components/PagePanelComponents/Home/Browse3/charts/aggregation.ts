/*
  aggregation.ts

  This file contains the grouping, binning, and aggregation functions for the charts.
  The grouping and binning functions are used to group the data points by the group keys,
  and then bin the data points into bins. The aggregation function is used to aggregate the
  data points within each bin.
*/

import {AggregationMethod, BinnedPoint, BinningMode, DataPoint} from './types';

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
 * Creates time-based bins for the given binning mode.
 */
export const createTimeBins = (
  xMin: number,
  xMax: number,
  binningMode: BinningMode
): Array<{x: number; binStart: number; binEnd: number}> => {
  const bins: Array<{x: number; binStart: number; binEnd: number}> = [];
  
  if (binningMode === 'absolute') {
    // This shouldn't be called for absolute mode, but handle it gracefully
    return [];
  }

  const startDate = new Date(xMin);
  const endDate = new Date(xMax);
  
  let current = new Date(startDate);
  
  // Align to appropriate boundary based on binning mode
  switch (binningMode) {
    case 'hour':
      current.setMinutes(0, 0, 0);
      break;
    case 'day':
      current.setHours(0, 0, 0, 0);
      break;
    case 'month':
      current.setDate(1);
      current.setHours(0, 0, 0, 0);
      break;
    case 'year':
      current.setMonth(0, 1);
      current.setHours(0, 0, 0, 0);
      break;
  }
  
  while (current <= endDate) {
    const binStart = current.getTime();
    const next = new Date(current);
    
    // Advance to next boundary
    switch (binningMode) {
      case 'hour':
        next.setHours(next.getHours() + 1);
        break;
      case 'day':
        next.setDate(next.getDate() + 1);
        break;
      case 'month':
        next.setMonth(next.getMonth() + 1);
        break;
      case 'year':
        next.setFullYear(next.getFullYear() + 1);
        break;
    }
    
    const binEnd = next.getTime();
    const binCenter = binStart + (binEnd - binStart) / 2;
    
    bins.push({
      x: binCenter,
      binStart,
      binEnd,
    });
    
    current = next;
    
    // Safety check to prevent infinite loops
    if (bins.length > 10000) {
      console.warn('Time binning created too many bins, stopping at 10000');
      break;
    }
  }
  
  return bins;
};

export const binDataPoints = (
  points: DataPoint[],
  binCount: number = 20,
  aggregation: AggregationMethod = 'average',
  useGroups: boolean = false,
  binningMode: BinningMode = 'absolute'
): Record<string, BinnedPoint[]> => {
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

    // Create bins based on binning mode
    let bins: {
      x: number;
      binStart: number;
      binEnd: number;
      yVals: number[];
      originalValues: number[];
    }[];

    if (binningMode === 'absolute') {
      // Original absolute binning logic
      const binSize = (xMax - xMin) / binCount;
      bins = Array.from({length: binCount}, (_, i) => ({
        x: xMin + binSize * (i + 0.5),
        binStart: xMin + binSize * i,
        binEnd: xMin + binSize * (i + 1),
        yVals: [],
        originalValues: [],
      }));
    } else {
      // Time-based binning
      const timeBins = createTimeBins(xMin, xMax, binningMode);
      bins = timeBins.map(bin => ({
        x: bin.x,
        binStart: bin.binStart,
        binEnd: bin.binEnd,
        yVals: [],
        originalValues: [],
      }));
    }

    points.forEach(pt => {
      let binIndex: number;
      
      if (binningMode === 'absolute') {
        const binSize = (xMax - xMin) / binCount;
        binIndex = Math.min(
          Math.floor((pt.x - xMin) / binSize),
          binCount - 1
        );
      } else {
        // For time-based binning, find the appropriate bin
        binIndex = bins.findIndex(bin => pt.x >= bin.binStart && pt.x < bin.binEnd);
        // Handle edge case where point is exactly at the end
        if (binIndex === -1 && bins.length > 0) {
          const lastBin = bins[bins.length - 1];
          if (pt.x >= lastBin.binStart && pt.x <= lastBin.binEnd) {
            binIndex = bins.length - 1;
          }
        }
        // Fallback to first or last bin if still not found
        if (binIndex === -1) {
          if (pt.x < bins[0].binStart) {
            binIndex = 0;
          } else {
            binIndex = bins.length - 1;
          }
        }
      }
      
      if (binIndex >= 0 && binIndex < bins.length) {
        bins[binIndex].yVals.push(pt.y);
        bins[binIndex].originalValues.push(pt.y);
      }
    });

    return {
      all: bins.map(bin => ({
        x: bin.x,
        y: aggregateValues(bin.yVals, aggregation),
        originalValue:
          bin.originalValues[0] ?? aggregateValues(bin.yVals, aggregation),
        binStart: bin.binStart,
        binEnd: bin.binEnd,
      })),
    };
  }

  // Calculate global bin structure first (shared across all groups)
  const allXVals = points.map(pt => pt.x);
  const globalXMin = Math.min(...allXVals);
  const globalXMax = Math.max(...allXVals);

  if (globalXMax === globalXMin) {
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

  // Create shared bin structure based on binning mode
  let sharedBins: {
    x: number;
    binStart: number;
    binEnd: number;
    groupData: Record<string, {yVals: number[]; originalValues: number[]}>;
  }[];

  if (binningMode === 'absolute') {
    const globalBinSize = (globalXMax - globalXMin) / binCount;
    sharedBins = Array.from({length: binCount}, (_, i) => ({
      x: globalXMin + globalBinSize * (i + 0.5),
      binStart: globalXMin + globalBinSize * i,
      binEnd: globalXMin + globalBinSize * (i + 1),
      groupData: {},
    }));
  } else {
    // Time-based binning for groups
    const timeBins = createTimeBins(globalXMin, globalXMax, binningMode);
    sharedBins = timeBins.map(bin => ({
      x: bin.x,
      binStart: bin.binStart,
      binEnd: bin.binEnd,
      groupData: {},
    }));
  }

  // Assign each point to the correct global bin and group
  points.forEach(pt => {
    const group = pt.group || 'Other';
    let binIndex: number;
    
    if (binningMode === 'absolute') {
      const globalBinSize = (globalXMax - globalXMin) / binCount;
      binIndex = Math.min(
        Math.floor((pt.x - globalXMin) / globalBinSize),
        binCount - 1
      );
    } else {
      // For time-based binning, find the appropriate bin
      binIndex = sharedBins.findIndex(bin => pt.x >= bin.binStart && pt.x < bin.binEnd);
      // Handle edge case where point is exactly at the end
      if (binIndex === -1 && sharedBins.length > 0) {
        const lastBin = sharedBins[sharedBins.length - 1];
        if (pt.x >= lastBin.binStart && pt.x <= lastBin.binEnd) {
          binIndex = sharedBins.length - 1;
        }
      }
      // Fallback to first or last bin if still not found
      if (binIndex === -1) {
        if (pt.x < sharedBins[0].binStart) {
          binIndex = 0;
        } else {
          binIndex = sharedBins.length - 1;
        }
      }
    }

    if (binIndex >= 0 && binIndex < sharedBins.length) {
      if (!sharedBins[binIndex].groupData[group]) {
        sharedBins[binIndex].groupData[group] = {yVals: [], originalValues: []};
      }

      sharedBins[binIndex].groupData[group].yVals.push(pt.y);
      sharedBins[binIndex].groupData[group].originalValues.push(pt.y);
    }
  });

  // Generate output grouped by series, but all using the same x coordinates
  const grouped: Record<string, BinnedPoint[]> = {};
  const groups = Array.from(new Set(points.map(pt => pt.group || 'Other')));

  groups.forEach(group => {
    grouped[group] = sharedBins.map(bin => ({
      x: bin.x, // Same x coordinate for all groups!
      y: bin.groupData[group]
        ? aggregateValues(bin.groupData[group].yVals, aggregation)
        : NaN, // No data for this group in this bin
      originalValue: bin.groupData[group]?.originalValues[0] ?? NaN,
      binStart: bin.binStart,
      binEnd: bin.binEnd,
    }));
  });

  return grouped;
};

/**
 * Calculates bin boundaries for a given data point and bin configuration.
 *
 * Args:
 *     dataX (number): The x-coordinate of the data point.
 *     transformedPoints (Array): Array of data points.
 *     binCount (number): Number of bins to create.
 *     currentXDomain (Array): Current X domain [min, max].
 *
 * Returns:
 *     Object: Object containing binStart, binEnd, or null values if not applicable.
 *
 * Examples:
 *     >>> calculateBinBoundaries(100, points, 20, [0, 200], false)
 *     {binStart: 95, binEnd: 105}
 */
export const calculateBinBoundaries = (
  dataX: number,
  transformedPoints: Array<{x: number; y: number; group?: string}>,
  binCount: number,
  currentXDomain: [number, number]
): {binStart: number | null; binEnd: number | null} => {
  // Use the same domain-based binning logic as data processing
  const filteredXValues = transformedPoints
    .filter(pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1])
    .map(pt => pt.x);

  if (filteredXValues.length < 2) {
    return {binStart: null, binEnd: null};
  }

  const xMin = Math.min(...filteredXValues);
  const xMax = Math.max(...filteredXValues);

  if (xMax <= xMin) {
    return {binStart: null, binEnd: null};
  }

  const binSize = (xMax - xMin) / binCount;

  // Find which bin the data point falls into
  const binIndex = Math.floor((dataX - xMin) / binSize);
  const clampedBinIndex = Math.max(0, Math.min(binIndex, binCount - 1));

  // Calculate actual bin boundaries
  const binStart = xMin + binSize * clampedBinIndex;
  const binEnd = xMin + binSize * (clampedBinIndex + 1);

  return {binStart, binEnd};
};

/**
 * Creates binned data points grouped by series for chart visualization.
 *
 * Args:
 *     transformedPoints (Array): Array of data points with x, y, and group properties.
 *     binCount (number): Number of bins to create.
 *     aggregation (AggregationMethod): Method to aggregate values within bins.
 *     currentXDomain (Array): Current X domain [min, max] for filtering.
 *     dataRanges (Object): Full data ranges with xMin, xMax properties.
 *     groupKeys (string[]): Group by field names.
 *     useStackedBinning (boolean): Whether to use stacked binning logic (for bar charts).
 *
 * Returns:
 *     Object: Record of group names to arrays of binned points.
 *
 * Examples:
 *     >>> createBinnedPointsByGroup(points, 20, 'average', [0, 100], ranges, 'op_name', undefined, false)
 *     {group1: [{x: 5, y: 10, originalValue: 10}], group2: [...]}
 */
export const createBinnedPointsByGroup = (
  transformedPoints: Array<{x: number; y: number; group?: string}>,
  binCount: number,
  aggregation: AggregationMethod,
  currentXDomain: [number, number],
  dataRanges: {xMin: number; xMax: number},
  groupKeys?: string[],
  useStackedBinning: boolean = false,
  binningMode: BinningMode = 'absolute'
): Record<string, BinnedPoint[]> => {
  if (!transformedPoints || transformedPoints.length === 0) {
    return {};
  }

  // Use chart domain if available, otherwise fall back to data ranges
  const effectiveXDomain = currentXDomain || [dataRanges.xMin, dataRanges.xMax];

  // Filter points by current X domain for rebinning
  const filteredPoints = transformedPoints.filter(
    pt => pt.x >= effectiveXDomain[0] && pt.x <= effectiveXDomain[1]
  );

  // For bar charts, fall back to all points if no points in current domain
  // For line plots, use filtered points even if empty (correct behavior for zoom)
  const pointsToUse =
    useStackedBinning && filteredPoints.length === 0
      ? transformedPoints
      : filteredPoints;

  // Check if we need grouping
  const hasGrouping =
    groupKeys && groupKeys.length > 0 && pointsToUse.some(pt => pt.group);

  // For stacked bar charts with grouping, use shared x-axis bins
  if (useStackedBinning && hasGrouping) {
    const xVals = pointsToUse.map(pt => pt.x);
    const xMin = Math.min(...xVals);
    const xMax = Math.max(...xVals);

    if (xMax === xMin) {
      // All points have same x value, group them without binning
      const grouped: Record<string, BinnedPoint[]> = {};
      pointsToUse.forEach(pt => {
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

    // Create shared bins across all groups based on binning mode
    let sharedBins: {
      x: number;
      binStart: number;
      binEnd: number;
      groups: Record<string, number[]>;
    }[];

    if (binningMode === 'absolute') {
      const binSize = (xMax - xMin) / binCount;
      sharedBins = Array.from({length: binCount}, (_, i) => ({
        x: xMin + binSize * (i + 0.5),
        binStart: xMin + binSize * i,
        binEnd: xMin + binSize * (i + 1),
        groups: {},
      }));
    } else {
      // Time-based binning for stacked groups
      const timeBins = createTimeBins(xMin, xMax, binningMode);
      sharedBins = timeBins.map(bin => ({
        x: bin.x,
        binStart: bin.binStart,
        binEnd: bin.binEnd,
        groups: {},
      }));
    }

    // Assign points to shared bins
    pointsToUse.forEach(pt => {
      const group = pt.group || 'Other';
      let binIndex: number;
      
      if (binningMode === 'absolute') {
        const binSize = (xMax - xMin) / binCount;
        binIndex = Math.min(
          Math.floor((pt.x - xMin) / binSize),
          binCount - 1
        );
      } else {
        // For time-based binning, find the appropriate bin
        binIndex = sharedBins.findIndex(bin => pt.x >= bin.binStart && pt.x < bin.binEnd);
        // Handle edge case where point is exactly at the end
        if (binIndex === -1 && sharedBins.length > 0) {
          const lastBin = sharedBins[sharedBins.length - 1];
          if (pt.x >= lastBin.binStart && pt.x <= lastBin.binEnd) {
            binIndex = sharedBins.length - 1;
          }
        }
        // Fallback to first or last bin if still not found
        if (binIndex === -1) {
          if (pt.x < sharedBins[0].binStart) {
            binIndex = 0;
          } else {
            binIndex = sharedBins.length - 1;
          }
        }
      }

      if (binIndex >= 0 && binIndex < sharedBins.length) {
        if (!sharedBins[binIndex].groups[group]) {
          sharedBins[binIndex].groups[group] = [];
        }
        sharedBins[binIndex].groups[group].push(pt.y);
      }
    });

    // Aggregate values in each bin by group
    const result: Record<string, BinnedPoint[]> = {};
    const allGroups = Array.from(
      new Set(pointsToUse.map(pt => pt.group || 'Other'))
    );

    allGroups.forEach(group => {
      result[group] = sharedBins.map(bin => ({
        x: bin.x,
        y: bin.groups[group]
          ? aggregateValues(bin.groups[group], aggregation)
          : 0,
        originalValue: bin.groups[group] ? bin.groups[group][0] : 0,
        binStart: bin.binStart,
        binEnd: bin.binEnd,
      }));
    });

    return result;
  }

  // For simple binning (line plots) or non-grouped bar charts
  return binDataPoints(pointsToUse, binCount, aggregation, hasGrouping, binningMode);
};
