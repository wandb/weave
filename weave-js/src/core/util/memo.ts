/**
 * Creates a memoized version of a function that caches results based on argument references.
 *
 * Args:
 *     fn: The function to memoize
 *
 * Returns:
 *     A memoized version of the input function
 *
 * Examples:
 *     const expensive = (a: any, b: any) => { console.log('computing'); return a + b; };
 *     const memoized = memoizeByReference(expensive);
 *     memoized(1, 2); // logs 'computing', returns 3
 *     memoized(1, 2); // returns 3 (cached)
 *
 *     const obj = { x: 1 };
 *     const memoizedWithObj = memoizeByReference((o: any) => o.x * 2);
 *     memoizedWithObj(obj); // returns 2
 *     memoizedWithObj(obj); // returns 2 (cached by reference)
 *     memoizedWithObj({ x: 1 }); // computes again (different reference)
 */
export function memoizeByReference<T extends (...args: any[]) => any>(
  fn: T
): T {
  // Cache structure to handle mixed primitive and reference arguments
  type CacheNode = {
    weakMap?: WeakMap<any, any>;
    primitiveMap?: Map<string, any>;
    result?: any;
    // hasResult is needed to distinguish between "not cached" and "cached undefined"
    // Without it, we couldn't cache functions that return undefined/null/false/0/""
    hasResult?: boolean;
  };

  const rootCache: CacheNode = {};

  return ((...args: Parameters<T>): ReturnType<T> => {
    let currentNode: CacheNode = rootCache;

    // Navigate through arguments to find/create cache entry
    for (let i = 0; i < args.length; i++) {
      const arg = args[i];
      const isLastArg = i === args.length - 1;

      if (
        arg !== null &&
        (typeof arg === 'object' ||
          typeof arg === 'function' ||
          typeof arg === 'symbol')
      ) {
        // Handle objects, functions, and symbols with WeakMap
        if (!currentNode.weakMap) {
          currentNode.weakMap = new WeakMap();
        }

        if (isLastArg) {
          if (currentNode.weakMap.has(arg)) {
            return currentNode.weakMap.get(arg);
          }
          const result = fn(...args);
          currentNode.weakMap.set(arg, result);
          return result;
        } else {
          if (!currentNode.weakMap.has(arg)) {
            currentNode.weakMap.set(arg, {});
          }
          currentNode = currentNode.weakMap.get(arg);
        }
      } else {
        // Handle primitives including null and undefined
        const key = String(arg) + ':' + typeof arg;

        if (!currentNode.primitiveMap) {
          currentNode.primitiveMap = new Map();
        }

        if (isLastArg) {
          if (currentNode.primitiveMap.has(key)) {
            return currentNode.primitiveMap.get(key);
          }
          const result = fn(...args);
          currentNode.primitiveMap.set(key, result);
          return result;
        } else {
          if (!currentNode.primitiveMap.has(key)) {
            currentNode.primitiveMap.set(key, {});
          }
          currentNode = currentNode.primitiveMap.get(key);
        }
      }
    }

    // Handle no arguments case
    if (args.length === 0) {
      if (currentNode.hasResult) {
        return currentNode.result;
      }
      const result = fn(...args);
      currentNode.result = result;
      currentNode.hasResult = true;
      return result;
    }

    // Should not reach here
    return fn(...args);
  }) as T;
}

/**
 * Creates a memoized version with configurable cache size.
 *
 * Args:
 *     fn: The function to memoize
 *     maxSize: Maximum number of cached results (default: 100)
 *
 * Returns:
 *     A memoized version with LRU cache behavior
 *
 * Examples:
 *     const memoized = memoizeByReferenceWithSize((x: number) => x * 2, 2);
 *     memoized(1); // computes and caches
 *     memoized(2); // computes and caches
 *     memoized(3); // computes and caches, evicts result for 1
 *     memoized(1); // computes again (was evicted)
 */
