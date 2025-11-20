import {Api as TraceServerApi} from './generated/traceServerApi';
import {Settings} from './settings';
import {defaultHost, getUrls, setGlobalDomain} from './urls';
import {ConcurrencyLimiter} from './utils/concurrencyLimit';
import {Netrc} from './utils/netrc';
import {createFetchWithRetry} from './utils/retry';
import {getWandbConfigs} from './wandb/settings';
import {WandbServerApi} from './wandb/wandbServerApi';
import {CallStackEntry, WeaveClient} from './weaveClient';

// Global client instance
export let globalClient: WeaveClient | null = null;

/**
 * Log in to Weights & Biases (W&B) using the provided API key.
 * This function attempts to save the credentials to your netrc file for future use,
 * but will continue even if it cannot write to the file system.
 *
 * @param {string} apiKey - Your W&B API key.
 * @param {string} [host] - (Optional) The host name (usually only needed if you're using a custom W&B server).
 * @throws {Error} If the API key is not specified or if the connection to the weave trace server cannot be verified.
 */
export async function login(apiKey: string, host?: string) {
  if (!host) {
    console.warn('No host provided, using default host:', defaultHost);
    host = defaultHost;
  }
  if (!apiKey) {
    throw new Error(
      'API key is required for login. Please provide a valid API key.'
    );
  }
  const {traceBaseUrl} = getUrls(host);

  // Test the connection to the traceServerApi
  const testTraceServerApi = new TraceServerApi({
    baseUrl: traceBaseUrl,
    baseApiParams: {
      headers: {
        'User-Agent': `W&B Weave JS Client ${process.env.VERSION || 'unknown'}`,
        Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`,
      },
    },
  });
  try {
    await testTraceServerApi.health.readRootHealthGet({});
  } catch (error) {
    throw new Error(
      'Unable to verify connection to the weave trace server with given API Key'
    );
  }

  // Try to save to netrc, but continue even if it fails
  try {
    const netrc = new Netrc();
    if (host && apiKey.trim()) {
      netrc.setEntry({machine: host, login: 'user', password: apiKey});
      netrc.save();
      console.log(`Successfully logged in. Credentials saved for ${host}`);
    }
  } catch (error) {
    // Log warning but don't fail - the API key can still be used from environment
    console.warn(
      'Could not save credentials to netrc file. You may need to set WANDB_API_KEY environment variable for future sessions.'
    );
  }

  // Set the API key in the environment for the current session
  process.env.WANDB_API_KEY = apiKey;
}

/**
 * Initialize the Weave client, which is required for weave tracing to work.
 *
 * @param project - The W&B project name (can be project or entity/project). If you don't
 *                   specify a W&B team (e.g., 'team/project'), your default entity is used.
 *                   To find or update your default entity, refer to User Settings at
 *                   https://docs.wandb.ai/guides/models/app/settings-page/user-settings/#default-team
 * @param settings - (Optional) Weave tracing settings
 * @returns A promise that resolves to the initialized Weave client.
 * @throws {Error} If the initialization fails
 */
export async function init(
  project: string,
  settings?: Settings
): Promise<WeaveClient> {
  const {apiKey, baseUrl, traceBaseUrl, domain} = getWandbConfigs();
  try {
    const wandbServerApi = new WandbServerApi(baseUrl, apiKey);

    let entityName: string | undefined;
    let projectName: string;
    if (project.includes('/')) {
      [entityName, projectName] = project.split('/');
    } else {
      entityName = await wandbServerApi.defaultEntityName();
      projectName = project;
    }
    const projectId = `${entityName}/${projectName}`;

    const retryFetch = createFetchWithRetry({
      baseDelay: 1000,
      maxDelay: 5 * 60 * 1000, // 5 minutes
      maxRetryTime: 12 * 60 * 60 * 1000, // 12 hours
      retryOnStatus: (status: number) =>
        status === 429 || (status >= 500 && status < 600),
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
      baseUrl: traceBaseUrl,
      baseApiParams: {
        headers: {
          'User-Agent': `W&B Weave JS Client ${process.env.VERSION || 'unknown'}`,
          Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`,
        },
      },
      customFetch: concurrencyLimitedFetch,
    });

    const client = new WeaveClient(
      traceServerApi,
      wandbServerApi,
      projectId,
      settings
    );
    setGlobalClient(client);
    setGlobalDomain(domain);
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

export function requireCurrentChildSummary(): {[key: string]: any} {
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

/**
 * Run a function with additional attributes that will be attached to all calls created within.
 * 
 * This is useful for setting metadata like environment, user IDs, or feature flags that should
 * be attached to all operations within a scope.
 * 
 * Attributes are isolated per async execution context using AsyncLocalStorage, so concurrent
 * operations won't interfere with each other.
 * 
 * @param attributes - Key-value pairs to attach to calls
 * @param fn - Function to execute with the attributes
 * @returns The return value of the function
 * 
 * @example
 * ```typescript
 * import * as weave from 'weave';
 * 
 * await weave.init('my-project');
 * 
 * const myOp = weave.op(async (name: string) => {
 *   return `Hello ${name}`;
 * });
 * 
 * // All calls within this function will have the 'env' and 'user' attributes
 * await weave.attributes({env: 'production', user: 'alice'}, async () => {
 *   await myOp('World');
 * });
 * 
 * // Concurrent operations are safely isolated
 * await Promise.all([
 *   weave.attributes({user: 'alice'}, async () => await myOp('test1')),
 *   weave.attributes({user: 'bob'}, async () => await myOp('test2')),
 * ]);
 * ```
 */
export async function attributes<T>(
  attributes: Record<string, any>,
  fn: () => T | Promise<T>
): Promise<T> {
  const client = getGlobalClient();
  if (!client) {
    // If no client is initialized, just run the function without attributes
    return await fn();
  }
  
  // Merge with existing attributes
  const currentAttributes = client.getCallAttributes();
  const mergedAttributes = {...currentAttributes, ...attributes};
  
  return await client.runWithAttributes(mergedAttributes, fn);
}
