// In memory cache
// Just wrap a high quality LRU implementation

import _ from 'lodash';
import LRUCache from 'lru-cache';

import {CacheKey, DependencyAwareCache} from './types';

export interface InMemoryCacheOpts<K extends CacheKey, IK extends any> {
  maxElements: number;
  keyFn: (oldKey: K) => IK;
  onDispose?: (key: IK, value: any) => void;
}

export class InMemoryCache<
  K extends CacheKey,
  IK extends {}
> extends DependencyAwareCache<K, IK> {
  private readonly lru: LRUCache<IK, any>;
  private readonly opts: InMemoryCacheOpts<K, IK>;

  // TODO(np): This is very naively implemented.  We need
  // a proper length function and then to decide on a reasonable
  // size for this cache
  constructor(public optsIn?: Partial<InMemoryCacheOpts<K, IK>>) {
    super();
    this.opts = _.defaults({}, optsIn, {
      maxElements: 20000,
      keyFn: (k: K) => k as any,
    });
    this.lru = new LRUCache({
      max: this.opts.maxElements,
      length: (n, key) => 1,
      maxAge: 1000 * 60 * 60 * 24, // 1 day
      dispose: this.onDispose.bind(this),
    });
  }

  onDispose(key: IK, value: any): void {
    if (this.opts.onDispose) {
      this.opts.onDispose(key, value);
    }
  }

  outerKeyToInnerKey(key: K): IK {
    return this.opts.keyFn(key);
  }

  getKey(key: IK): any {
    return this.lru.get(key);
  }

  setKey(key: IK, value: any, ttlSeconds?: number): boolean {
    return this.lru.set(key, value, ttlSeconds ? ttlSeconds * 1000 : undefined);
  }

  delKey(key: IK): Promise<void> {
    return Promise.resolve(this.lru.del(key));
  }

  hasKey(key: IK): boolean {
    return this.lru.has(key);
  }
  reset(): Promise<void> {
    return Promise.resolve(this.lru.reset());
  }
}
