import {setGlobalClient} from '../clientApi.js';
import {Api as TraceServerApi} from '../generated/traceServerApi.js';
import {InMemoryTraceServer} from '../inMemoryTraceServer.js';
import {Settings} from '../settings.js';
import {WandbServerApi} from '../wandb/wandbServerApi.js';
import {WeaveClient} from '../weaveClient.js';

export function initWithCustomTraceServer(
  projectName: string,
  customTraceServer: InMemoryTraceServer,
  settings: Settings = new Settings(true)
) {
  const client = new WeaveClient(
    customTraceServer as unknown as TraceServerApi<any>,
    {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
    projectName,
    settings
  );
  setGlobalClient(client);
}
