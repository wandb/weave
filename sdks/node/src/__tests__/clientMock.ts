import {setGlobalClient} from '../clientApi';
import {type InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {type Settings} from '../settings';
import type {WeaveTrace} from '../vendor/weave-server-sdk';
import {WeaveClient} from '../weaveClient';

export function initWithCustomTraceServer(
  projectId: string,
  customTraceServer: InMemoryTraceServer,
  settings: Partial<Settings> = {}
) {
  const client = new WeaveClient({
    traceServerApi: customTraceServer as unknown as WeaveTrace,
    projectId,
    settings,
  });
  setGlobalClient(client);
}
