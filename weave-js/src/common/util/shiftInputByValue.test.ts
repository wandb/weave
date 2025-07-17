import {shiftInputByValue} from './shiftInputByValue';

describe('shiftInputByValue', () => {
  describe('with ticks and strideLength', () => {
    const ticks = [0, 10, 20, 30, 40, 50];
    const strideLength = 5;

    it('should shift up by strideLength when direction is positive', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        1,
        15,
        undefined,
        undefined
      );
      expect(result).toBe(20); // 15 + 5 = 20
    });

    it('should shift down by strideLength when direction is negative', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        -1,
        25,
        undefined,
        undefined
      );
      expect(result).toBe(20); // 25 - 5 = 20
    });

    it('should clamp to minimum tick when shift would go below', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        -1,
        5,
        undefined,
        undefined
      );
      expect(result).toBe(0); // 5 - 5 = 0, clamped to ticks[0]
    });

    it('should clamp to maximum tick when shift would go above', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        1,
        45,
        undefined,
        undefined
      );
      expect(result).toBe(50); // 45 + 5 = 50, clamped to ticks[5]
    });

    it('should handle value exactly at tick boundary', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        1,
        20,
        undefined,
        undefined
      );
      expect(result).toBe(25); // 20 + 5 = 25
    });

    it('should handle value between ticks', () => {
      const result = shiftInputByValue(
        ticks,
        strideLength,
        1,
        17,
        undefined,
        undefined
      );
      expect(result).toBe(22); // 17 + 5 = 22
    });
  });

  describe('with ticks but no strideLength', () => {
    const ticks = [0, 10, 20, 30, 40, 50];

    it('should move to next tick when direction is positive', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        15,
        undefined,
        undefined
      );
      expect(result).toBe(30); // _.sortedIndex(15) = 2, 2 + 1 = 3, ticks[3] = 30
    });

    it('should move to previous tick when direction is negative', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        -1,
        25,
        undefined,
        undefined
      );
      expect(result).toBe(20); // _.sortedIndex(25) = 3, 3 - 1 = 2, ticks[2] = 20
    });

    it('should stay at first tick when moving down from first tick', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        -1,
        0,
        undefined,
        undefined
      );
      expect(result).toBe(0); // already at first tick
    });

    it('should stay at last tick when moving up from last tick', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        50,
        undefined,
        undefined
      );
      expect(result).toBe(50); // already at last tick
    });

    it('should handle value exactly at a tick', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        20,
        undefined,
        undefined
      );
      expect(result).toBe(30); // next tick after 20
    });

    it('should handle value between ticks', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        17,
        undefined,
        undefined
      );
      expect(result).toBe(30); // _.sortedIndex(17) = 2, 2 + 1 = 3, ticks[3] = 30
    });

    it('should handle value between ticks going backward', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        -1,
        17,
        undefined,
        undefined
      );
      expect(result).toBe(10); // previous tick before 17
    });

    it('should handle value below first tick', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        -5,
        undefined,
        undefined
      );
      expect(result).toBe(10); // _.sortedIndex(-5) = 0, 0 + 1 = 1, ticks[1] = 10
    });

    it('should handle value above last tick', () => {
      const result = shiftInputByValue(
        ticks,
        undefined,
        -1,
        55,
        undefined,
        undefined
      );
      expect(result).toBe(50); // last tick
    });
  });

  describe('without ticks', () => {
    it('should shift by strideLength when provided', () => {
      const result = shiftInputByValue(undefined, 5, 1, 10, 0, 20);
      expect(result).toBe(15); // 10 + 5 = 15
    });

    it('should shift by 1 when no strideLength provided', () => {
      const result = shiftInputByValue(undefined, undefined, 1, 10, 0, 20);
      expect(result).toBe(11); // 10 + 1 = 11
    });

    it('should shift down by strideLength', () => {
      const result = shiftInputByValue(undefined, 3, -1, 10, 0, 20);
      expect(result).toBe(7); // 10 - 3 = 7
    });

    it('should clamp to minimum when shift would go below', () => {
      const result = shiftInputByValue(undefined, 5, -1, 3, 0, 20);
      expect(result).toBe(0); // 3 - 5 = -2, clamped to 0
    });

    it('should clamp to maximum when shift would go above', () => {
      const result = shiftInputByValue(undefined, 5, 1, 18, 0, 20);
      expect(result).toBe(20); // 18 + 5 = 23, clamped to 20
    });

    it('should handle undefined min and max', () => {
      const result = shiftInputByValue(
        undefined,
        5,
        1,
        10,
        undefined,
        undefined
      );
      expect(result).toBe(15); // 10 + 5 = 15, no clamping
    });

    it('should handle undefined min only', () => {
      const result = shiftInputByValue(undefined, 5, 1, 10, undefined, 20);
      expect(result).toBe(15); // 10 + 5 = 15, only max clamping
    });

    it('should handle undefined max only', () => {
      const result = shiftInputByValue(undefined, 5, -1, 10, 0, undefined);
      expect(result).toBe(5); // 10 - 5 = 5, only min clamping
    });

    it('should handle zero direction', () => {
      const result = shiftInputByValue(undefined, 5, 0, 10, 0, 20);
      expect(result).toBe(10); // 10 + 0 = 10
    });
  });

  describe('edge cases', () => {
    it('should handle empty ticks array', () => {
      const result = shiftInputByValue([], 5, 1, 10, 0, 20);
      expect(result).toBe(15); // falls back to no-ticks behavior
    });

    it('should handle single tick', () => {
      const result = shiftInputByValue(
        [5],
        undefined,
        1,
        5,
        undefined,
        undefined
      );
      expect(result).toBe(5); // stays at the only tick
    });

    it('should handle single tick with strideLength', () => {
      const result = shiftInputByValue([5], 3, 1, 5, undefined, undefined);
      expect(result).toBe(5); // 5 + 3 = 8, but clamped to 5
    });

    it('should handle unsorted ticks', () => {
      const unsortedTicks = [30, 10, 50, 20, 0, 40];
      const result = shiftInputByValue(
        unsortedTicks,
        undefined,
        1,
        15,
        undefined,
        undefined
      );
      // Should work with lodash sortedIndex which handles unsorted arrays
      expect(result).toBe(20);
    });

    it('should handle NaN value', () => {
      const result = shiftInputByValue(undefined, 5, 1, NaN, 0, 20);
      expect(result).toBe(NaN); // NaN + 5 = NaN
    });

    it('should handle Infinity value', () => {
      const result = shiftInputByValue(undefined, 5, 1, Infinity, 0, 20);
      expect(result).toBe(20); // Infinity + 5 = Infinity, clamped to 20
    });

    it('should handle -Infinity value', () => {
      const result = shiftInputByValue(undefined, 5, -1, -Infinity, 0, 20);
      expect(result).toBe(0); // -Infinity - 5 = -Infinity, clamped to 0
    });

    it('should handle very large direction values', () => {
      const result = shiftInputByValue(undefined, 1, 1000, 10, 0, 20);
      expect(result).toBe(20); // 10 + 1000 = 1010, clamped to 20
    });

    it('should handle very small direction values', () => {
      const result = shiftInputByValue(undefined, 1, -1000, 10, 0, 20);
      expect(result).toBe(0); // 10 - 1000 = -990, clamped to 0
    });
  });

  describe('real-world scenarios', () => {
    it('should work like a typical slider with step=1', () => {
      const ticks = [0, 1, 2, 3, 4, 5];
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        2,
        undefined,
        undefined
      );
      expect(result).toBe(3);
    });

    it('should work like a slider with custom step', () => {
      const result = shiftInputByValue(undefined, 0.1, 1, 1.5, 0, 2);
      expect(result).toBe(1.6);
    });

    it('should work like a percentage slider', () => {
      const ticks = [0, 25, 50, 75, 100];
      const result = shiftInputByValue(
        ticks,
        undefined,
        1,
        30,
        undefined,
        undefined
      );
      expect(result).toBe(75); // _.sortedIndex(30) = 2, 2 + 1 = 3, ticks[3] = 75
    });

    it('should work like a temperature slider with stride', () => {
      const result = shiftInputByValue(undefined, 5, 1, 20, -10, 40);
      expect(result).toBe(25);
    });
  });
});
