import {setGlobalClient} from '../clientApi';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {InMemoryTraceServer} from '../inMemoryTraceServer';
import {Settings} from '../settings';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {WeaveClient} from '../weaveClient';

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
