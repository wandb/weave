/**
 * Unit tests for aggregation.ts
 *
 * Tests the aggregation, binning, and data processing logic used for line plots and bar charts.
 */

import {describe, expect, it} from 'vitest';

import {
  aggregateValues,
  binDataPoints,
  calculateBinBoundaries,
  createBinnedPointsByGroup,
} from '../aggregation';
import {AggregationMethod, DataPoint} from '../types';

describe('aggregation', () => {
  describe('aggregateValues', () => {
    it('should calculate average correctly', () => {
      expect(aggregateValues([1, 2, 3, 4, 5], 'average')).toBe(3);
      expect(aggregateValues([10, 20, 30], 'average')).toBe(20);
      expect(aggregateValues([0], 'average')).toBe(0);
    });

    it('should calculate sum correctly', () => {
      expect(aggregateValues([1, 2, 3, 4, 5], 'sum')).toBe(15);
      expect(aggregateValues([10, 20, 30], 'sum')).toBe(60);
      expect(aggregateValues([0], 'sum')).toBe(0);
      expect(aggregateValues([-5, 5], 'sum')).toBe(0);
    });

    it('should calculate min correctly', () => {
      expect(aggregateValues([1, 2, 3, 4, 5], 'min')).toBe(1);
      expect(aggregateValues([30, 10, 20], 'min')).toBe(10);
      expect(aggregateValues([42], 'min')).toBe(42);
      expect(aggregateValues([-10, -5, -15], 'min')).toBe(-15);
    });

    it('should calculate max correctly', () => {
      expect(aggregateValues([1, 2, 3, 4, 5], 'max')).toBe(5);
      expect(aggregateValues([30, 10, 20], 'max')).toBe(30);
      expect(aggregateValues([42], 'max')).toBe(42);
      expect(aggregateValues([-10, -5, -15], 'max')).toBe(-5);
    });

    it('should calculate p95 correctly', () => {
      // Test with 100 values (0-99)
      const values = Array.from({length: 100}, (_, i) => i);
      expect(aggregateValues(values, 'p95')).toBe(94); // 95th percentile of 0-99 is 94

      // Test with smaller arrays
      expect(aggregateValues([1, 2, 3, 4, 5], 'p95')).toBe(4); // 95th percentile of [1,2,3,4,5] is 4
      expect(aggregateValues([10, 20, 30, 40, 50], 'p95')).toBe(40); // 95th percentile of [10,20,30,40,50] is 40
    });

    it('should calculate p99 correctly', () => {
      // Test with 100 values (0-99)
      const values = Array.from({length: 100}, (_, i) => i);
      expect(aggregateValues(values, 'p99')).toBe(98); // 99th percentile of 0-99 is 98

      // Test with smaller arrays
      expect(aggregateValues([1, 2, 3, 4, 5], 'p99')).toBe(4); // 99th percentile of [1,2,3,4,5] is 4
      expect(aggregateValues([10, 20, 30, 40, 50], 'p99')).toBe(40); // 99th percentile of [10,20,30,40,50] is 40
    });

    it('should return NaN for empty arrays', () => {
      expect(aggregateValues([], 'average')).toBeNaN();
      expect(aggregateValues([], 'sum')).toBeNaN();
      expect(aggregateValues([], 'min')).toBeNaN();
      expect(aggregateValues([], 'max')).toBeNaN();
      expect(aggregateValues([], 'p95')).toBeNaN();
      expect(aggregateValues([], 'p99')).toBeNaN();
    });

    it('should default to average for unknown aggregation methods', () => {
      expect(aggregateValues([1, 2, 3], 'unknown' as AggregationMethod)).toBe(
        2
      );
    });

    it('should handle floating point numbers correctly', () => {
      expect(aggregateValues([1.1, 2.2, 3.3], 'average')).toBeCloseTo(2.2, 10);
      expect(aggregateValues([1.5, 2.5, 3.5], 'sum')).toBeCloseTo(7.5, 10);
    });
  });

  describe('binDataPoints', () => {
    const mockPoints: DataPoint[] = [
      {x: 0, y: 10},
      {x: 1, y: 20},
      {x: 2, y: 30},
      {x: 3, y: 40},
      {x: 4, y: 50},
    ];

    it('should return original points when binCount is 0 or invalid', () => {
      const result = binDataPoints(mockPoints, 0, 'average', false);

      expect(result.all).toHaveLength(5);
      expect(result.all[0]).toEqual({
        x: 0,
        y: 10,
        originalValue: 10,
      });
      expect(result.all[4]).toEqual({
        x: 4,
        y: 50,
        originalValue: 50,
      });
    });

    it('should return original points when points array is empty', () => {
      const result = binDataPoints([], 10, 'average', false);

      expect(result).toEqual({all: []});
    });

    it('should bin data points without grouping', () => {
      const result = binDataPoints(mockPoints, 2, 'average', false);

      expect(result.all).toHaveLength(2);

      // First bin contains points with x values 0, 1
      expect(result.all[0].x).toBeCloseTo(1, 1);
      expect(result.all[0].y).toBeCloseTo(15, 1); // Average of 10, 20

      // Second bin contains points with x values 2, 3, 4
      expect(result.all[1].x).toBeCloseTo(3, 1);
      expect(result.all[1].y).toBeCloseTo(40, 1); // Average of 30, 40, 50
    });

    it('should handle identical x values', () => {
      const sameXPoints: DataPoint[] = [
        {x: 5, y: 10},
        {x: 5, y: 20},
        {x: 5, y: 30},
      ];

      const result = binDataPoints(sameXPoints, 5, 'average', false);

      expect(result.all).toHaveLength(3);
      expect(result.all[0]).toEqual({x: 5, y: 10, originalValue: 10});
    });

    it('should bin data points with grouping', () => {
      const groupedPoints: DataPoint[] = [
        {x: 0, y: 10, group: 'A'},
        {x: 1, y: 20, group: 'A'},
        {x: 2, y: 30, group: 'B'},
        {x: 3, y: 40, group: 'B'},
      ];

      const result = binDataPoints(groupedPoints, 2, 'average', true);

      expect(Object.keys(result)).toEqual(['A', 'B']);
      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);
    });

    it('should use different aggregation methods correctly', () => {
      const testPoints: DataPoint[] = [
        {x: 0, y: 10},
        {x: 0.5, y: 20},
        {x: 1, y: 30},
      ];

      const avgResult = binDataPoints(testPoints, 1, 'average', false);
      const sumResult = binDataPoints(testPoints, 1, 'sum', false);
      const maxResult = binDataPoints(testPoints, 1, 'max', false);

      expect(avgResult.all[0].y).toBeCloseTo(20, 1); // (10+20+30)/3
      expect(sumResult.all[0].y).toBeCloseTo(60, 1); // 10+20+30
      expect(maxResult.all[0].y).toBeCloseTo(30, 1); // max(10,20,30)
    });

    it('should handle groups with shared bins correctly', () => {
      const groupedPoints: DataPoint[] = [
        {x: 0, y: 10, group: 'A'},
        {x: 0, y: 15, group: 'B'},
        {x: 1, y: 20, group: 'A'},
        {x: 1, y: 25, group: 'B'},
        {x: 2, y: 30, group: 'A'},
        {x: 2, y: 35, group: 'B'},
      ];

      const result = binDataPoints(groupedPoints, 2, 'average', true);

      expect(Object.keys(result).sort()).toEqual(['A', 'B']);

      // Both groups should have same number of bins
      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);

      // Check that bins are aligned (same x coordinates)
      expect(result.A[0].x).toBeCloseTo(result.B[0].x, 5);
      expect(result.A[1].x).toBeCloseTo(result.B[1].x, 5);
    });

    it('should handle points without groups when useGroups is true', () => {
      const mixedPoints: DataPoint[] = [
        {x: 0, y: 10, group: 'A'},
        {x: 1, y: 20}, // No group
        {x: 2, y: 30, group: 'A'},
      ];

      const result = binDataPoints(mixedPoints, 2, 'average', true);

      expect(Object.keys(result).sort()).toEqual(['A', 'Other']);
    });
  });

  describe('calculateBinBoundaries', () => {
    const mockPoints = [
      {x: 0, y: 10},
      {x: 10, y: 20},
      {x: 20, y: 30},
      {x: 30, y: 40},
      {x: 40, y: 50},
    ];

    it('should calculate correct bin boundaries for data point in middle', () => {
      const result = calculateBinBoundaries(15, mockPoints, 4, [0, 40]);

      expect(result.binStart).toBeCloseTo(10, 1);
      expect(result.binEnd).toBeCloseTo(20, 1);
    });

    it('should calculate correct bin boundaries for data point at start', () => {
      const result = calculateBinBoundaries(5, mockPoints, 4, [0, 40]);

      expect(result.binStart).toBeCloseTo(0, 1);
      expect(result.binEnd).toBeCloseTo(10, 1);
    });

    it('should calculate correct bin boundaries for data point at end', () => {
      const result = calculateBinBoundaries(35, mockPoints, 4, [0, 40]);

      expect(result.binStart).toBeCloseTo(30, 1);
      expect(result.binEnd).toBeCloseTo(40, 1);
    });

    it('should handle edge case with data point outside domain', () => {
      const result = calculateBinBoundaries(50, mockPoints, 4, [0, 40]);

      // Should clamp to last bin
      expect(result.binStart).toBeCloseTo(30, 1);
      expect(result.binEnd).toBeCloseTo(40, 1);
    });

    it('should return null boundaries when insufficient data', () => {
      const result = calculateBinBoundaries(15, [{x: 5, y: 10}], 4, [0, 40]);

      expect(result.binStart).toBe(null);
      expect(result.binEnd).toBe(null);
    });

    it('should return null boundaries when xMax equals xMin', () => {
      const sameXPoints = [
        {x: 10, y: 20},
        {x: 10, y: 30},
        {x: 10, y: 40},
      ];

      const result = calculateBinBoundaries(10, sameXPoints, 4, [5, 15]);

      expect(result.binStart).toBe(null);
      expect(result.binEnd).toBe(null);
    });

    it('should filter points by domain correctly', () => {
      const wideRangePoints = [
        {x: -10, y: 10},
        {x: 5, y: 20},
        {x: 15, y: 30},
        {x: 25, y: 40},
        {x: 50, y: 50},
      ];

      // Only points at x=5, 15, 25 should be considered (within domain [0, 30])
      const result = calculateBinBoundaries(20, wideRangePoints, 3, [0, 30]);

      expect(result.binStart).not.toBe(null);
      expect(result.binEnd).not.toBe(null);
    });
  });

  describe('createBinnedPointsByGroup', () => {
    const mockPoints = [
      {x: 0, y: 10, group: 'A'},
      {x: 5, y: 20, group: 'A'},
      {x: 10, y: 30, group: 'B'},
      {x: 15, y: 40, group: 'B'},
      {x: 20, y: 50, group: 'A'},
    ];

    const mockDataRanges = {xMin: 0, xMax: 20};

    it('should return empty object for empty points array', () => {
      const result = createBinnedPointsByGroup(
        [],
        5,
        'average',
        [0, 20],
        mockDataRanges,
        ['group']
      );

      expect(result).toEqual({});
    });

    it('should create bins without grouping when no groupKeys provided', () => {
      const result = createBinnedPointsByGroup(
        mockPoints,
        2,
        'average',
        [0, 20],
        mockDataRanges
      );

      expect(Object.keys(result)).toContain('all');
      expect(result.all).toHaveLength(2);
    });

    it('should create bins with grouping when groupKeys provided', () => {
      const result = createBinnedPointsByGroup(
        mockPoints,
        2,
        'average',
        [0, 20],
        mockDataRanges,
        ['group']
      );

      expect(Object.keys(result).sort()).toEqual(['A', 'B']);
      expect(result.A).toHaveLength(2);
      expect(result.B).toHaveLength(2);
    });

    it('should use stacked binning for bar charts', () => {
      const result = createBinnedPointsByGroup(
        mockPoints,
        2,
        'sum',
        [0, 20],
        mockDataRanges,
        ['group'],
        true // useStackedBinning
      );

      expect(Object.keys(result).sort()).toEqual(['A', 'B']);

      // All groups should have same x coordinates (shared bins)
      expect(result.A[0].x).toBeCloseTo(result.B[0].x, 5);
      expect(result.A[1].x).toBeCloseTo(result.B[1].x, 5);
    });

    it('should filter points by current domain', () => {
      const result = createBinnedPointsByGroup(
        mockPoints,
        2,
        'average',
        [5, 15], // Narrow domain
        mockDataRanges,
        ['group']
      );

      // Should only include points with x in [5, 15]
      expect(Object.keys(result).sort()).toEqual(['A', 'B']);
    });

    it('should fallback to all points for bar charts when no points in domain', () => {
      const result = createBinnedPointsByGroup(
        mockPoints,
        2,
        'average',
        [100, 200], // Domain with no points
        mockDataRanges,
        ['group'],
        true // useStackedBinning
      );

      // Should fallback to using all points
      expect(Object.keys(result).sort()).toEqual(['A', 'B']);
      expect(result.A.length).toBeGreaterThan(0);
      expect(result.B.length).toBeGreaterThan(0);
    });

    it('should handle points with same x value in stacked binning', () => {
      const sameXPoints = [
        {x: 10, y: 15, group: 'A'},
        {x: 10, y: 25, group: 'B'},
        {x: 10, y: 35, group: 'A'},
      ];

      const result = createBinnedPointsByGroup(
        sameXPoints,
        2,
        'average',
        [5, 15],
        {xMin: 5, xMax: 15},
        ['group'],
        true
      );

      expect(Object.keys(result).sort()).toEqual(['A', 'B']);
      expect(result.A[0]).toEqual({x: 10, y: 15, originalValue: 15}); // Average of 15, 35
      expect(result.B[0]).toEqual({x: 10, y: 25, originalValue: 25});
    });

    it('should use correct aggregation methods', () => {
      const testPoints = [
        {x: 0, y: 10, group: 'A'},
        {x: 1, y: 20, group: 'A'},
        {x: 2, y: 30, group: 'A'},
      ];

      const avgResult = createBinnedPointsByGroup(
        testPoints,
        1,
        'average',
        [0, 3],
        {xMin: 0, xMax: 3},
        ['group']
      );

      const sumResult = createBinnedPointsByGroup(
        testPoints,
        1,
        'sum',
        [0, 3],
        {xMin: 0, xMax: 3},
        ['group']
      );

      expect(avgResult.A[0].y).toBeCloseTo(20, 1); // (10+20+30)/3
      expect(sumResult.A[0].y).toBeCloseTo(60, 1); // 10+20+30
    });

    it('should handle groups without data in bins correctly', () => {
      const sparsePoints = [
        {x: 0, y: 10, group: 'A'},
        {x: 20, y: 30, group: 'B'}, // Different bin
      ];

      const result = createBinnedPointsByGroup(
        sparsePoints,
        2,
        'average',
        [0, 20],
        {xMin: 0, xMax: 20},
        ['group'],
        true
      );

      expect(Object.keys(result).sort()).toEqual(['A', 'B']);

      // Group A should have data in first bin, NaN in second
      expect(result.A[0].y).toBe(10);
      expect(result.A[1].y).toBe(0);

      // Group B should have NaN in first bin, data in second
      expect(result.B[0].y).toBe(0);
      expect(result.B[1].y).toBe(30);
    });
  });
});
