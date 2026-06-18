import {setGlobalClient} from '../clientApi';
import {type Api as TraceServerApi} from '../generated/traceServerApi';
import {type InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {Settings} from '../settings';
import {WeaveClient} from '../weaveClient';

export function initWithCustomTraceServer(
  projectId: string,
  customTraceServer: InMemoryTraceServer,
  settings: Partial<Settings> = {}
) {
  const client = new WeaveClient({
    traceServerApi: customTraceServer as unknown as TraceServerApi<any>,
    projectId,
    settings,
  });
  setGlobalClient(client);
}
