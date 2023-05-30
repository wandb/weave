import {Node} from '../model/graph/types';
import {OpStore} from '../opStore/types';
import {Server} from '.';

export class Router {
  public constructor(
    public readonly servers: Server[],
    public readonly opStore: OpStore,
    private readonly routingFunc: (node: Node) => Server
  ) {}

  public route(node: Node): Server {
    const server = this.routingFunc(node);
    if (!this.servers.includes(server)) {
      throw new Error('Router returned an invalid server');
    }
    return server;
  }
}

export class RoutedServer implements Server {
  public constructor(
    private readonly router: Router,
    readonly opStore: OpStore
  ) {}

  public query(
    nodes: Node[],
    resetBackendExecutionCache?: boolean
  ): Promise<any[]> {
    type NodeAndGlobalIndex = {node: Node; globalIndex: number};
    const serverNodes: NodeAndGlobalIndex[][] = [];
    this.router.servers.forEach(() => {
      serverNodes.push([]);
    });

    nodes.forEach((node, i) => {
      const assignedServer = this.router.route(node);
      const serverIndex = this.router.servers.indexOf(assignedServer);
      serverNodes[serverIndex].push({node, globalIndex: i});
    });

    const queries: Array<Promise<any[]>> = [];
    this.router.servers.forEach((server, i) => {
      if (serverNodes[i].length > 0) {
        queries.push(
          server.query(
            serverNodes[i].map(({node}) => node),
            resetBackendExecutionCache
          )
        );
      } else {
        queries.push(Promise.resolve([]));
      }
    });

    return Promise.all(queries).then(results => {
      const finalResults: any[] = Array(nodes.length);
      results.forEach((result, i) => {
        const globalIndices = serverNodes[i].map(
          ({globalIndex}) => globalIndex
        );
        globalIndices.forEach((globalIndex, j) => {
          finalResults[globalIndex] = result[j];
        });
      });
      return finalResults;
    });
  }

  debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'RoutedServer',
      opStore: this.opStore.debugMeta(),
    };
  }
}
