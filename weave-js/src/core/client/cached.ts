import Observable from 'zen-observable';

import {Cache, InMemoryCache} from '../cache';
import {Hasher, MemoizedHasher} from '../model/graph/editing/hash';
import {Node} from '../model/graph/types';
import {Type} from '../model/types';
import {OpStore} from '../opStore/types';
import {defaultCachePolicy} from './cachePolicy';
import {Client} from './types';

type CachedNode = {
  obs: Observable<any>;
  sub: ZenObservable.Subscription;
};
export class CachedClient implements Client {
  readonly opStore: OpStore;
  private readonly cache: Cache;
  private readonly hasher: Hasher;

  public constructor(private readonly client: Client) {
    this.hasher = new MemoizedHasher();
    this.cache = new InMemoryCache({
      maxElements: 1000,
      keyFn: this.hasher.typedNodeId,
      onDispose: this.onDispose.bind(this),
    });
    this.opStore = client.opStore;
  }
  subscribe<T extends Type>(node: Node<T>): Observable<any> {
    // Moving the cache from `query` to subscribe.
    // This allows us to maintain a cache of subscriptions
    // (which are used for both `query` and `subscribe`)
    // This works by maintaining a single open subscription per node
    // during the lifetime of the node being cached. This allows
    // subsequent calls to `query` or `subscribed` to receive the
    // data from the subscription. This means reloading similar content
    // on screen will not cause a re-query, but will instead use the
    // existing subscription for up to 30 seconds!
    const shouldCache = defaultCachePolicy(node);
    if (this.cache.has(node) && shouldCache) {
      return this.cache.get(node).obs;
    }
    const obs = this.client.subscribe(node);
    if (shouldCache) {
      const sub = obs.subscribe(res => {});

      this.cache.set(node, {obs, sub}, 30);
    }

    return obs;
  }

  public setPolling(polling: boolean) {
    this.client.setPolling(polling);
  }

  public isPolling(): boolean {
    return this.client.isPolling();
  }

  public addOnPollingChangeListener(
    callback: (polling: boolean) => void
  ): void {
    return this.client.addOnPollingChangeListener(callback);
  }
  public removeOnPollingChangeListener(
    callback: (polling: boolean) => void
  ): void {
    return this.client.removeOnPollingChangeListener(callback);
  }

  async query<T extends Type>(node: Node<T>): Promise<any> {
    const result = new Promise((resolve, reject) => {
      const obs = this.subscribe(node);
      const sub = obs.subscribe(
        nodeRes => {
          resolve(nodeRes);
          sub.unsubscribe();
        },
        caughtError => {
          reject(caughtError);
          sub.unsubscribe();
        }
      );
    });
    return result;
  }

  async action<T extends Type>(node: Node<T>): Promise<any> {
    return this.client.action(node);
  }

  loadingObservable(): Observable<boolean> {
    return this.client.loadingObservable();
  }
  public refreshAll(): Promise<void> {
    return this.cache.reset().finally(() => {
      return this.client.refreshAll();
    });
  }
  public debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'CachedClient',
      opStore: this.opStore.debugMeta(),
      client: this.client.debugMeta(),
    };
  }

  public isWeavePythonBackend(): boolean {
    return this.client.isWeavePythonBackend();
  }

  public clearCacheForNode(node: Node<any>): Promise<void> {
    return this.client.clearCacheForNode(node).then(() => {
      return this.cache.invalidate(node);
    });
  }

  private onDispose(key: string, value: CachedNode): void {
    value.sub.unsubscribe();
  }
}
