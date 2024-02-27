import Observable from 'zen-observable';

import type {Node} from '../model/graph/types';
import type {Type} from '../model/types';
import type {OpStore} from '../opStore/types';

export interface Client {
  readonly opStore: OpStore;
  subscribe<T extends Type>(node: Node<T>): Observable<any>;
  query<T extends Type>(node: Node<T>): Promise<any>;
  // Same as query but uncached, used for mutations.
  action<T extends Type>(node: Node<T>): Promise<any>;
  loadingObservable(): Observable<boolean>;
  refreshAll(): Promise<void>;
  debugMeta(): {id: string} & {[prop: string]: any};
  setPolling(polling: boolean): void;
  isPolling(): boolean;
  addOnPollingChangeListener(callback: (polling: boolean) => void): void;
  removeOnPollingChangeListener(callback: (polling: boolean) => void): void;
  clearCacheForNode(node: Node<any>): Promise<void>;
  isWeavePythonBackend(): boolean;
}
