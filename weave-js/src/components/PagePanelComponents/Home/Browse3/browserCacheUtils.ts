/**
 * Default cache expiry time in milliseconds (24 hours)
 */
const DEFAULT_CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000;

/**
 * Browser storage cache entry
 */
type CacheData<T> = {
  data: T;
  timestamp: number; // UTC timestamp in milliseconds
};

/**
 * Retrieves cached data from localStorage with expiry check
 * @param cacheKey - Unique key for the cached data
 * @param expiryMs - Optional expiry time in milliseconds (defaults to 24 hours)
 * @returns The cached data if valid, null if expired or not found
 */
export const getCachedByKeyWithExpiry = <T>(
  cacheKey: string,
  expiryMs: number = DEFAULT_CACHE_EXPIRY_MS
): T | null => {
  const cached = localStorage.getItem(cacheKey);
  if (!cached) {
    return null;
  }

  try {
    const {data, timestamp}: CacheData<T> = JSON.parse(cached);
    const currentTime = Date.now();

    if (currentTime - timestamp > expiryMs) {
      localStorage.removeItem(cacheKey);
      return null;
    }
    return data;
  } catch (e) {
    console.error('Error parsing cached data:', e);
    return null;
  }
};

/**
 * Stores data in localStorage with UTC timestamp
 * @param cacheKey - Unique key for the cached data
 * @param data - The data to be cached
 */
export const setCacheByKeyWithExpiry = <T>(cacheKey: string, data: T): void => {
  const cacheData: CacheData<T> = {
    data,
    timestamp: Date.now(),
  };

  try {
    localStorage.setItem(cacheKey, JSON.stringify(cacheData));
  } catch (e) {
    console.error('Error setting cached data:', e);
  }
};
