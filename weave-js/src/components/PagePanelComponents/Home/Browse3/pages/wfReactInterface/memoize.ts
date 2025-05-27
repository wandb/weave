/**
 * A simple LRU (Least Recently Used) cache implementation.
 * This cache maintains a fixed-size map of key-value pairs and evicts the least recently used item when the cache is full.
 */
class LRUCache {
  private cache: Map<string, any>;
  private maxSize: number;

  constructor(maxSize: number) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }

  /**
   * Retrieves a value from the cache and updates its position as most recently used.
   * @param key - The key to look up in the cache
   * @returns The cached value or undefined if not found
   */
  get(key: string): any {
    if (!this.cache.has(key)) return undefined;
    const value = this.cache.get(key);
    // Move to end (most recently used)
    this.cache.delete(key);
    this.cache.set(key, value);
    return value;
  }

  /**
   * Stores a value in the cache, evicting the least recently used item if the cache is full.
   * @param key - The key to store the value under
   * @param value - The value to store
   */
  set(key: string, value: any): void {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    } else if (this.cache.size >= this.maxSize) {
      // Remove least recently used item
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }
    this.cache.set(key, value);
  }
}

/**
 * Creates a memoized version of an async function that caches its results.
 * The cache is implemented using an LRU strategy to prevent unbounded memory growth.
 *
 * @param fn - The async function to memoize
 * @param keyFn - A function that generates a cache key from the function arguments
 * @param maxSize - The maximum number of results to cache (default: 100)
 * @returns A memoized version of the input function
 *
 * @example
 * const memoizedFetch = memoize(
 *   async (id: string) => fetch(`/api/${id}`),
 *   (id) => id,
 *   50
 * );
 */
export function memoize<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  keyFn: (...args: Parameters<T>) => string,
  maxSize: number = 100
): T {
  const cache = new LRUCache(maxSize);

  return (async (...args: Parameters<T>) => {
    const key = keyFn(...args);
    const cached = cache.get(key);
    if (cached !== undefined) {
      return cached;
    }
    const result = await fn(...args);
    cache.set(key, result);
    return result;
  }) as T;
}
