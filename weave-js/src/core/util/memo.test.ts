import {describe, expect, it, vi} from 'vitest';

import {
  memoizeByReference,
  memoizeByReferenceWithSize,
  memoizeWithClear,
} from './memo';

describe('memoization functions', () => {
  describe('memoizeByReference', () => {
    it('should memoize function results based on primitive arguments', () => {
      const fn = vi.fn((a: number, b: number) => a + b);
      const memoized = memoizeByReference(fn);

      // First call
      expect(memoized(1, 2)).toBe(3);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same arguments - should return cached result
      expect(memoized(1, 2)).toBe(3);
      expect(fn).toHaveBeenCalledTimes(1); // Not called again

      // Different arguments - should compute new result
      expect(memoized(2, 3)).toBe(5);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should memoize based on object reference, not value', () => {
      const fn = vi.fn((obj: {x: number}) => obj.x * 2);
      const memoized = memoizeByReference(fn);

      const obj1 = {x: 5};
      const obj2 = {x: 5}; // Same value but different reference

      // First call with obj1
      expect(memoized(obj1)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same reference - cached
      expect(memoized(obj1)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Different reference with same value - not cached
      expect(memoized(obj2)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should handle mixed primitive and object arguments', () => {
      const fn = vi.fn((str: string, obj: {n: number}, num: number) => {
        return `${str}-${obj.n}-${num}`;
      });
      const memoized = memoizeByReference(fn);

      const obj = {n: 10};

      expect(memoized('hello', obj, 5)).toBe('hello-10-5');
      expect(fn).toHaveBeenCalledTimes(1);

      // Same arguments - cached
      expect(memoized('hello', obj, 5)).toBe('hello-10-5');
      expect(fn).toHaveBeenCalledTimes(1);

      // Different string - not cached
      expect(memoized('world', obj, 5)).toBe('world-10-5');
      expect(fn).toHaveBeenCalledTimes(2);

      // Different object reference - not cached
      expect(memoized('hello', {n: 10}, 5)).toBe('hello-10-5');
      expect(fn).toHaveBeenCalledTimes(3);
    });

    it('should handle null and undefined arguments', () => {
      const fn = vi.fn((a: any, b: any) => `${a}-${b}`);
      const memoized = memoizeByReference(fn);

      expect(memoized(null, undefined)).toBe('null-undefined');
      expect(fn).toHaveBeenCalledTimes(1);

      // Same null/undefined - cached
      expect(memoized(null, undefined)).toBe('null-undefined');
      expect(fn).toHaveBeenCalledTimes(1);

      expect(memoized(undefined, null)).toBe('undefined-null');
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should handle functions as arguments', () => {
      const fn = vi.fn((f: Function, x: number) => f(x));
      const memoized = memoizeByReference(fn);

      const double = (n: number) => n * 2;
      const triple = (n: number) => n * 3;

      expect(memoized(double, 5)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same function reference - cached
      expect(memoized(double, 5)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Different function - not cached
      expect(memoized(triple, 5)).toBe(15);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should handle no arguments', () => {
      let counter = 0;
      const fn = vi.fn(() => ++counter);
      const memoized = memoizeByReference(fn);

      expect(memoized()).toBe(1);
      expect(fn).toHaveBeenCalledTimes(1);

      // Should return cached result
      expect(memoized()).toBe(1);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should maintain correct type signature', () => {
      const fn = (a: string, b: number): boolean => a.length > b;
      const memoized = memoizeByReference(fn);

      // Type checking - should compile without errors
      const result: boolean = memoized('hello', 3);
      expect(result).toBe(true);
    });
  });

  describe('memoizeByReferenceWithSize', () => {
    it('should evict least recently used entries when cache is full', () => {
      const fn = vi.fn((n: number) => n * 2);
      const memoized = memoizeByReferenceWithSize(fn, 3);

      // Fill cache
      expect(memoized(1)).toBe(2);
      expect(memoized(2)).toBe(4);
      expect(memoized(3)).toBe(6);
      expect(fn).toHaveBeenCalledTimes(3);

      // Access 1 to make it more recent
      expect(memoized(1)).toBe(2);
      expect(fn).toHaveBeenCalledTimes(3); // Still cached

      // Add new entry - should evict 2 (least recently used)
      expect(memoized(4)).toBe(8);
      expect(fn).toHaveBeenCalledTimes(4);

      // Check that 2 was evicted
      expect(memoized(2)).toBe(4);
      expect(fn).toHaveBeenCalledTimes(5); // Had to recompute

      // Check that 1 is still cached
      expect(memoized(1)).toBe(2);
      expect(fn).toHaveBeenCalledTimes(5); // Still cached
    });

    it('should handle objects with LRU cache', () => {
      const fn = vi.fn((obj: {id: number}) => obj.id * 10);
      const memoized = memoizeByReferenceWithSize(fn, 2);

      const obj1 = {id: 1};
      const obj2 = {id: 2};
      const obj3 = {id: 3};

      expect(memoized(obj1)).toBe(10);
      expect(memoized(obj2)).toBe(20);
      expect(fn).toHaveBeenCalledTimes(2);

      // obj1 should be evicted when obj3 is added
      expect(memoized(obj3)).toBe(30);
      expect(fn).toHaveBeenCalledTimes(3);

      // obj1 should no longer be cached
      expect(memoized(obj1)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(4);
    });

    it('should use default cache size of 100', () => {
      const fn = vi.fn((n: number) => n);
      const memoized = memoizeByReferenceWithSize(fn);

      // Fill cache to default size
      for (let i = 0; i < 100; i++) {
        memoized(i);
      }
      expect(fn).toHaveBeenCalledTimes(100);

      // All should still be cached
      for (let i = 0; i < 100; i++) {
        memoized(i);
      }
      expect(fn).toHaveBeenCalledTimes(100);

      // Adding one more should trigger eviction
      memoized(100);
      expect(fn).toHaveBeenCalledTimes(101);
    });

    it('should handle LRU eviction with access order', () => {
      const fn = vi.fn((n: number) => n);
      const memoized = memoizeByReferenceWithSize(fn, 2);

      memoized(1);
      memoized(2);

      // Access 1 to make it more recent
      memoized(1);

      // Add 3 - should evict 2, not 1
      memoized(3);

      // 1 should still be cached
      memoized(1);
      expect(fn).toHaveBeenCalledTimes(3); // Only 3 computations total

      // 2 should have been evicted
      memoized(2);
      expect(fn).toHaveBeenCalledTimes(4); // Had to recompute 2
    });
  });

  describe('memoizeWithClear', () => {
    it('should provide a clear method to reset cache', () => {
      const fn = vi.fn((a: number, b: number) => a + b);
      const memoized = memoizeWithClear(fn);

      // Add some cached values
      expect(memoized(1, 2)).toBe(3);
      expect(memoized(3, 4)).toBe(7);
      expect(fn).toHaveBeenCalledTimes(2);

      // Should return cached values
      expect(memoized(1, 2)).toBe(3);
      expect(memoized(3, 4)).toBe(7);
      expect(fn).toHaveBeenCalledTimes(2);

      // Clear cache
      memoized.clear();

      // Should recompute after clear
      expect(memoized(1, 2)).toBe(3);
      expect(memoized(3, 4)).toBe(7);
      expect(fn).toHaveBeenCalledTimes(4);
    });

    it('should clear cache for both primitives and objects', () => {
      const fn = vi.fn((str: string, obj: {n: number}) => `${str}-${obj.n}`);
      const memoized = memoizeWithClear(fn);

      const obj = {n: 5};

      expect(memoized('hello', obj)).toBe('hello-5');
      expect(fn).toHaveBeenCalledTimes(1);

      // Cached
      expect(memoized('hello', obj)).toBe('hello-5');
      expect(fn).toHaveBeenCalledTimes(1);

      // Clear and recompute
      memoized.clear();
      expect(memoized('hello', obj)).toBe('hello-5');
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should maintain correct type signature with clear method', () => {
      const fn = (a: string): number => a.length;
      const memoized = memoizeWithClear(fn);

      // Type checking
      const result: number = memoized('test');
      expect(result).toBe(4);

      // Clear method should be available
      memoized.clear();
    });
  });

  describe('edge cases and memory management', () => {
    it('should handle circular references in objects', () => {
      const fn = vi.fn((obj: any) => obj.value);
      const memoized = memoizeByReference(fn);

      const circular: any = {value: 42};
      circular.self = circular;

      expect(memoized(circular)).toBe(42);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same reference - cached
      expect(memoized(circular)).toBe(42);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should handle arrays as arguments', () => {
      const fn = vi.fn((arr: number[]) => arr.reduce((a, b) => a + b, 0));
      const memoized = memoizeByReference(fn);

      const arr1 = [1, 2, 3];
      const arr2 = [1, 2, 3]; // Same values, different reference

      expect(memoized(arr1)).toBe(6);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same array reference - cached
      expect(memoized(arr1)).toBe(6);
      expect(fn).toHaveBeenCalledTimes(1);

      // Different array reference - not cached
      expect(memoized(arr2)).toBe(6);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should handle complex nested structures', () => {
      const fn = vi.fn((obj: any) => JSON.stringify(obj));
      const memoized = memoizeByReference(fn);

      const complex = {
        nested: {
          array: [1, 2, {deep: true}],
          map: new Map([['key', 'value']]),
        },
      };

      const result1 = memoized(complex);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same reference - cached
      const result2 = memoized(complex);
      expect(result1).toBe(result2);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should handle Symbol arguments', () => {
      const fn = vi.fn((sym: symbol, val: number) => val);
      const memoized = memoizeByReference(fn);

      const sym1 = Symbol('test');
      const sym2 = Symbol('test'); // Different symbol

      expect(memoized(sym1, 10)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Same symbol - cached
      expect(memoized(sym1, 10)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(1);

      // Different symbol - not cached
      expect(memoized(sym2, 10)).toBe(10);
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });
});
