import fetch from 'isomorphic-unfetch';
import _ from 'lodash';
import {performance} from 'universal-perf-hooks';

import {GlobalCGEventTracker} from '../analytics/tracker';
import {Node, serialize, serializeMulti} from '../model';
import type {OpStore} from '../opStore';
import {batchIntervalOverride, isWeaveDebugEnabled} from '../util/debug';
import {uuidv4} from '../util/id';
import type {Server} from './types';

const BATCH_INTERVAL_MS = () => batchIntervalOverride() ?? 50;
const WEAVE_1_SERVER_TIMEOUT_MS = 1000 * 60 * 2; // 2 minutes

// from https://www.jpwilliams.dev/how-to-unpack-the-return-type-of-a-promise-in-typescript
// when all of our apps are on TS 4.x we can use Awaited<> instead
// type Unwrap<T> = T extends Promise<infer U>
//   ? U
//   : T extends (...args: any) => Promise<infer U2>
//   ? U2
//   : T extends (...args: any) => infer U3
//   ? U3
//   : T;

// to prevent importing the DOM types here (they're all or nothing),
// we get the Response type off of the fetch polyfill instead
//
// because the library doesn't actually export it, we need to unpack the promise
// type returned by the fetch() function
// type Response = Unwrap<ReturnType<typeof fetch>>;

export interface RemoteWeaveOptions {
  weaveUrl: string;

  // An async function for retrieving auth token
  tokenFunc: () => Promise<string | undefined>;

  // An anonymous API key for anonymous requests
  anonApiKey?: string;

  useAdminPrivileges: boolean;

  // Set shadow service headers on request
  isShadow: boolean;

  // Enable so a single HTTP request cannot contain more than one disjoint graph
  contiguousBatchesOnly: boolean;

  // If true, will merge inexpensive batches into a single request
  mergeInexpensiveBatches: boolean;

  // Maximum number of concurrent requests to the server
  maxConcurrentRequests: number;

  // Maximum number of nodes to send in a single request
  maxBatchSize: number;

  // Maximum number of times to retry a request; network errors do not count against this
  maxRetries: number;

  // Backoff formula: min(backoffMax, backoffBase * e^(backoffExpScalar * backoffCount))
  backoffBase: number;
  backoffMax: number;
  backoffExpScalar: number;

  fetch: typeof fetch;
}

const defaultOpts: RemoteWeaveOptions = {
  weaveUrl: 'https://localhost:9004/execute',
  tokenFunc: () => Promise.resolve(''),
  useAdminPrivileges: false,
  isShadow: false,
  contiguousBatchesOnly: true,
  mergeInexpensiveBatches: true,
  // Let's start with 2 concurrent requests, and see how it goes
  maxConcurrentRequests: 2,
  maxBatchSize: Infinity,
  maxRetries: 5,
  backoffBase: 500,
  backoffMax: 20000,
  backoffExpScalar: 0.8,
  fetch: fetch.bind(globalThis as any),
};

type NodeState = 'waiting' | 'active';

interface NodeEntry {
  node: Node;
  resolve: (r: any) => void;
  reject: (r: any) => void;
  state: NodeState;
  retries: number;
}

// TODO: currently deprecated, but works in all browsers
declare function btoa(s: string): string;

const createClientCacheKey = (windowSizeMs: number = 15000) => {
  // Returning undefined for now since caching is now handled higher
  // up in the stack - this is quite redundant with the cache key. Keeping
  // the code here for now in case we want to use it again in the future.
  return undefined;
  // return Math.floor(Date.now() / windowSizeMs).toString();
};

// Handles (de)serialization to send to a remote CG server
export class RemoteHttpServer implements Server {
  public clientCacheKey: string | undefined = createClientCacheKey();
  private readonly opts: RemoteWeaveOptions;
  private readonly flushInterval: NodeJS.Timeout;
  private pendingNodes: Map<Node, NodeEntry> = new Map();
  private pendingRequests: Set<Promise<any>> = new Set();
  private nextFlushTime = 0;
  private backoffCount: number = 0;
  private trace: (...args: any[]) => void;

  public constructor(
    inOpts: Partial<RemoteWeaveOptions>,
    public readonly opStore: OpStore
  ) {
    this.opts = _.defaults({}, inOpts, defaultOpts);
    this.flushInterval = setInterval(
      () =>
        this.flush().catch(e => {
          console.error('Error flushing RemoteHttpServer', e);
          clearInterval(this.flushInterval);
        }),
      BATCH_INTERVAL_MS()
    );
    this.trace = isWeaveDebugEnabled()
      ? (...args: any[]) =>
          console.debug(
            `[Weave:RemoteHttpServer] [${(performance.now() / 1000).toFixed(
              3
            )}s]`,
            ...args
          )
      : () => {};
  }

