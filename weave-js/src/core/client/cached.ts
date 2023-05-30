import Observable from 'zen-observable';

import {Cache, InMemoryCache} from '../cache';
import {Hasher, MemoizedHasher} from '../model/graph/editing/hash';
import {Node} from '../model/graph/types';
import {Type} from '../model/types';
import {OpStore} from '../opStore/types';
import {Client} from './types';

export class CachedClient implements Client {
  readonly opStore: OpStore;
  private readonly cache: Cache;
  private readonly hasher: Hasher;

  public constructor(private readonly client: Client) {
    this.hasher = new MemoizedHasher();
    this.cache = new InMemoryCache({
      maxElements: 1000,
      keyFn: this.hasher.typedNodeId,
    });
    this.opStore = client.opStore;
  }
  subscribe<T extends Type>(node: Node<T>): Observable<any> {
    return this.client.subscribe(node);
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
    if (this.cache.has(node)) {
      return this.cache.get(node);
    }
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
    this.cache.set(node, result, 30);
    return result;
  }

  async action<T extends Type>(node: Node<T>): Promise<any> {
    return this.client.action(node);
  }

  loadingObservable(): Observable<boolean> {
    return this.client.loadingObservable();
  }
  public refreshAll(): Promise<void> {
    return this.client.refreshAll();
  }
  public debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'CachedClient',
      opStore: this.opStore.debugMeta(),
      client: this.client.debugMeta(),
    };
  }
}
