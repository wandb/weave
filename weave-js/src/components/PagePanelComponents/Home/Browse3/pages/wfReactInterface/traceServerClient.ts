/**
 * EDIT ME
 * This file defines the connection between the web client and the trace server.
 * The intention is that the implementation is a 1-1 mapping to the trace
 * server's API. This file should not contain any business logic. If possible,
 * we could generate this from `trace_server.py`. Which in effect is a perfect
 * mapping of `weave/trace_server/trace_server_interface.py` as a web service.
 *
 * These types MUST be kept in sync with the types defined in
 * `weave/trace_server/trace_server_interface.py`. Please modify with care.
 *
 * TODO: Currently, we only implement Call Read and Call Query - there are
 * several other endpoints that we should implement.
 */

import {getCookie} from '@wandb/weave/common/util/cookie';
import fetch from 'isomorphic-unfetch';
import _ from 'lodash';

export type KeyedDictType = {
  [key: string]: any;
  _keys?: string[];
};

export type TraceCallSchema = {
  project_id: string;
  id: string;
  op_name: string;
  trace_id: string;
  parent_id?: string;
  started_at: string;
  attributes: KeyedDictType;
  inputs: KeyedDictType;
  ended_at?: string;
  exception?: string;
  output?: KeyedDictType;
  summary?: KeyedDictType;
  wb_run_id?: string;
  wb_user_id?: string;
};

type TraceCallReadReq = {
  project_id: string;
  id: string;
};

export type TraceCallReadRes = {
  call: TraceCallSchema;
};

interface TraceCallsFilter {
  op_names?: string[];
  input_refs?: string[];
  output_refs?: string[];
  parent_ids?: string[];
  trace_ids?: string[];
  call_ids?: string[];
  trace_roots_only?: boolean;
  wb_run_ids?: string[];
  wb_user_ids?: string[];
}

type TraceCallsQueryReq = {
  project_id: string;
  filter?: TraceCallsFilter;
  limit?: number;
  offset?: number;
};

export type TraceCallsQueryRes = {
  calls: TraceCallSchema[];
};

interface TraceObjectsFilter {
  base_object_classes?: string[];
  object_names?: string[];
  is_op?: boolean;
  latest_only?: boolean;
}

type TraceObjQueryReq = {
  project_id: string;
  filter?: TraceObjectsFilter;
};

export interface TraceObjSchema {
  project_id: string;
  object_id: string;
  created_at: string;
  digest: string;
  version_index: number;
  is_latest: number;
  kind: 'op' | 'object';
  base_object_class?: string;
  val: any;
}

type TraceObjQueryRes = {
  objs: TraceObjSchema[];
};

export type TraceRefsReadBatchReq = {
  refs: string[];
};

export type TraceRefsReadBatchRes = {
  vals: any[];
};

export type TraceTableQueryReq = {
  project_id: string;
  digest: string;
  filter?: {
    row_digests?: string[];
  };
  limit?: number;
};

export type TraceTableQueryRes = {
  rows: Array<{
    digest: string;
    val: any;
  }>;
};

export type TraceFileContentReadReq = {
  project_id: string;
  digest: string;
};

export type TraceFileContentReadRes = {
  content: string;
};

const DEFAULT_BATCH_INTERVAL = 150;
const MAX_REFS_PER_BATCH = 1000;

export class TraceServerClient {
  private baseUrl: string;
  private readBatchCollectors: Array<{
    req: TraceRefsReadBatchReq;
    resolvePromise: (res: TraceRefsReadBatchRes) => void;
    rejectPromise: (err: any) => void;
  }> = [];
  private inFlightFetchesRequests: Record<
    string,
    Record<
      string,
      Array<{
        resolve: (res: any) => void;
        reject: (err: any) => void;
      }>
    >
  > = {};

  constructor(baseUrl: string) {
    this.readBatchCollectors = [];
    this.inFlightFetchesRequests = {};
    this.baseUrl = baseUrl;
    this.scheduleReadBatch();
  }

