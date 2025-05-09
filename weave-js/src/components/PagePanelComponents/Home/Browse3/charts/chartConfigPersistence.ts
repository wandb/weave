import {DirectTraceServerClient} from '../pages/wfReactInterface/traceServerDirectClient';
import {ChartConfig} from './ChartTypes';
import {deserializeChartConfigs, serializeChartConfigs} from './utils';

const CONFIG_TYPE = 'browse3-charts-v1';
const SAVE_DEBOUNCE_MS = 5000;

let lastSaveTimeout: ReturnType<typeof setTimeout> | null = null;
let lastSaveArgs: {
  client: DirectTraceServerClient;
  projectId: string;
  configs: ChartConfig[];
} | null = null;

export async function loadChartConfigs(
  client: DirectTraceServerClient,
  projectId: string
): Promise<ChartConfig[]> {
  try {
    const res = await client.configurationList({
      project_id: projectId,
      type: CONFIG_TYPE,
    });
    if (res.configurations.length > 0) {
      const config = res.configurations[res.configurations.length - 1];
      return deserializeChartConfigs(config.value);
    }
    return [];
  } catch (err) {
    return [];
  }
}

export function saveChartConfigs(
  client: DirectTraceServerClient,
  projectId: string,
  configs: ChartConfig[]
) {
  lastSaveArgs = {client, projectId, configs};
  if (lastSaveTimeout) {
    clearTimeout(lastSaveTimeout);
  }
  lastSaveTimeout = setTimeout(() => {
    actuallySaveChartConfigs(
      lastSaveArgs!.client,
      lastSaveArgs!.projectId,
      lastSaveArgs!.configs
    );
    lastSaveTimeout = null;
    lastSaveArgs = null;
  }, SAVE_DEBOUNCE_MS);
}

async function actuallySaveChartConfigs(
  client: DirectTraceServerClient,
  projectId: string,
  configs: ChartConfig[]
) {
  const serialized = serializeChartConfigs(configs);
  try {
    const res = await client.configurationList({
      project_id: projectId,
      type: CONFIG_TYPE,
    });
    if (res.configurations.length > 0) {
      // Update the most recent config
      const config = res.configurations[res.configurations.length - 1];
      await client.configurationUpdate({
        id: config.id,
        project_id: projectId,
        value: serialized,
      });
    } else {
      await client.configurationCreate({
        project_id: projectId,
        type: CONFIG_TYPE,
        value: serialized,
      });
    }
  } catch (err) {
    console.error(err);
  }
}
