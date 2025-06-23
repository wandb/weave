import {describe, expect, it} from 'vitest';

import {
  aggregateValues,
  binDataPoints,
  calculateBinBoundaries,
  createBinnedPointsByGroup,
} from './aggregation';
import {DataPoint} from './types';

describe('aggregateValues', () => {
  describe('basic functionality', () => {
    it('returns NaN for empty array', () => {
      expect(aggregateValues([])).toBeNaN();
      expect(aggregateValues([], 'sum')).toBeNaN();
    });

    it('calculates sum correctly', () => {
      expect(aggregateValues([1, 2, 3, 4, 5], 'sum')).toBe(15);
      expect(aggregateValues([-1, -2, -3], 'sum')).toBe(-6);
      expect(aggregateValues([1.5, 2.5], 'sum')).toBe(4);
    });

    it('finds min and max correctly', () => {
      const values = [5, 2, 8, 1, 9];
      expect(aggregateValues(values, 'min')).toBe(1);
      expect(aggregateValues(values, 'max')).toBe(9);
    });

    it('calculates percentiles correctly', () => {
      const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      expect(aggregateValues(values, 'p95')).toBe(9);
      expect(aggregateValues(values, 'p99')).toBe(9);
    });

    it('calculates average correctly (default)', () => {
      expect(aggregateValues([1, 2, 3, 4, 5])).toBe(3);
      expect(aggregateValues([1, 2, 3, 4, 5], 'average')).toBe(3);
      expect(aggregateValues([-2, -4, -6])).toBe(-4);
    });
  });
});

describe('binDataPoints', () => {
  const samplePoints: DataPoint[] = [
    {x: 1, y: 10},
    {x: 2, y: 20},
    {x: 3, y: 30},
    {x: 4, y: 40},
    {x: 5, y: 50},
  ];

  const groupedPoints: DataPoint[] = [
    {x: 1, y: 10, group: 'A'},
    {x: 2, y: 20, group: 'A'},
    {x: 3, y: 30, group: 'B'},
    {x: 4, y: 40, group: 'B'},
    {x: 5, y: 50, group: 'A'},
  ];

  describe('basic functionality', () => {
    it('returns empty result for empty points', () => {
      expect(binDataPoints([], 10)).toEqual({all: []});
      expect(binDataPoints([], 10, 'average', true)).toEqual({});
    });

    it('returns unbinned points for invalid binCount', () => {
      const result = binDataPoints(samplePoints, 0);
      expect(result.all).toHaveLength(5);
      expect(result.all[0]).toEqual({x: 1, y: 10, originalValue: 10});
    });

    it('bins points correctly without groups', () => {
      const result = binDataPoints(samplePoints, 2);
      expect(result.all).toHaveLength(2);
      expect(result.all[0].x).toBeCloseTo(2);
      expect(result.all[1].x).toBeCloseTo(4);
    });

    it('applies different aggregation methods', () => {
      const points: DataPoint[] = [
        {x: 1, y: 10},
        {x: 1.1, y: 20},
        {x: 2, y: 30},
        {x: 2.1, y: 40},
      ];

      const sumResult = binDataPoints(points, 2, 'sum');
      const avgResult = binDataPoints(points, 2, 'average');
      const maxResult = binDataPoints(points, 2, 'max');

      expect(sumResult.all[0].y).toBe(30); // 10 + 20
      expect(avgResult.all[0].y).toBe(15); // (10 + 20) / 2
      expect(maxResult.all[0].y).toBe(20); // max(10, 20)
    });
  });

  describe('with groups', () => {
    it('bins points by group with shared x coordinates', () => {
      const result = binDataPoints(groupedPoints, 2, 'average', true);

      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);

      // Both groups should have the same x coordinates
      expect(result.A[0].x).toBeCloseTo(result.B[0].x);
      expect(result.A[1].x).toBeCloseTo(result.B[1].x);
    });

    it('handles groups with no data in some bins', () => {
      const sparsePoints: DataPoint[] = [
        {x: 1, y: 10, group: 'A'},
        {x: 5, y: 50, group: 'B'},
      ];

      const result = binDataPoints(sparsePoints, 2, 'average', true);

      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);
      expect(result.A[1].y).toBeNaN();
      expect(result.B[0].y).toBeNaN();
    });

    it('handles identical x values with groups', () => {
      const identicalPoints: DataPoint[] = [
        {x: 5, y: 10, group: 'A'},
        {x: 5, y: 20, group: 'B'},
        {x: 5, y: 30, group: 'A'},
      ];

      const result = binDataPoints(identicalPoints, 10, 'average', true);
      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(1);
      expect(result.A[0].x).toBeCloseTo(5);
      expect(result.B[0].x).toBeCloseTo(5);
    });
  });
});

