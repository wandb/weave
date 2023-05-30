import {Node} from '../model/graph/types';
import {OpStore} from '../opStore/types';

export interface Server {
  readonly opStore: OpStore;
  query(
    nodes: Node[],
    stripTags?: boolean,
    resetBackendExecutionCache?: boolean
  ): Promise<any[]>;
  // subscribe(payload: BatchedGraphs): ZenObservable.SubscriptionObserver<any>[];
  debugMeta(): {id: string} & {[prop: string]: any};
}