export function memoizeByReferenceWithSize<T extends (...args: any[]) => any>(
  fn: T,
  maxSize: number = 100
): T {
  const cache = new Map<string, {value: any; accessOrder: number}>();
  const argRefs = new WeakMap<any, string>();
  let keyCounter = 0;
  let accessCounter = 0;

  return ((...args: Parameters<T>): ReturnType<T> => {
    // Build cache key from argument references
    const keyParts: string[] = [];

    for (const arg of args) {
      if (
        arg !== null &&
        (typeof arg === 'object' ||
          typeof arg === 'function' ||
          typeof arg === 'symbol')
      ) {
        if (!argRefs.has(arg)) {
          argRefs.set(arg, `ref_${keyCounter++}`);
        }
        keyParts.push(argRefs.get(arg)!);
      } else {
        // Include type to differentiate between e.g., "1" string and 1 number
        keyParts.push(String(arg) + ':' + typeof arg);
      }
    }

    const key = keyParts.length > 0 ? keyParts.join('|') : '__no_args__';

    if (cache.has(key)) {
      const entry = cache.get(key)!;
      entry.accessOrder = accessCounter++;
      return entry.value;
    }

    // Evict least recently used if at capacity
    if (cache.size >= maxSize) {
      let oldestKey: string | undefined;
      let oldestAccessOrder = Infinity;

      for (const [k, v] of cache.entries()) {
        if (v.accessOrder < oldestAccessOrder) {
          oldestAccessOrder = v.accessOrder;
          oldestKey = k;
        }
      }

      if (oldestKey !== undefined) {
        cache.delete(oldestKey);
      }
    }

    const result = fn(...args);
    cache.set(key, {value: result, accessOrder: accessCounter++});
    return result;
  }) as T;
}

/**
 * Clears the memoization cache for a memoized function.
 * Note: This only works if the memoized function exposes a clear method.
 */
export function memoizeWithClear<T extends (...args: any[]) => any>(
  fn: T
): T & {clear: () => void} {
  // Cache structure to handle mixed primitive and reference arguments
  type CacheNode = {
    weakMap?: WeakMap<any, any>;
    primitiveMap?: Map<string, any>;
    result?: any;
    // hasResult is needed to distinguish between "not cached" and "cached undefined"
    // Without it, we couldn't cache functions that return undefined/null/false/0/""
    hasResult?: boolean;
  };

  let rootCache: CacheNode = {};

  const memoized = ((...args: Parameters<T>): ReturnType<T> => {
    let currentNode: CacheNode = rootCache;

    // Navigate through arguments to find/create cache entry
    for (let i = 0; i < args.length; i++) {
      const arg = args[i];
      const isLastArg = i === args.length - 1;

      if (
        arg !== null &&
        (typeof arg === 'object' ||
          typeof arg === 'function' ||
          typeof arg === 'symbol')
      ) {
        // Handle objects, functions, and symbols with WeakMap
        if (!currentNode.weakMap) {
          currentNode.weakMap = new WeakMap();
        }

        if (isLastArg) {
          if (currentNode.weakMap.has(arg)) {
            return currentNode.weakMap.get(arg);
          }
          const result = fn(...args);
          currentNode.weakMap.set(arg, result);
          return result;
        } else {
          if (!currentNode.weakMap.has(arg)) {
            currentNode.weakMap.set(arg, {});
          }
          currentNode = currentNode.weakMap.get(arg);
        }
      } else {
        // Handle primitives including null and undefined
        const key = String(arg) + ':' + typeof arg;

        if (!currentNode.primitiveMap) {
          currentNode.primitiveMap = new Map();
        }

        if (isLastArg) {
          if (currentNode.primitiveMap.has(key)) {
            return currentNode.primitiveMap.get(key);
          }
          const result = fn(...args);
          currentNode.primitiveMap.set(key, result);
          return result;
        } else {
          if (!currentNode.primitiveMap.has(key)) {
            currentNode.primitiveMap.set(key, {});
          }
          currentNode = currentNode.primitiveMap.get(key);
        }
      }
    }

    // Handle no arguments case
    if (args.length === 0) {
      if (currentNode.hasResult) {
        return currentNode.result;
      }
      const result = fn(...args);
      currentNode.result = result;
      currentNode.hasResult = true;
      return result;
    }

    // Should not reach here
    return fn(...args);
  }) as T & {clear: () => void};

  memoized.clear = () => {
    // Create a new root cache, old WeakMap entries will be garbage collected
    rootCache = {};
  };

  return memoized;
}