describe('calculateBinBoundaries', () => {
  const samplePoints = [
    {x: 0, y: 10},
    {x: 10, y: 20},
    {x: 20, y: 30},
    {x: 30, y: 40},
  ];

  describe('basic functionality', () => {
    it('returns exact boundaries for prediction index', () => {
      const result = calculateBinBoundaries(15, samplePoints, 4, [0, 30], true);
      expect(result).toEqual({binStart: 15, binEnd: 15});
    });

    it('calculates bin boundaries correctly for regular plots', () => {
      const result = calculateBinBoundaries(15, samplePoints, 4, [0, 30]);
      expect(result.binStart).toBeCloseTo(15);
      expect(result.binEnd).toBeCloseTo(22.5);
    });

    it('handles edge cases', () => {
      // Insufficient points
      const result1 = calculateBinBoundaries(5, [{x: 5, y: 10}], 4, [0, 10]);
      expect(result1).toEqual({binStart: null, binEnd: null});

      // No range (xMax === xMin)
      const identicalPoints = [
        {x: 5, y: 10},
        {x: 5, y: 20},
      ];
      const result2 = calculateBinBoundaries(5, identicalPoints, 4, [0, 10]);
      expect(result2).toEqual({binStart: null, binEnd: null});
    });

    it('clamps bin index to valid range', () => {
      const result = calculateBinBoundaries(-10, samplePoints, 4, [0, 30]);
      expect(result.binStart).toBeCloseTo(0);
      expect(result.binEnd).toBeCloseTo(7.5);
    });
  });
});

describe('createBinnedPointsByGroup', () => {
  const samplePoints = [
    {x: 1, y: 10, group: 'A'},
    {x: 2, y: 20, group: 'A'},
    {x: 3, y: 30, group: 'B'},
    {x: 4, y: 40, group: 'B'},
    {x: 5, y: 50, group: 'A'},
  ];

  describe('basic functionality', () => {
    it('returns empty result for empty points', () => {
      const result = createBinnedPointsByGroup([], 10, 'average', [0, 10], {
        xMin: 0,
        xMax: 10,
      });
      expect(result).toEqual({});
    });

    it('creates single group when no groupBy specified', () => {
      const ungroupedPoints = samplePoints.map(p => ({x: p.x, y: p.y}));
      const result = createBinnedPointsByGroup(
        ungroupedPoints,
        2,
        'average',
        [1, 5],
        {xMin: 1, xMax: 5}
      );

      expect(result.all).toBeDefined();
      expect(result.all).toHaveLength(2);
    });

    it('creates separate groups with shared x coordinates', () => {
      const result = createBinnedPointsByGroup(
        samplePoints,
        2,
        'average',
        [1, 5],
        {xMin: 1, xMax: 5},
        'group'
      );

      expect(result.A).toBeDefined();
      expect(result.B).toBeDefined();
      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);

      // Check shared x coordinates
      expect(result.A[0].x).toBeCloseTo(result.B[0].x);
      expect(result.A[1].x).toBeCloseTo(result.B[1].x);
    });
  });

  describe('stacked binning', () => {
    it('uses shared bins for stacked bar charts', () => {
      const result = createBinnedPointsByGroup(
        samplePoints,
        2,
        'sum',
        [1, 5],
        {xMin: 1, xMax: 5},
        'group',
        'group',
        true
      );

      expect(result.A).toBeDefined();
      expect(result.B).toBeDefined();
      expect(result.A[0].x).toBeCloseTo(result.B[0].x);
      expect(result.A[1].x).toBeCloseTo(result.B[1].x);
    });

    it('falls back to all points when filtered points is empty', () => {
      const result = createBinnedPointsByGroup(
        samplePoints,
        2,
        'average',
        [10, 20], // Domain with no points
        {xMin: 1, xMax: 5},
        'group',
        'group',
        true
      );

      expect(result.A).toBeDefined();
      expect(result.B).toBeDefined();
    });
  });

  describe('aggregation methods', () => {
    const testPoints = [
      {x: 1, y: 10, group: 'A'},
      {x: 1.1, y: 20, group: 'A'},
      {x: 2, y: 30, group: 'A'},
    ];

    it('applies different aggregation methods correctly', () => {
      const sumResult = createBinnedPointsByGroup(
        testPoints,
        2,
        'sum',
        [1, 2],
        {xMin: 1, xMax: 2},
        'group'
      );

      const maxResult = createBinnedPointsByGroup(
        testPoints,
        2,
        'max',
        [1, 2],
        {xMin: 1, xMax: 2},
        'group'
      );

      expect(sumResult.A[0].y).toBe(30); // 10 + 20
      expect(maxResult.A[0].y).toBe(20); // max(10, 20)
    });
  });
});
