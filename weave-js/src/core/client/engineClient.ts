import Observable from 'zen-observable';

import {Engine} from '../engine/types';
import * as GraphTypes from '../model/graph/types';
import * as Model from '../model/types';
import {OpStore} from '../opStore/types';
import {Client} from './types';

/** Provides a Client interface on top of engine. Just
 * used for certain ops, like partitionedTableRows that use a shared
 * function between the refineNode and resolver implementations.
 */
export class EngineClient implements Client {
  readonly opStore: OpStore;
  public constructor(private readonly engine: Engine) {
    this.opStore = engine.opStore;
  }

  public subscribe<T extends Model.Type>(
    node: GraphTypes.Node<T>
  ): Observable<any> {
    throw new Error('not implemented');
  }
  public async query<T extends Model.Type>(
    node: GraphTypes.Node<T>
  ): Promise<any> {
    return (await this.engine.executeNodes([node], true))[0];
  }
  public loadingObservable(): Observable<boolean> {
    throw new Error('not implemented');
  }
  public refreshAll(): Promise<void> {
    throw new Error('not implemented');
  }
  public action<T extends Model.Type>(node: GraphTypes.Node<T>): Promise<any> {
    throw new Error('not implemented');
  }
  public setPolling(polling: boolean) {
    return;
  }
  public setIsPolling(polling: boolean) {
    return;
  }
  public isPolling(): boolean {
    return false;
  }
  public clearCacheForNode(node: GraphTypes.Node<any>): Promise<void> {
    throw new Error('not implemented');
  }
  addOnPollingChangeListener(callback: (polling: boolean) => void): void {
    return;
  }
  removeOnPollingChangeListener(callback: (polling: boolean) => void): void {
    return;
  }
  public debugMeta(): {id: string} & {[prop: string]: any} {
    return {id: 'EngineClient', opStore: this.opStore.debugMeta()};
  }
  public isWeavePythonBackend(): boolean {
    return false;
  }
}
