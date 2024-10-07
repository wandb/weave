import {ConcurrencyLimiter} from './concurrency-limit';
import {TRACE_BASE_URL, WANDB_BASE_URL} from './constants';
import {InMemoryTraceServer} from './in-memory-trace-server';
import {createFetchWithRetry} from './retry';
import {getApiKey} from './settings';
import {Api as TraceServerApi} from './trace-server-api';
import {WandbServerApi} from './wandb-server-api';
import {CallStackEntry, createSettings, WeaveClient} from './weave-client';

// Global client instance
export let globalClient: WeaveClient | null = null;

export async function init(projectName: string): Promise<WeaveClient> {
  const host = WANDB_BASE_URL;
  const apiKey = getApiKey();

  const headers: Record<string, string> = {
    'User-Agent': `W&B Internal JS Client ${process.env.VERSION || 'unknown'}`,
    Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`,
  };

  try {
    const wandbServerApi = new WandbServerApi(host, apiKey);
    const defaultEntityName = await wandbServerApi.defaultEntityName();
    const projectId = `${defaultEntityName}/${projectName}`;

    const retryFetch = createFetchWithRetry({
      baseDelay: 1000,
      maxDelay: 5 * 60 * 1000, // 5 minutes
      maxRetryTime: 12 * 60 * 60 * 1000, // 12 hours
      retryOnStatus: (status: number) => status === 429 || (status >= 500 && status < 600),
    });
    const concurrencyLimiter = new ConcurrencyLimiter(20);
    const concurrencyLimitedFetch = concurrencyLimiter.limitFunction(
      async (...fetchParams: Parameters<typeof fetch>) => {
        const result = await retryFetch(...fetchParams);
        // Useful for debugging
        // console.log(`Active: ${concurrencyLimiter.active} Pending: ${concurrencyLimiter.pending}`);
        return result;
      }
    );

    const traceServerApi = new TraceServerApi({
      baseUrl: TRACE_BASE_URL,
      baseApiParams: {headers},
      customFetch: concurrencyLimitedFetch,
    });

    globalClient = new WeaveClient(traceServerApi, wandbServerApi, projectId);
    console.log(`Initializing project: ${projectId}`);
    return globalClient;
  } catch (error) {
    console.error('Error during initialization:', error);
    throw error;
  }
}

export function initWithCustomTraceServer(projectName: string, customTraceServer: InMemoryTraceServer) {
  globalClient = new WeaveClient(
    customTraceServer as unknown as TraceServerApi<any>,
    {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
    projectName,
    createSettings({quiet: true})
  );
}

export function requireClient(): WeaveClient {
  if (globalClient == null) {
    throw new Error('Weave client not initialized (make sure to call `weave.init()` first)');
  }
  return globalClient;
}

export function requireCurrentCallStackEntry(): CallStackEntry {
  if (globalClient == null) {
    throw new Error('Weave client not initialized (make sure to call `weave.init()` first)');
  }
  const callStackEntry = globalClient.getCallStack().peek();
  if (callStackEntry == null) {
    throw new Error('No current call stack entry');
  }
  return callStackEntry;
}

export function requireCurrentChildSummary(): {[key: string]: any} {
  const callStackEntry = requireCurrentCallStackEntry();
  return callStackEntry.childSummary;
}
