import {GlobalCGEventTracker} from '../analytics/tracker';
import {Node} from '../model/graph/types';
import {OpStore} from '../opStore/types';
import {Server} from './types';

export class ServerWithShadow implements Server {
  readonly opStore: OpStore;
  constructor(
    private readonly mainServer: Server,
    private readonly shadowServer: Server,
    opStore?: OpStore
  ) {
    if (opStore) {
      this.opStore = opStore;
    } else {
      this.opStore = mainServer.opStore;
    }
  }

  query(nodes: Node[], resetBackendExecutionCache?: boolean): Promise<any[]> {
    GlobalCGEventTracker.shadowServerRequests++;
    this.shadowServer
      .query(nodes, resetBackendExecutionCache)
      .catch(reason =>
        console.log(
          'Weave shadow request rejected (this is no big deal): ',
          reason
        )
      ); // fire and forget
    return this.mainServer.query(nodes, resetBackendExecutionCache);
  }

  debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'ServerWithShadow',
      mainServer: this.mainServer.debugMeta(),
      shadowServer: this.shadowServer.debugMeta(),
      opStore: this.opStore.debugMeta(),
    };
  }
}
