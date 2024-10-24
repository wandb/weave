import { Api as TraceServerApi } from './generated/traceServerApi';
import { Settings } from './settings';
import { defaultBaseUrl, defaultDomain, defaultTraceBaseUrl, setGlobalDomain } from './urls';
import { ConcurrencyLimiter } from './utils/concurrencyLimit';
import { Netrc } from './utils/netrc';
import { createFetchWithRetry } from './utils/retry';
import { getApiKey } from './wandb/settings';
import { WandbServerApi } from './wandb/wandbServerApi';
import { CallStackEntry, WeaveClient } from './weaveClient';

export interface InitOptions {
  project: string;
  entity?: string;
  projectName?: string;
  baseUrl?: string;
  traceBaseUrl?: string;
  domain?: string;
  apiKey?: string;
  settings?: Settings;
}
export interface LoginOptions {
  apiKey: string;
  baseUrl?: string;
  traceBaseUrl?: string;
}

// Global client instance
export let globalClient: WeaveClient | null = null;

export async function login(options?: LoginOptions) {
  if (!options?.apiKey) {
    throw Error('API Key must be specified');
  }
  const { apiKey, baseUrl, traceBaseUrl } = options;
  const url = new URL(baseUrl ?? defaultBaseUrl);
  const host = url.host;
  const resolvedTraceBaseUrl = traceBaseUrl ?? defaultTraceBaseUrl;

  const netrc = new Netrc();
  netrc.setMachine(host, { login: 'user', password: apiKey });
  netrc.save();

  // Test the connection to the traceServerApi
  const testTraceServerApi = new TraceServerApi({
    baseUrl: resolvedTraceBaseUrl,
    baseApiParams: {
      headers: {
        'User-Agent': `W&B Internal JS Client ${process.env.VERSION || 'unknown'}`,
        Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`,
      },
    },
  });
  try {
    await testTraceServerApi.health.readRootHealthGet({});
  } catch (error) {
    throw new Error('Unable to verify connection to the weave trace server with given API Key');
  }

  console.log(`Successfully logged in.  Credentials saved for ${host}`);
}
export async function init({
  project,
  entity,
  baseUrl,
  traceBaseUrl,
  domain,
  apiKey,
  settings,
}: InitOptions): Promise<WeaveClient> {
  const resolvedUrl = new URL(baseUrl ?? defaultBaseUrl);
  const resolvedTraceUrl = new URL(traceBaseUrl ?? defaultTraceBaseUrl);
  const resolvedApiKey = apiKey ?? getApiKey(resolvedUrl.host);
  const resolvedDomain = domain ?? defaultDomain;
  try {
    const wandbServerApi = new WandbServerApi(resolvedUrl.origin, resolvedApiKey);
    const entityName = entity ?? (await wandbServerApi.defaultEntityName());
    const projectId = `${entityName}/${project}`;

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
      baseUrl: resolvedTraceUrl.origin,
      baseApiParams: {
        headers: {
          'User-Agent': `W&B Internal JS Client ${process.env.VERSION || 'unknown'}`,
          Authorization: `Basic ${Buffer.from(`api:${resolvedApiKey}`).toString('base64')}`,
        },
      },
      customFetch: concurrencyLimitedFetch,
    });

    const client = new WeaveClient(traceServerApi, wandbServerApi, projectId, settings, resolvedDomain);
    setGlobalClient(client);
    setGlobalDomain(resolvedDomain);
    console.log(`Initializing project: ${projectId}`);
    return client;
  } catch (error) {
    console.error('Error during initialization:', error);
    throw error;
  }
}

export function requireCurrentCallStackEntry(): CallStackEntry {
  const client = getGlobalClient();
  if (!client) {
    throw new Error('Weave client not initialized');
  }
  const callStackEntry = client.getCallStack().peek();
  if (!callStackEntry) {
    throw new Error('No current call stack entry');
  }
  return callStackEntry;
}

export function requireCurrentChildSummary(): { [key: string]: any } {
  const callStackEntry = requireCurrentCallStackEntry();
  return callStackEntry.childSummary;
}

export function getGlobalClient(): WeaveClient | null {
  return globalClient;
}

export function requireGlobalClient(): WeaveClient {
  const client = getGlobalClient();
  if (!client) {
    throw new Error('Weave client not initialized');
  }
  return client;
}

export function setGlobalClient(client: WeaveClient) {
  globalClient = client;
}