  public close() {
    clearInterval(this.flushInterval);
  }

  public refreshBackendCacheKey(windowSizeMs: number = 15000) {
    this.clientCacheKey = createClientCacheKey(windowSizeMs);
  }

  public async query(
    nodes: Node[],
    stripTags?: boolean,
    withBackendCacheReset?: boolean
  ): Promise<any[]> {
    GlobalCGEventTracker.remoteHttpServerQueryBatchRequests++;
    if (withBackendCacheReset) {
      this.refreshBackendCacheKey(1);
    }

    this.trace(`Enqueue ${nodes.length} nodes`);
    return await Promise.all(
      nodes.map(
        node =>
          new Promise((resolve, reject) => {
            this.pendingNodes.set(node, {
              node,
              resolve,
              reject,
              state: 'waiting',
              retries: 0,
            });
          })
      )
    );
  }

  public queryEach(
    nodes: Node[],
    withBackendCacheReset?: boolean
  ): Array<Promise<any>> {
    GlobalCGEventTracker.remoteHttpServerQueryBatchRequests++;
    if (withBackendCacheReset) {
      this.refreshBackendCacheKey(1);
    }

    this.trace(`Enqueue ${nodes.length} nodes`);

    return nodes.map(
      node =>
        new Promise((resolve, reject) => {
          this.pendingNodes.set(node, {
            node,
            resolve,
            reject,
            state: 'waiting',
            retries: 0,
          });
        })
    );
  }

