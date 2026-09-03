import {WeaveTrace} from './vendor/weave-server-sdk';

/** Ceiling for one Stainless request, including our retry wrapper. */
export const TRACE_SERVER_TIMEOUT_MS = 5 * 60 * 1000;

export function createTraceServerClient(options: {
  apiKey: string;
  baseURL: string;
  fetch?: typeof fetch;
  defaultHeaders?: Record<string, string>;
}): WeaveTrace {
  return new WeaveTrace({
    username: 'api',
    password: options.apiKey,
    baseURL: options.baseURL,
    fetch: options.fetch,
    maxRetries: 0,
    timeout: TRACE_SERVER_TIMEOUT_MS,
    defaultHeaders: {
      'User-Agent': `W&B Weave JS Client ${process.env.VERSION || 'unknown'}`,
      ...options.defaultHeaders,
    },
  });
}