  callsQuery: (req: TraceCallsQueryReq) => Promise<TraceCallsQueryRes> =
    req => {
      return this.makeRequest<TraceCallsQueryReq, TraceCallsQueryRes>(
        '/calls/query',
        req
      );
    };
  callRead: (req: TraceCallReadReq) => Promise<TraceCallReadRes> = req => {
    return this.makeRequest<TraceCallReadReq, TraceCallReadRes>(
      '/call/read',
      req
    );
  };
  objsQuery: (req: TraceObjQueryReq) => Promise<TraceObjQueryRes> = req => {
    return this.makeRequest<TraceObjQueryReq, TraceObjQueryRes>(
      '/objs/query',
      req
    );
  };

  readBatch: (req: TraceRefsReadBatchReq) => Promise<TraceRefsReadBatchRes> =
    req => {
      return this.requestReadBatch(req);
    };

  tableQuery: (req: TraceTableQueryReq) => Promise<TraceTableQueryRes> =
    req => {
      return this.makeRequest<TraceTableQueryReq, TraceTableQueryRes>(
        '/table/query',
        req
      );
    };

  fileContent: (
    req: TraceFileContentReadReq
  ) => Promise<TraceFileContentReadRes> = req => {
    const res = this.makeRequest<TraceFileContentReadReq, string>(
      '/files/content',
      req,
      true
    );
    return new Promise((resolve, reject) => {
      res
        .then(content => {
          resolve({content});
        })
        .catch(err => {
          reject(err);
        });
    });
  };

  private makeRequest = async <QT, ST>(
    endpoint: string,
    req: QT,
    returnText?: boolean
  ): Promise<ST> => {
    const url = `${this.baseUrl}${endpoint}`;
    const reqBody = JSON.stringify(req);
    let needsFetch = false;
    if (!this.inFlightFetchesRequests[endpoint]) {
      this.inFlightFetchesRequests[endpoint] = {};
    }
    if (!this.inFlightFetchesRequests[endpoint][reqBody]) {
      this.inFlightFetchesRequests[endpoint][reqBody] = [];
      needsFetch = true;
    }

    const prom = new Promise<ST>((resolve, reject) => {
      this.inFlightFetchesRequests[endpoint][reqBody].push({resolve, reject});
    });

    if (!needsFetch) {
      return prom;
    }

    const headers: {[key: string]: string} = {
      'Content-Type': 'application/json',
      // This is a dummy auth header, the trace server requires
      // that we send a basic auth header, but it uses cookies for
      // authentication.
      Authorization: 'Basic ' + btoa(':'),
    };
    const useAdminPrivileges = getCookie('use_admin_privileges') === 'true';
    if (useAdminPrivileges) {
      headers['use-admin-privileges'] = 'true';
    }
    // eslint-disable-next-line wandb/no-unprefixed-urls
    fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: reqBody,
    })
      .then(response => {
        if (returnText) {
          return response.text();
        }
        return response.json();
      })
      .then(res => {
        try {
          const inFlightRequest = [
            ...this.inFlightFetchesRequests[endpoint]?.[reqBody],
          ];
          delete this.inFlightFetchesRequests[endpoint][reqBody];
          if (inFlightRequest) {
            inFlightRequest.forEach(({resolve}) => {
              resolve(res);
            });
          }
        } catch (err) {
          console.error(err);
        }
      })
      .catch(err => {
        try {
          const inFlightRequest = [
            ...this.inFlightFetchesRequests[endpoint]?.[reqBody],
          ];
          delete this.inFlightFetchesRequests[endpoint][reqBody];
          if (inFlightRequest) {
            inFlightRequest.forEach(({reject}) => {
              reject(err);
            });
          }
        } catch (err2) {
          console.error(err2);
        }
      });

    return prom;
  };

  private requestReadBatch: (
    req: TraceRefsReadBatchReq
  ) => Promise<TraceRefsReadBatchRes> = req => {
    return new Promise<TraceRefsReadBatchRes>((resolve, reject) => {
      this.readBatchCollectors.push({
        req,
        resolvePromise: resolve,
        rejectPromise: reject,
      });
    });
  };

  private doReadBatch = async () => {
    if (this.readBatchCollectors.length === 0) {
      return;
    }
    const collectors = [...this.readBatchCollectors];
    this.readBatchCollectors = [];
    const refs = _.uniq(collectors.map(c => c.req.refs).flat());
    const valMap = new Map<string, any>();
    while (refs.length > 0) {
      const refsForBatch = refs.splice(0, MAX_REFS_PER_BATCH);
      const res = await this.readBatchDirect({refs: refsForBatch});
      const vals = res.vals;
      for (let i = 0; i < refsForBatch.length; i++) {
        valMap.set(refsForBatch[i], vals[i]);
      }
    }
    collectors.forEach(collector => {
      const req = collector.req;
      const refVals = req.refs.map(ref => valMap.get(ref));
      collector.resolvePromise({vals: refVals});
    });
  };

  private scheduleReadBatch = async () => {
    await this.doReadBatch();
    setTimeout(this.scheduleReadBatch, DEFAULT_BATCH_INTERVAL);
  };

  private readBatchDirect: (
    req: TraceRefsReadBatchReq
  ) => Promise<TraceRefsReadBatchRes> = req => {
    return this.makeRequest<TraceRefsReadBatchReq, TraceRefsReadBatchRes>(
      '/refs/read_batch',
      req
    );
  };
}

