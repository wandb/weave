import * as GraphTypes from '../model/graph/types';

export type CacheKey = GraphTypes.Node;

export interface MultiSetEntry<K extends CacheKey> {
  key: K;
  value: any;
  ttlSeconds?: number;
  dependsOn?: K[];
  dependencies?: K[];
}

// The minimal interface for a cache that supports CG execution
export interface Cache {
  get(key: CacheKey): any; // undefined if not found

  getMulti(keys: CacheKey[]): Promise<any[]>;
  set(
    key: CacheKey,
    value: any,
    ttlSeconds?: number,
    dependsOn?: CacheKey[],
    dependencies?: CacheKey[]
  ): boolean;

  setMulti(entries: Array<MultiSetEntry<CacheKey>>): Promise<boolean>;
  invalidate(key: CacheKey): Promise<void>;
  has(key: CacheKey): boolean;

  hasMulti(keys: CacheKey[]): Promise<any[]>;
  reset(): Promise<void>;
}

/**
 * DependencyAwareCache is an ABC which partially implements the above Cache
 * interface.  It is intended to be used as a base class for more specific
 * caches.  It provides a default implementation for handling dependencies
 * and only requires subclasses to implement
 *   abstract outerKeyToInnerKey(key: OK): IK;
 *   abstract delKey(key: IK): Promise<void>;
 *   abstract setKey(key: IK, value: any, ttlSeconds?: number): Promise<boolean>;
 *   abstract getKey(key: IK): Promise<any>;
 *   abstract hasKey(key: IK): Promise<boolean>;
 *   abstract reset(): Promise<void>;
 *
 * The key aspect of this class is that it allows the caller to provide downstream
 * dependents and upstream dependencies. When a key is invalidated, it will invalidate
 * all dependent keys.
 */
export abstract class DependencyAwareCache<OK extends CacheKey, IK extends any>
  implements Cache
{
  protected dependencyMap: Map<IK, Set<IK>>;

  constructor() {
    this.dependencyMap = new Map();
  }

  set(
    key: OK,
    value: any,
    ttlSeconds?: number,
    dependencies?: OK[],
    dependents?: OK[]
  ): boolean {
    const innerKey = this.outerKeyToInnerKey(key);
    if (dependents != null) {
      if (!this.dependencyMap.has(innerKey)) {
        this.dependencyMap.set(
          innerKey,
          new Set(dependents.map(this.outerKeyToInnerKey.bind(this)))
        );
      } else {
        dependents.forEach(d =>
          this.dependencyMap.get(innerKey)!.add(this.outerKeyToInnerKey(d))
        );
      }
    }
    if (dependencies != null) {
      dependencies.forEach(d => {
        const dKey = this.outerKeyToInnerKey(d);
        if (!this.dependencyMap.has(dKey)) {
          this.dependencyMap.set(dKey, new Set([innerKey]));
        } else {
          this.dependencyMap.get(dKey)!.add(innerKey);
        }
      });
    }
    return this.setKey(innerKey, value, ttlSeconds);
  }

  cascadeDelete(k: IK): void {
    this.delKey(k);
    if (this.dependencyMap.has(k)) {
      this.dependencyMap.get(k)!.forEach(d => {
        this.cascadeDelete(d);
        this.dependencyMap.delete(d);
      });
    }
  }

  invalidate(key: OK): Promise<void> {
    return Promise.resolve(this.cascadeDelete(this.outerKeyToInnerKey(key)));
  }

  getMulti(keys: OK[]): Promise<any[]> {
    return Promise.all(keys.map(k => this.get(k)));
  }

  async setMulti(entries: Array<MultiSetEntry<OK>>): Promise<boolean> {
    const result = await Promise.all(
      entries.map(e =>
        this.set(e.key, e.value, e.ttlSeconds, e.dependsOn, e.dependencies)
      )
    );
    return result.every(r => !!r);
  }

  hasMulti(keys: OK[]): Promise<boolean[]> {
    return Promise.all(keys.map(k => this.has(k)));
  }

  get(key: OK): any {
    return this.getKey(this.outerKeyToInnerKey(key));
  }
  has(key: OK): boolean {
    return this.hasKey(this.outerKeyToInnerKey(key));
  }

  abstract outerKeyToInnerKey(key: OK): IK;
  abstract delKey(key: IK): Promise<void>;
  abstract setKey(key: IK, value: any, ttlSeconds?: number): boolean;
  abstract getKey(key: IK): any;
  abstract hasKey(key: IK): boolean;
  abstract reset(): Promise<void>;
}
