import type Fetch from 'isomorphic-unfetch';

import {GlobalCGEventTracker} from './analytics/tracker';
import {InMemoryCache} from './cache';
import {BasicClient, CachedClient, Client} from './client';
import {supportedEngineForNode} from './hl';
import {nodeToString} from './language/js/print';
import {MemoizedHasher} from './model/graph/editing/hash';
import {Node} from './model/graph/types';
import {makePerformanceMixedOpStore} from './opStore/mixedOpStore';
import {OpStore} from './opStore/types';
import {
  LocalServer,
  RemoteHttpServer,
  Server,
  ServerWithShadow,
} from './server';
import {RoutedServer, Router} from './server/routed';
import {ServerAPI} from './serverApi';
import {
  DEBUG_ATTACH_TO_GLOBAL_THIS,
  LOG_DEBUG_MESSAGES,
} from './util/constants';

// Useful for console debugging
export function bindClientToGlobalThis(client: Client) {
  if (typeof globalThis !== 'undefined' && DEBUG_ATTACH_TO_GLOBAL_THIS) {
    (globalThis as any).cgquery = client.query.bind(client);
  }
}

export function createLocalServer(backend: ServerAPI): Server {
  const hashing = new MemoizedHasher();
  const cache = new InMemoryCache({keyFn: hashing.typedNodeId});
  return new LocalServer(cache, backend);
}

export function createLocalClient(backend: ServerAPI): Client {
  const client = new BasicClient(createLocalServer(backend));

  bindClientToGlobalThis(client);
  return client;
}

export function createRemoteServer(
  weaveUrl: string,
  tokenFunc: () => Promise<string | undefined>,
  opStore: OpStore,
  isAdmin = false,
  isShadow = false,
  anonApiKey?: string,
  fetch?: typeof Fetch
): Server {
  return new RemoteHttpServer(
    {
      weaveUrl,
      tokenFunc,
      anonApiKey,
      useAdminPrivileges: isAdmin,
      isShadow,
      fetch,
    },
    opStore
  );
}

export function createRemoteClient(
  weaveUrl: string,
  tokenFunc: () => Promise<string | undefined>,
  isAdmin = false,
  opStore: OpStore,
  anonApiKey?: string,
  fetch?: typeof Fetch
): Client {
  const remoteServer = createRemoteServer(
    weaveUrl,
    tokenFunc,
    opStore,
    isAdmin,
    false,
    anonApiKey,
    fetch
  );
  const client = new CachedClient(new BasicClient(remoteServer));

  bindClientToGlobalThis(client);
  return client;
}

export function createServerWithShadow(
  mainServer: Server,
  shadowServer: Server
): Server {
  return new ServerWithShadow(mainServer, shadowServer);
}

export function createdRoutedPerformanceServer(
  localServer: Server,
  pythonServer: Server
): Server {
  const {routingFunc, opStore} = performanceRouter(localServer, pythonServer);
  const router = new Router([localServer, pythonServer], opStore, routingFunc);
  return new RoutedServer(router, opStore);
}

function performanceRouter(
  localServer: Server,
  pythonServer: Server
): {routingFunc: (node: Node) => Server; opStore: OpStore} {
  const opStore = makePerformanceMixedOpStore(
    localServer.opStore,
    pythonServer.opStore
  );
  const routingFunc = (node: Node) => {
    const supportedEngines = supportedEngineForNode(node, opStore);
    if (supportedEngines.size === 0) {
      if (LOG_DEBUG_MESSAGES) {
        console.warn(
          `No allowed engines for node, ${JSON.stringify(
            node
          )}, using TS backend`
        );
      }
      GlobalCGEventTracker.routedServerLocal++;
      return localServer;
    } else if (supportedEngines.has('py')) {
      if (LOG_DEBUG_MESSAGES) {
        console.log(
          'RoutingFunc: Using Python backend \n',
          nodeToString(node, opStore)
        );
      }
      GlobalCGEventTracker.routedServerRemote++;
      return pythonServer;
    } else {
      if (LOG_DEBUG_MESSAGES) {
        console.log(
          'RoutingFunc: Using Typescript backend \n',
          nodeToString(node, opStore)
        );
      }
      GlobalCGEventTracker.routedServerLocal++;
      return localServer;
    }
  };

  return {opStore, routingFunc};
}
