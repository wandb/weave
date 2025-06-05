import {AggregationMethod, BinnedPoint, DataPoint} from './chartFormatting';

export const getAxisDomain = (): ['auto', 'auto'] => ['auto', 'auto'];

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

export const binDataPoints = (
  points: DataPoint[],
  binCount: number = 20,
  aggregation: AggregationMethod = 'average',
  useGroups: boolean = false
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

    const binSize = (xMax - xMin) / binCount;
    const bins: {x: number; yVals: number[]; originalValues: number[]}[] =
      Array.from({length: binCount}, (_, i) => ({
        x: xMin + binSize * (i + 0.5),
        yVals: [],
        originalValues: [],
      }));

    points.forEach(pt => {
      const binIndex = Math.min(
        Math.floor((pt.x - xMin) / binSize),
        binCount - 1
      );
      bins[binIndex].yVals.push(pt.y);
      bins[binIndex].originalValues.push(pt.y);
    });

    return {
      all: bins.map(bin => ({
        x: bin.x,
        y: aggregateValues(bin.yVals, aggregation),
        originalValue:
          bin.originalValues[0] ?? aggregateValues(bin.yVals, aggregation),
      })),
    };
  }

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

    groupPoints.forEach(pt => {
      const binIndex = Math.min(
        Math.floor((pt.x - xMin) / binSize),
        binCount - 1
      );
      bins[binIndex].yVals.push(pt.y);
      bins[binIndex].originalValues.push(pt.y);
    });

    grouped[group] = bins.map(bin => ({
      x: bin.x,
      y: aggregateValues(bin.yVals, aggregation),
      originalValue:
        bin.originalValues[0] ?? aggregateValues(bin.yVals, aggregation),
    }));
  });

  return grouped;
};
