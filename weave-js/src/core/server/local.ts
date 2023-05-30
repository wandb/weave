import {GlobalCGEventTracker} from '../analytics/tracker';
import {Cache} from '../cache';
import {BasicEngine, Engine} from '../engine';
import type {Node} from '../model/graph/types';
import type {OpStore} from '../opStore/types';
import type {ServerAPI} from '../serverApi';
import type {Tracer} from '../traceTypes';
import type {Server} from './types';

export class LocalServer implements Server {
  readonly opStore: OpStore;
  private readonly engine: Engine;
  constructor(cache: Cache, backend: ServerAPI, trace?: Tracer) {
    this.engine = new BasicEngine(cache, backend, {
      trace,
    });
    this.opStore = this.engine.opStore;
  }

  query(nodes: Node[], resetBackendExecutionCache?: boolean): Promise<any[]> {
    GlobalCGEventTracker.localServerQueryBatchRequests++;
    return this.engine.executeNodes(nodes, true, resetBackendExecutionCache);
  }

  debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'LocalServer',
      opStore: this.opStore.debugMeta(),
    };
  }
}
