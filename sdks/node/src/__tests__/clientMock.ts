import {setGlobalClient} from '../clientApi';
import {InMemoryTraceServer} from '../inMemoryTraceServer';
import {Settings} from '../settings';
import {TraceServerApiLike} from '../traceServerApiFactory';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {WeaveClient} from '../weaveClient';

export function initWithCustomTraceServer(
  projectName: string,
  customTraceServer: InMemoryTraceServer,
  settings: Settings = new Settings(true)
) {
  const client = new WeaveClient(
    customTraceServer as unknown as TraceServerApiLike,
    {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
    projectName,
    settings
  );
  setGlobalClient(client);
}
