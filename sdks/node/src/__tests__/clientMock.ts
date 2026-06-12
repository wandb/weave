import {setGlobalClient} from '../clientApi';
import {type Api as TraceServerApi} from '../generated/traceServerApi';
import {type InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {Settings} from '../settings';
import {type WandbServerApi} from '../wandb/wandbServerApi';
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