  public debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'RemoteHttpServer',
      opStore: this.opStore.debugMeta(),
    };
  }

  private resolveNode(node: Node, result: any) {
    const record = this.pendingNodes.get(node);
    if (record == null) {
      throw new Error(
        'resolveNode called on node that was not awaiting a result'
      );
    }
    this.pendingNodes.delete(node);
    record.resolve(result);
  }

  private rejectNode(node: Node, e: {message: string; traceback: string[]}) {
    const record = this.pendingNodes.get(node);
    if (record == null) {
      throw new Error(
        'resolveNode called on node that was not awaiting a result'
      );
    }
    this.pendingNodes.delete(node);
    record.reject(e);
  }

  private getWaitingNodes() {
    return Array.from(this.pendingNodes.values())
      .filter(r => r.state === 'waiting')
      .slice(0, this.opts.maxBatchSize);
  }

  private backoff(step = 1) {
    const nextBackoff = Math.min(
      this.opts.backoffMax,
      this.opts.backoffBase *
        Math.exp((this.backoffCount += step) * this.opts.backoffExpScalar)
    );
    this.trace(`Backing off for ${Math.round(nextBackoff)}ms`);
    this.nextFlushTime = Date.now() + nextBackoff;
  }

  private resetBackoff() {
    if (this.backoffCount > 0) {
      this.trace(`Got OK response, reset backoff`);
      this.backoffCount = 0;
    }
  }

  private async flush() {
    if (Date.now() < this.nextFlushTime) {
      // Spammy
      // this.trace(`Request backoff in effect`);
      return;
    }

    const availableRequests =
      this.opts.maxConcurrentRequests - this.pendingRequests.size;

    if (availableRequests <= 0) {
      this.trace(`Too many requests in-flight (${this.pendingRequests.size})`);
      return;
    }

    const nodeEntries = this.getWaitingNodes();
    if (nodeEntries.length === 0) {
      return;
    }

    this.trace(`Flushing ${nodeEntries.length} nodes`);

    const nodes = nodeEntries.map(e => e.node);
    const [payloads, originalIndexes] = this.opts.contiguousBatchesOnly
      ? serializeMulti(nodes, this.opts.mergeInexpensiveBatches)
      : [[serialize(nodes)], [_.range(nodes.length)]];

    for (
      let reqIdx = 0;
      reqIdx < Math.min(availableRequests, payloads.length);
      reqIdx++
    ) {
      const payload = payloads[reqIdx];
      const indexes = originalIndexes[reqIdx];

      const setState = (state: NodeState) =>
        indexes.forEach(i => (nodeEntries[i].state = state));

      const setRetryOrFail = () =>
        indexes.forEach(i => {
          const entry = nodeEntries[i];
          if (entry.retries >= this.opts.maxRetries) {
            this.trace(`Cancelling node after ${entry.retries} retries`);
            this.rejectNode(entry.node, {
              message: `Weave request failed after ${entry.retries} retries`,
              traceback: [],
            });
          } else {
            entry.state = 'waiting';
            entry.retries++;
          }
        });

      const rejectAll = (e: {message: string; traceback: string[]}) =>
        indexes.forEach(i => this.rejectNode(nodeEntries[i].node, e));

      const resolveOrReject = (response: {
        data: any[];
        errors?: Array<{message: string; traceback: string[]}>;
        node_to_error?: {[nodeNdx: number]: number};
      }) => {
        (indexes as number[]).forEach((entryIndex, nodeIndex) => {
          const currentNode = nodeEntries[entryIndex].node;
          if (response.node_to_error != null && response.errors != null) {
            const nodeErrorNdx = response.node_to_error[nodeIndex];
            if (nodeErrorNdx != null) {
              this.rejectNode(currentNode, response.errors[nodeErrorNdx]);
              return;
            }
          }
          this.resolveNode(currentNode, response.data[nodeIndex]);
        });
      };

      setState('active');
      const p = new Promise(async resolve => {
        const payloadJSON = {
          graphs: payload,
        };
        const body = JSON.stringify(payloadJSON);

        const additionalHeaders: Record<string, string> = {};
        if (this.opts.useAdminPrivileges) {
          // This is also found in cookie, which to prefer?
          additionalHeaders['use-admin-privileges'] = 'true';
        }
        if (this.opts.anonApiKey != null && this.opts.anonApiKey !== '') {
          additionalHeaders['x-wandb-anonymous-auth-id'] = btoa(
            this.opts.anonApiKey
          );
        }
        if (this.opts.isShadow) {
          additionalHeaders['weave-shadow'] = 'true';
          additionalHeaders['x-weave-include-execution-time'] = 'true';
        } else {
          additionalHeaders['weave-shadow'] = 'false';
        }

        if (this.clientCacheKey != null) {
          additionalHeaders['x-weave-client-cache-key'] = this.clientCacheKey;
        }

        additionalHeaders['x-request-id'] = uuidv4();

        let respJson: any = {
          data: new Array(nodes.length).fill(null),
        };
        let fetchResponse: any = null;
        const startTime = performance.now();
        try {
          fetchResponse = await this.opts.fetch(this.opts.weaveUrl, {
            credentials: 'include',
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...additionalHeaders,
            },
            body,
          });
        } catch (err) {
          // network error, always retry these, does not count against max retries
          this.trace(`fetch failed: ${(err as Error).message}`, err);
          this.backoff();
          // if we've been waiting for more than the timeout, we know it's a timeout and not a network error
          const totalWaitTime = performance.now() - startTime;
          if (totalWaitTime >= WEAVE_1_SERVER_TIMEOUT_MS - 1000) {
            // This is a timeout, not a network error
            rejectAll({
              message: `Weave request failed - backend timeout after ${totalWaitTime} milliseconds.`,
              traceback: [],
            });
          } else {
            setState('waiting');
          }
        }

        if (!this.opts.isShadow && fetchResponse != null) {
          if (fetchResponse.ok) {
            // 200
            try {
              const resp = await fetchResponse.json();
              this.resetBackoff();

              if (resp.data == null) {
                this.trace(
                  'Weave response was missing data. Fetch Details:\n',
                  JSON.stringify(
                    {
                      payloadJSON,
                      nodes,
                      resp,
                    },
                    null,
                    2
                  )
                );
              } else {
                respJson = resp;
              }
            } catch (err) {
              this.trace(
                'Weave response deserialization failed. Fetch Details:\n',
                JSON.stringify(
                  {
                    payloadJSON,
                    nodes,
                    err,
                  },
                  null,
                  2
                )
              );
              throw new Error('Weave response deserialization failed' + err);
            }

            resolveOrReject(respJson);
          } else {
            if ([502, 503, 504].includes(fetchResponse.status)) {
              // Retryable
              // 502 = bad gateway
              // 503 = service unavailable
              // 504 = gateway timeout
              this.backoff();
              setRetryOrFail();
            } else if ([429].includes(fetchResponse.status)) {
              // Retryable but aggressively back off
              // 429 = too many requests
              this.backoff(10);
              setRetryOrFail();
            } else {
              rejectAll({
                message: 'Weave request failed: ' + fetchResponse.status,
                traceback: [],
              });
            }
          }
        }
        this.pendingRequests.delete(p);
        resolve(true); // Ignored
      });
      this.pendingRequests.add(p);
    }
  }
}
