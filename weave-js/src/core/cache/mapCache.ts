// Simple map-based cache, keyed directly by CacheKey
// Use for shortlived, finite execution contexts like map ops

import {CacheKey, DependencyAwareCache} from './types';

export class MapCache extends DependencyAwareCache<CacheKey, CacheKey> {
  private readonly map: Map<CacheKey, any>;

  constructor() {
    super();
    this.map = new Map<CacheKey, any>();
  }

  outerKeyToInnerKey(key: CacheKey): CacheKey {
    return key;
  }

  getKey(key: CacheKey): Promise<any> {
    return Promise.resolve(this.map.get(key));
  }

  setKey(key: CacheKey, value: any, ttlSeconds?: number): boolean {
    return !!this.map.set(key, value);
  }

  delKey(key: CacheKey): Promise<void> {
    this.map.delete(key);
    return Promise.resolve();
  }

  hasKey(key: CacheKey): boolean {
    return this.map.has(key);
  }

  reset(): Promise<void> {
    return Promise.resolve(this.map.clear());
  }
}