const MAX_CHUNK_SIZE = 10000;

/**
 * Use this function to query calls from the trace server. This function will
 * handle chunking the results if the user requests more than `MAX_CHUNK_SIZE`
 * calls. This is to protect the server from returning too much data at once.
 *
 * Note: we should probably roll this into the `callsQuery` directly, but I don't
 * want to change the API right now to support cancelation.
 */
export const chunkedCallsQuery = (
  client: TraceServerClient,
  req: TraceCallsQueryReq,
  onSuccess: (res: TraceCallsQueryRes) => void,
  onError: (err: any) => void
): {
  cancel: () => void;
} => {
  let cancelled = false;

  const safeOnSuccess = (res: TraceCallsQueryRes) => {
    if (!cancelled) {
      onSuccess(res);
    }
  };

  const safeOnError = (err: any) => {
    if (!cancelled) {
      onError(err);
    }
  };

  const fetchCalls = async () => {
    const userRequestedLimit = req.limit ?? Infinity;
    const userRequestedOffset = req.offset ?? 0;
    const shouldPage = userRequestedLimit > MAX_CHUNK_SIZE;
    if (!shouldPage) {
      // If the user requested less than the max chunk size, we can just
      // make a single request.
      let page: TraceCallsQueryRes;
      try {
        page = await client.callsQuery(req);
      } catch (err) {
        safeOnError(err);
        return;
      }
      safeOnSuccess(page);
    } else {
      const allCallResults: TraceCallSchema[] = [];
      let effectiveOffset = userRequestedOffset;
      let effectiveRemainingLimit = userRequestedLimit;

      // Keep paging until we have all the results requested.
      while (effectiveRemainingLimit > 0) {
        const effectiveLimit = Math.min(
          effectiveRemainingLimit,
          MAX_CHUNK_SIZE
        );
        const pageReq = {
          ...req,
          limit: effectiveLimit,
          offset: effectiveOffset,
        };
        let page: TraceCallsQueryRes;
        try {
          page = await client.callsQuery(pageReq);
        } catch (err) {
          safeOnError(err);
          return;
        }
        allCallResults.push(...page.calls);
        effectiveRemainingLimit -= page.calls.length;
        effectiveOffset += page.calls.length;

        // Break if we have less than the requested limit.
        if (page.calls.length < effectiveLimit) {
          break;
        }
      }

      safeOnSuccess({
        calls: allCallResults,
      });
    }
  };
  fetchCalls();
  return {
    cancel: () => {
      cancelled = true;
    },
  };
};
